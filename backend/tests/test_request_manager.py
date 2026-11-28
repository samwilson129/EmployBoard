import asyncio

import httpx

from app.config import Settings
from app.services.ats_request_manager import ATSRequestManager
from app.services.description_cache_service import DescriptionCacheService
from app.services.ingestion_service import IngestionService
from app.services.job_sync_service import JobSyncService


def settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test",
        ats_request_config_json='{"test":{"retry_count":1,"initial_retry_delay":0,"max_retry_delay":0}}',
    )


def test_request_manager_coalesces_identical_requests():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"ok": True})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            manager = ATSRequestManager(client, settings())
            values = await asyncio.gather(
                *(manager.get_json("test", "https://example.test/jobs") for _ in range(20))
            )
            assert values == [{"ok": True}] * 20

    asyncio.run(run())
    assert calls == 1


def test_request_manager_retries_429():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            manager = ATSRequestManager(client, settings())
            assert await manager.get_json("test", "https://example.test/jobs") == {
                "ok": True
            }
            assert manager.metrics()["test"]["rate_limits"] == 1

    asyncio.run(run())
    assert calls == 2


def test_cache_eviction_count_never_allows_capacity_overflow():
    assert DescriptionCacheService.eviction_count(0, 10) == 0
    assert DescriptionCacheService.eviction_count(10, 10) == 1
    assert DescriptionCacheService.eviction_count(14, 10) == 5


def test_ledger_payload_compaction_removes_unbounded_content():
    compacted = JobSyncService._compact_payload(
        {
            "id": "job-1",
            "descriptionHtml": "<p>long description</p>",
            "nested": {"content": "large body", "team": "Engineering"},
            "labels": ["remote", "full-time"],
        }
    )
    assert compacted == {
        "id": "job-1",
        "nested": {"team": "Engineering"},
        "labels": ["remote", "full-time"],
    }


def test_request_metric_delta_uses_only_current_run():
    delta = IngestionService._metric_delta(
        {
            "requests": 10,
            "rate_limits": 1,
            "failures": 2,
            "total_response_ms": 1000,
        },
        {
            "requests": 14,
            "rate_limits": 2,
            "failures": 3,
            "total_response_ms": 1600,
        },
    )
    assert delta == {
        "requests": 4,
        "rate_limits": 1,
        "failures": 1,
        "average_response_ms": 150,
    }
