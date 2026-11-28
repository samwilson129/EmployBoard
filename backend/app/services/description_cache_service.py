from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.adapters.registry import build_adapter
from app.config import Settings
from app.models.job import Job
from app.models.job_description_cache import JobDescriptionCache
from app.models.job_description_negative_cache import JobDescriptionNegativeCache
from app.services.ats_request_manager import ATSRequestManager
from app.services.normalization_service import normalize_adapter_job

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CachedDescription:
    description: str | None
    requirements: str | None
    responsibilities: str | None
    skills: list[str] | None


class CacheMetrics:
    def __init__(self) -> None:
        self._values: dict[str, int] = {
            "cache_hits": 0,
            "cache_misses": 0,
            "description_fetch_failures": 0,
            "negative_cache_hits": 0,
            "evictions": 0,
            "cleanup_expired": 0,
            "cleanup_orphans": 0,
        }

    def increment(self, key: str, amount: int = 1) -> None:
        self._values[key] = self._values.get(key, 0) + amount

    def snapshot(self, current_size: int, capacity: int) -> dict[str, int | float]:
        hits = self._values["cache_hits"]
        misses = self._values["cache_misses"]
        return {
            **self._values,
            "current_size": current_size,
            "capacity": capacity,
            "cache_hit_ratio": hits / (hits + misses) if hits + misses else 0.0,
        }


CACHE_METRICS = CacheMetrics()


class DescriptionCacheService:
    _inflight: dict[uuid.UUID, asyncio.Task[CachedDescription | None]] = {}
    _inflight_lock = asyncio.Lock()

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ):
        self.session_factory = session_factory
        self.settings = settings

    async def get_or_fetch(
        self, session: AsyncSession, job: Job
    ) -> CachedDescription | None:
        now = datetime.now(UTC)
        cached = await session.scalar(
            select(JobDescriptionCache).where(
                JobDescriptionCache.job_id == job.job_id,
                JobDescriptionCache.expires_at > now,
            )
        )
        if cached is not None:
            cached.last_accessed_at = now
            cached.fetch_count += 1
            CACHE_METRICS.increment("cache_hits")
            await session.commit()
            return self._value(cached)

        negative = await session.scalar(
            select(JobDescriptionNegativeCache).where(
                JobDescriptionNegativeCache.job_id == job.job_id,
                JobDescriptionNegativeCache.retry_after_at > now,
            )
        )
        if negative is not None:
            CACHE_METRICS.increment("negative_cache_hits")
            return None

        CACHE_METRICS.increment("cache_misses")
        if self._has_legacy_content(job):
            value = CachedDescription(
                description=job.description,
                requirements=job.requirements,
                responsibilities=job.responsibilities,
                skills=job.skills,
            )
            await self._store(session, job.job_id, value, None, now)
            job.description = None
            job.requirements = None
            job.responsibilities = None
            await session.commit()
            return value

        async with self._inflight_lock:
            task = self._inflight.get(job.job_id)
            if task is None:
                task = asyncio.create_task(self._fetch_and_store(job.job_id))
                self._inflight[job.job_id] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                async with self._inflight_lock:
                    if self._inflight.get(job.job_id) is task:
                        self._inflight.pop(job.job_id, None)

    async def _fetch_and_store(self, job_id: uuid.UUID) -> CachedDescription | None:
        async with self.session_factory() as session:
            job = await session.scalar(
                select(Job)
                .where(Job.job_id == job_id)
                .options(selectinload(Job.company), selectinload(Job.sources))
            )
            if job is None:
                return None
            if self._has_legacy_content(job):
                value = CachedDescription(
                    job.description,
                    job.requirements,
                    job.responsibilities,
                    job.skills,
                )
                await self._store(session, job_id, value, None, datetime.now(UTC))
                job.description = None
                job.requirements = None
                job.responsibilities = None
                await session.commit()
                return value

            try:
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    headers={
                        "User-Agent": self.settings.user_agent,
                        "Accept": "application/json, application/rss+xml, text/xml",
                    },
                ) as client:
                    manager = ATSRequestManager(client, self.settings)
                    for source in sorted(
                        job.sources,
                        key=lambda item: item.last_verified_at
                        or item.fetched_at,
                        reverse=True,
                    ):
                        adapter = build_adapter(
                            source.ats_provider, client, self.settings, manager
                        )
                        if not adapter.supports_detail:
                            continue
                        detail = await adapter.fetch_detail(
                            job.company, source.external_job_id, source.source_payload
                        )
                        if detail is None:
                            continue
                        normalized = normalize_adapter_job(detail, job.company)
                        value = CachedDescription(
                            normalized.description,
                            normalized.requirements,
                            normalized.responsibilities,
                            normalized.skills,
                        )
                        if self._has_value(value):
                            await self._store(
                                session,
                                job_id,
                                value,
                                source.ats_provider,
                                datetime.now(UTC),
                            )
                            await session.commit()
                            return value
                await self._negative(
                    session, job_id, "description_unavailable", datetime.now(UTC)
                )
                await session.commit()
                CACHE_METRICS.increment("description_fetch_failures")
                return None
            except Exception as exc:  # noqa: BLE001 - negative cache isolates failures
                reason = "rate_limited" if "429" in str(exc) else "transient_error"
                await self._negative(session, job_id, reason, datetime.now(UTC))
                await session.commit()
                CACHE_METRICS.increment("description_fetch_failures")
                logger.warning("Description fetch failed for %s: %s", job_id, exc)
                return None

    async def _store(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        value: CachedDescription,
        provider: str | None,
        now: datetime,
    ) -> None:
        # PostgreSQL advisory locking makes the capacity check atomic across
        # concurrent API requests without adding Redis.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('job_description_cache'))")
        )
        row = await session.get(JobDescriptionCache, job_id)
        if row is None:
            count = int(
                await session.scalar(select(func.count(JobDescriptionCache.job_id)))
                or 0
            )
            if count >= self.settings.job_description_cache_max_entries:
                victims = (
                    select(JobDescriptionCache.job_id)
                    .order_by(JobDescriptionCache.last_accessed_at.asc())
                    .limit(
                        self.eviction_count(
                            count, self.settings.job_description_cache_max_entries
                        )
                    )
                )
                result = await session.execute(
                    delete(JobDescriptionCache).where(
                        JobDescriptionCache.job_id.in_(victims)
                    )
                )
                CACHE_METRICS.increment("evictions", result.rowcount or 0)
            row = JobDescriptionCache(job_id=job_id)
            session.add(row)
        row.description = value.description
        row.requirements = value.requirements
        row.responsibilities = value.responsibilities
        row.skills = value.skills
        row.cached_at = now
        row.last_accessed_at = now
        row.expires_at = now + timedelta(
            hours=self.settings.job_description_cache_ttl_hours
        )
        row.source_provider = provider
        row.source_updated_at = now
        row.fetch_count = (row.fetch_count or 0) + 1
        negative = await session.get(JobDescriptionNegativeCache, job_id)
        if negative is not None:
            await session.delete(negative)

    async def _negative(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        reason: str,
        now: datetime,
    ) -> None:
        row = await session.get(JobDescriptionNegativeCache, job_id)
        if row is None:
            row = JobDescriptionNegativeCache(job_id=job_id)
            session.add(row)
        row.failure_reason = reason
        row.failed_at = now
        row.retry_after_at = now + timedelta(
            minutes=self.settings.job_description_negative_ttl_minutes
        )

    async def cleanup(self, session: AsyncSession) -> dict[str, int]:
        now = datetime.now(UTC)
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('job_description_cache'))")
        )
        expired = await session.execute(
            delete(JobDescriptionCache).where(
                JobDescriptionCache.expires_at <= now
            )
        )
        negative = await session.execute(
            delete(JobDescriptionNegativeCache).where(
                JobDescriptionNegativeCache.retry_after_at <= now
            )
        )
        orphan = await session.execute(
            delete(JobDescriptionCache).where(
                ~JobDescriptionCache.job_id.in_(select(Job.job_id))
            )
        )
        count = int(
            await session.scalar(select(func.count(JobDescriptionCache.job_id))) or 0
        )
        capacity_evicted = 0
        if count > self.settings.job_description_cache_max_entries:
            victims = (
                select(JobDescriptionCache.job_id)
                .order_by(JobDescriptionCache.last_accessed_at.asc())
                .limit(count - self.settings.job_description_cache_max_entries)
            )
            result = await session.execute(
                delete(JobDescriptionCache).where(
                    JobDescriptionCache.job_id.in_(victims)
                )
            )
            capacity_evicted = result.rowcount or 0
        await session.commit()
        CACHE_METRICS.increment("cleanup_expired", expired.rowcount or 0)
        CACHE_METRICS.increment("cleanup_orphans", orphan.rowcount or 0)
        CACHE_METRICS.increment("evictions", capacity_evicted)
        return {
            "expired": expired.rowcount or 0,
            "negative": negative.rowcount or 0,
            "orphans": orphan.rowcount or 0,
            "capacity_evicted": capacity_evicted,
        }

    async def metrics(self, session: AsyncSession) -> dict[str, int | float]:
        size = int(
            await session.scalar(select(func.count(JobDescriptionCache.job_id))) or 0
        )
        return CACHE_METRICS.snapshot(
            size, self.settings.job_description_cache_max_entries
        )

    @staticmethod
    def _value(row: JobDescriptionCache) -> CachedDescription:
        return CachedDescription(
            row.description, row.requirements, row.responsibilities, row.skills
        )

    @staticmethod
    def eviction_count(count: int, capacity: int) -> int:
        return max(1, count - capacity + 1) if count >= capacity else 0

    @staticmethod
    def _has_value(value: CachedDescription) -> bool:
        return any(
            item is not None and item != ""
            for item in (
                value.description,
                value.requirements,
                value.responsibilities,
            )
        )

    @staticmethod
    def _has_legacy_content(job: Job) -> bool:
        return any(
            item is not None and item != ""
            for item in (job.description, job.requirements, job.responsibilities)
        )


async def run_cache_maintenance(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as session:
        result = await DescriptionCacheService(session_factory, settings).cleanup(session)
        logger.info("Description cache maintenance finished: %s", result)
