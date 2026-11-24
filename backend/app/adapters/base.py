from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings
from app.models.company import Company

logger = logging.getLogger(__name__)


class AdapterError(RuntimeError):
    """A source could not be fetched or parsed safely."""


class TransientAdapterError(AdapterError):
    """A retryable source failure."""


@dataclass(slots=True)
class AdapterJob:
    """Provider-neutral intermediate representation produced by an adapter.

    Adapters are allowed to understand provider payloads. They are not allowed
    to decide canonical enum values, salary policy or deduplication; that is
    handled by the provider-independent normalization and sync services.
    """

    external_job_id: str
    title: str
    application_url: str
    original_job_url: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type_raw: str | None = None
    workplace_type_raw: str | None = None
    experience_level_raw: str | None = None
    description_html: str | None = None
    requirements_html: str | None = None
    responsibilities_html: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    requisition_id: str | None = None
    skills: list[str] | None = None
    source_payload: dict[str, Any] = field(default_factory=dict)
    detail_fetched: bool = False


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, min(float(value), 60.0))
    except ValueError:
        return None


async def request_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    max_retries: int = 3,
) -> Any:
    """GET JSON with timeouts, Retry-After support and bounded exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await client.get(url, params=params)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            if attempt >= max_retries:
                raise TransientAdapterError(f"Network failure for {url}: {exc}") from exc
            await asyncio.sleep(min(2**attempt + random.uniform(0, 0.4), 15))
            continue

        if response.status_code == 429 or 500 <= response.status_code < 600:
            last_error = AdapterError(
                f"HTTP {response.status_code} from {url}: {response.text[:200]}"
            )
            if attempt >= max_retries:
                raise TransientAdapterError(str(last_error)) from last_error
            delay = _retry_after_seconds(response)
            if delay is None:
                delay = min(2**attempt + random.uniform(0, 0.5), 20)
            logger.warning(
                "Retrying %s after HTTP %s in %.1fs (attempt %s/%s)",
                url,
                response.status_code,
                delay,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(delay)
            continue

        if response.status_code == 404:
            raise AdapterError(f"HTTP 404 from {url}: board or endpoint not found")
        if response.status_code in (401, 403):
            raise AdapterError(
                f"HTTP {response.status_code} from {url}: access is not permitted"
            )
        if response.is_error:
            raise AdapterError(
                f"HTTP {response.status_code} from {url}: {response.text[:300]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise AdapterError(f"Invalid JSON from {url}") from exc

    raise TransientAdapterError(f"Request failed for {url}: {last_error}")


class ATSAdapter(ABC):
    provider: str
    display_name: str
    documentation_url: str
    supports_detail: bool = False

    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    @abstractmethod
    async def fetch_jobs(self, company: Company) -> list[AdapterJob]:
        raise NotImplementedError

    async def fetch_detail(
        self,
        company: Company,
        external_job_id: str,
        existing_payload: dict[str, Any] | None = None,
    ) -> AdapterJob | None:
        """Optional detail endpoint for providers whose list response is sparse."""
        return None

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return await request_json(
            self.client,
            url,
            params=params,
            max_retries=self.settings.http_max_retries,
        )
