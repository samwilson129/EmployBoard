from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderRequestConfig:
    requests_per_minute: int
    max_concurrency: int
    retry_count: int
    initial_retry_delay: float
    max_retry_delay: float
    backoff_multiplier: float
    timeout_seconds: float


class ATSRequestManager:
    """Shared, provider-aware HTTP request manager.

    A manager is scoped to one AsyncClient/ingestion cycle. It rate-limits
    providers independently and coalesces identical concurrent GETs.
    """

    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._window_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._singleflight: dict[str, asyncio.Task[Any]] = {}
        self._singleflight_lock = asyncio.Lock()
        self._metrics: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "requests": 0,
                "rate_limits": 0,
                "failures": 0,
                "total_response_ms": 0,
            }
        )

    def config_for(self, provider: str) -> ProviderRequestConfig:
        override = self.settings.ats_request_config.get(provider, {})
        if not isinstance(override, dict):
            override = {}
        return ProviderRequestConfig(
            requests_per_minute=int(
                override.get(
                    "requests_per_minute",
                    self.settings.ats_default_requests_per_minute,
                )
            ),
            max_concurrency=int(
                override.get(
                    "max_concurrency", self.settings.ats_default_max_concurrency
                )
            ),
            retry_count=int(override.get("retry_count", self.settings.http_max_retries)),
            initial_retry_delay=float(
                override.get(
                    "initial_retry_delay",
                    self.settings.ats_default_retry_delay_seconds,
                )
            ),
            max_retry_delay=float(
                override.get(
                    "max_retry_delay",
                    self.settings.ats_default_max_retry_delay_seconds,
                )
            ),
            backoff_multiplier=float(
                override.get(
                    "backoff_multiplier",
                    self.settings.ats_default_backoff_multiplier,
                )
            ),
            timeout_seconds=float(
                override.get("timeout_seconds", self.settings.http_timeout_seconds)
            ),
        )

    async def get_json(
        self,
        provider: str,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        key = self._key("json", provider, url, params)
        return await self._singleflight_get(
            key,
            lambda: self._request(provider, url, params=params, response_type="json"),
        )

    async def get_text(
        self,
        provider: str,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        key = self._key("text", provider, url, params)
        return await self._singleflight_get(
            key,
            lambda: self._request(provider, url, params=params, response_type="text"),
        )

    async def _singleflight_get(self, key: str, factory):
        async with self._singleflight_lock:
            task = self._singleflight.get(key)
            if task is None:
                task = asyncio.create_task(factory())
                self._singleflight[key] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                async with self._singleflight_lock:
                    if self._singleflight.get(key) is task:
                        self._singleflight.pop(key, None)

    async def _request(
        self,
        provider: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        response_type: str,
    ) -> Any:
        config = self.config_for(provider)
        semaphore = self._semaphores.setdefault(
            provider, asyncio.Semaphore(config.max_concurrency)
        )
        async with semaphore:
            for attempt in range(config.retry_count + 1):
                await self._wait_for_slot(provider, config.requests_per_minute)
                started = time.perf_counter()
                try:
                    response = await self.client.get(
                        url,
                        params=params,
                        timeout=httpx.Timeout(config.timeout_seconds, connect=10),
                    )
                except (httpx.TimeoutException, httpx.NetworkError):
                    self._metrics[provider]["failures"] += 1
                    if attempt >= config.retry_count:
                        raise
                    await self._backoff(config, attempt)
                    continue
                finally:
                    self._metrics[provider]["requests"] += 1
                    self._metrics[provider]["total_response_ms"] += (
                        time.perf_counter() - started
                    ) * 1000

                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if response.status_code == 429:
                        self._metrics[provider]["rate_limits"] += 1
                    if attempt >= config.retry_count:
                        self._metrics[provider]["failures"] += 1
                        raise httpx.HTTPStatusError(
                            f"Retry limit reached for {provider}: HTTP {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                    retry_after = self._retry_after(response)
                    await self._backoff(config, attempt, retry_after)
                    continue
                if response.status_code >= 400:
                    self._metrics[provider]["failures"] += 1
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code} from {url}",
                        request=response.request,
                        response=response,
                    )
                return response.json() if response_type == "json" else response.text

        raise RuntimeError("request manager exited without a response")

    async def _wait_for_slot(self, provider: str, requests_per_minute: int) -> None:
        async with self._window_locks[provider]:
            window = self._windows[provider]
            now = time.monotonic()
            while window and now - window[0] >= 60:
                window.popleft()
            if len(window) >= requests_per_minute:
                await asyncio.sleep(max(0, 60 - (now - window[0])))
                now = time.monotonic()
                while window and now - window[0] >= 60:
                    window.popleft()
            window.append(time.monotonic())

    async def _backoff(
        self,
        config: ProviderRequestConfig,
        attempt: int,
        retry_after: float | None = None,
    ) -> None:
        if retry_after is not None:
            delay = min(retry_after, config.max_retry_delay)
        else:
            delay = min(
                config.initial_retry_delay * config.backoff_multiplier**attempt,
                config.max_retry_delay,
            )
            delay = delay * (0.8 + random.random() * 0.4)
        await asyncio.sleep(delay)

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after")
        if not value:
            return None
        try:
            return max(0, float(value))
        except ValueError:
            return None

    @staticmethod
    def _key(
        response_type: str,
        provider: str,
        url: str,
        params: dict[str, Any] | None,
    ) -> str:
        return json.dumps(
            [response_type, provider, url, sorted((params or {}).items())],
            sort_keys=True,
            default=str,
        )

    def metrics(self) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for provider, values in self._metrics.items():
            requests = values["requests"]
            result[provider] = {
                **values,
                "average_response_ms": (
                    values["total_response_ms"] / requests if requests else 0
                ),
            }
        return result
