from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.base import ATSAdapter
from app.config import Settings
from app.models.company import Company
from app.models.job import Job
from app.models.job_source import JobSource
from app.services.deduplication_service import (
    find_cross_source_candidate,
    find_requisition_match,
)
from app.services.normalization_service import (
    NormalizationError,
    NormalizedJob,
    normalize_adapter_job,
)

logger = logging.getLogger(__name__)

_MAX_RECORDED_ERRORS = 100


@dataclass
class SyncStats:
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    deactivated: int = 0
    skipped: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def add_error(self, stage: str, message: str, **context: Any) -> None:
        if len(self.errors) >= _MAX_RECORDED_ERRORS:
            return
        self.errors.append({"stage": stage, "error": message, **context})

    def as_dict(self) -> dict[str, Any]:
        return {
            "jobs_fetched": self.fetched,
            "jobs_inserted": self.inserted,
            "jobs_updated": self.updated,
            "jobs_deactivated": self.deactivated,
            "jobs_skipped": self.skipped,
            "error_count": len(self.errors),
        }


class JobSyncService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def sync_company(
        self,
        session: AsyncSession,
        company: Company,
        adapter: ATSAdapter,
        *,
        now: datetime | None = None,
    ) -> SyncStats:
        now = now or datetime.now(UTC)
        stats = SyncStats()

        adapter_jobs = await adapter.fetch_jobs(company)
        stats.fetched = len(adapter_jobs)
        logger.info(
            "Fetched %s jobs from %s board %s",
            stats.fetched,
            adapter.provider,
            company.board_identifier,
        )

        seen_external_ids: set[str] = set()
        for adapter_job in adapter_jobs:
            seen_external_ids.add(str(adapter_job.external_job_id))
            try:
                async with session.begin_nested():
                    normalized = normalize_adapter_job(adapter_job, company)
                    outcome = await self._upsert_job(
                        session, company, adapter.provider, normalized, now
                    )
                if outcome == "inserted":
                    stats.inserted += 1
                else:
                    stats.updated += 1
            except NormalizationError as exc:
                stats.skipped += 1
                stats.add_error(
                    "validation",
                    str(exc),
                    external_job_id=str(adapter_job.external_job_id),
                )
            except Exception as exc:  # noqa: BLE001 - one bad job must not stop the run
                stats.skipped += 1
                stats.add_error(
                    "upsert",
                    str(exc),
                    external_job_id=str(adapter_job.external_job_id),
                )
                logger.exception(
                    "Failed to upsert %s job %s",
                    adapter.provider,
                    adapter_job.external_job_id,
                )

        await session.flush()

        if adapter.supports_detail:
            await self._enrich_details(session, company, adapter, stats, now)
            await session.flush()

        await self._deactivate_missing(
            session,
            company,
            adapter.provider,
            seen_external_ids,
            stats,
            now,
        )
        return stats

    async def _upsert_job(
        self,
        session: AsyncSession,
        company: Company,
        provider: str,
        job: NormalizedJob,
        now: datetime,
    ) -> str:
        source = await session.scalar(
            select(JobSource)
            .where(
                JobSource.ats_provider == provider,
                JobSource.external_job_id == job.external_job_id,
            )
            .options(selectinload(JobSource.job))
        )

        if source is not None:
            canonical = source.job
            self._apply_job_fields(canonical, job, now, preserve_missing=True)
            source.original_job_url = job.original_job_url
            source.source_payload = self._merge_payload(
                source.source_payload, job.source_payload
            )
            source.fetched_at = now
            source.last_verified_at = now
            await session.flush()
            return "updated"

        canonical = await find_requisition_match(
            session, company.company_id, job.requisition_id
        )
        if canonical is not None:
            self._apply_job_fields(canonical, job, now, preserve_missing=True)
            session.add(
                JobSource(
                    job=canonical,
                    ats_provider=provider,
                    external_job_id=job.external_job_id,
                    original_job_url=job.original_job_url,
                    source_payload=job.source_payload,
                    fetched_at=now,
                    last_verified_at=now,
                )
            )
            await session.flush()
            logger.info(
                "Merged %s job %s into canonical job %s via requisition %s",
                provider,
                job.external_job_id,
                canonical.job_id,
                job.requisition_id,
            )
            return "updated"

        canonical = Job(
            job_id=uuid.uuid4(),
            company_id=company.company_id,
            title=job.title,
            normalized_title=job.normalized_title or job.title.lower(),
            normalized_location=job.normalized_location,
            requisition_id=job.requisition_id,
            department=job.department,
            location=job.location,
            employment_type=job.employment_type,
            workplace_type=job.workplace_type,
            experience_level=job.experience_level,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
            salary_interval=job.salary_interval,
            description=job.description,
            requirements=job.requirements,
            responsibilities=job.responsibilities,
            skills=job.skills,
            posted_at=job.posted_at,
            expires_at=job.expires_at,
            application_url=job.application_url,
            is_active=True,
            missing_sync_count=0,
            first_seen_at=now,
            last_seen_at=now,
        )

        candidate = await find_cross_source_candidate(
            session, company.company_id, job, provider
        )
        if candidate is not None:
            canonical.duplicate_of_job_id = candidate.job_id
            logger.info(
                "Flagged possible cross-source duplicate %s -> %s for %s",
                job.external_job_id,
                candidate.job_id,
                company.company_name,
            )

        session.add(canonical)
        await session.flush()
        session.add(
            JobSource(
                job=canonical,
                ats_provider=provider,
                external_job_id=job.external_job_id,
                original_job_url=job.original_job_url,
                source_payload=job.source_payload,
                fetched_at=now,
                last_verified_at=now,
            )
        )
        await session.flush()
        return "inserted"

    @staticmethod
    def _apply_job_fields(
        canonical: Job,
        job: NormalizedJob,
        now: datetime,
        *,
        preserve_missing: bool,
    ) -> None:
        canonical.title = job.title
        canonical.normalized_title = job.normalized_title or job.title.lower()
        canonical.application_url = job.application_url
        canonical.last_seen_at = now
        canonical.is_active = True
        canonical.missing_sync_count = 0

        optional_fields = (
            "normalized_location",
            "requisition_id",
            "department",
            "location",
            "employment_type",
            "workplace_type",
            "experience_level",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_interval",
            "description",
            "requirements",
            "responsibilities",
            "skills",
            "posted_at",
            "expires_at",
        )
        for field_name in optional_fields:
            value = getattr(job, field_name)
            if value is None and preserve_missing:
                continue
            setattr(canonical, field_name, value)

    @staticmethod
    def _merge_payload(
        existing: dict[str, Any] | None, incoming: dict[str, Any] | None
    ) -> dict[str, Any]:
        incoming = incoming or {}
        if not existing:
            return incoming
        if isinstance(existing, dict) and "detail" in existing:
            if "detail" not in incoming:
                merged = dict(incoming)
                merged["detail"] = existing["detail"]
                return merged
        return incoming

    async def _enrich_details(
        self,
        session: AsyncSession,
        company: Company,
        adapter: ATSAdapter,
        stats: SyncStats,
        now: datetime,
    ) -> None:
        config = company.config or {}
        configured_limit = config.get("detail_limit")
        if isinstance(configured_limit, (int, float)):
            limit = max(0, int(configured_limit))
        else:
            limit = self.settings.smartrecruiters_detail_limit
        if limit == 0:
            return

        stmt = (
            select(Job)
            .join(JobSource, JobSource.job_id == Job.job_id)
            .where(
                Job.company_id == company.company_id,
                Job.is_active.is_(True),
                Job.description.is_(None),
                JobSource.ats_provider == adapter.provider,
            )
            .options(selectinload(Job.sources))
            .order_by(Job.posted_at.desc().nullslast())
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        jobs = (await session.scalars(stmt)).all()
        logger.info(
            "Enriching details for %s %s jobs (%s)",
            len(jobs),
            adapter.provider,
            company.company_name,
        )
        for canonical in jobs:
            source = next(
                (
                    item
                    for item in canonical.sources
                    if item.ats_provider == adapter.provider
                ),
                None,
            )
            if source is None:
                continue
            try:
                detail = await adapter.fetch_detail(
                    company, source.external_job_id, source.source_payload
                )
                if detail is None:
                    continue
                normalized = normalize_adapter_job(detail, company)
                self._apply_job_fields(canonical, normalized, now, preserve_missing=True)
                source.source_payload = detail.source_payload
                source.last_verified_at = now
                if normalized.original_job_url:
                    source.original_job_url = normalized.original_job_url
                await session.flush()
            except Exception as exc:  # noqa: BLE001 - detail failures are isolated
                stats.add_error(
                    "detail",
                    str(exc),
                    external_job_id=source.external_job_id,
                )
                logger.warning(
                    "Detail fetch failed for %s %s: %s",
                    adapter.provider,
                    source.external_job_id,
                    exc,
                )

    async def _deactivate_missing(
        self,
        session: AsyncSession,
        company: Company,
        provider: str,
        seen_external_ids: set[str],
        stats: SyncStats,
        now: datetime,
    ) -> None:
        previous_active = await session.scalar(
            select(func.count(func.distinct(Job.job_id)))
            .select_from(Job)
            .join(JobSource, JobSource.job_id == Job.job_id)
            .where(
                Job.company_id == company.company_id,
                Job.is_active.is_(True),
                JobSource.ats_provider == provider,
            )
        )
        previous_active = int(previous_active or 0)

        if stats.fetched == 0:
            logger.warning(
                "Skipping deactivation for %s: source returned zero jobs",
                company.company_name,
            )
            return
        if (
            previous_active > 0
            and stats.fetched
            < previous_active * self.settings.deactivation_min_fetch_ratio
        ):
            logger.warning(
                "Skipping deactivation for %s: fetched %s jobs vs %s previously active "
                "(below safety ratio %.2f)",
                company.company_name,
                stats.fetched,
                previous_active,
                self.settings.deactivation_min_fetch_ratio,
            )
            return

        stmt = (
            select(Job)
            .where(
                Job.company_id == company.company_id,
                Job.is_active.is_(True),
            )
            .options(selectinload(Job.sources))
            .execution_options(populate_existing=True)
        )
        jobs = (await session.scalars(stmt)).all()
        for canonical in jobs:
            provider_sources = [
                source
                for source in canonical.sources
                if source.ats_provider == provider
            ]
            if not provider_sources:
                continue
            if any(
                source.external_job_id in seen_external_ids
                for source in provider_sources
            ):
                continue
            # A canonical job linked to another provider is handled by that
            # provider's synchronization, not this one.
            if len(canonical.sources) > len(provider_sources):
                continue
            canonical.missing_sync_count = (canonical.missing_sync_count or 0) + 1
            if (
                canonical.missing_sync_count
                >= self.settings.deactivation_miss_threshold
            ):
                canonical.is_active = False
                stats.deactivated += 1
                logger.info(
                    "Deactivated job %s (%s) after %s consecutive confirmed absences",
                    canonical.job_id,
                    canonical.title,
                    canonical.missing_sync_count,
                )
        await session.flush()
