from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.registry import build_adapter
from app.config import Settings
from app.models.company import Company
from app.models.ingestion_run import IngestionRun
from app.services.job_sync_service import JobSyncService, SyncStats
from app.services.ats_request_manager import ATSRequestManager
from app.services.description_cache_service import DescriptionCacheService

logger = logging.getLogger(__name__)

_ADVISORY_LOCK_NAME = "employboard_ingestion"


class IngestionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ):
        self.session_factory = session_factory
        self.settings = settings
        self.sync_service = JobSyncService(settings)

    async def sync_all(
        self,
        *,
        company_ids: list[uuid.UUID] | None = None,
        providers: list[str] | None = None,
    ) -> dict[str, Any]:
        started_at = datetime.now(UTC)
        async with self.session_factory() as lock_session:
            acquired = await lock_session.scalar(
                text("SELECT pg_try_advisory_lock(hashtext(:name))"),
                {"name": _ADVISORY_LOCK_NAME},
            )
            if not acquired:
                return {
                    "status": "already_running",
                    "started_at": started_at.isoformat(),
                    "message": "An ingestion cycle is already running.",
                    "companies": [],
                }
            await lock_session.commit()

            try:
                companies = await self._load_companies(company_ids, providers)
                results: list[dict[str, Any]] = []
                headers = {
                    "User-Agent": self.settings.user_agent,
                    "Accept": "application/json",
                }
                timeout = httpx.Timeout(self.settings.http_timeout_seconds, connect=10)
                async with httpx.AsyncClient(
                    timeout=timeout,
                    headers=headers,
                    follow_redirects=True,
                    limits=httpx.Limits(
                        max_connections=10, max_keepalive_connections=5
                    ),
                ) as client:
                    request_manager = ATSRequestManager(client, self.settings)
                    for company in companies:
                        result = await self._sync_one(
                            company, client, request_manager
                        )
                        results.append(result)
                        # Be polite between independent public sources.
                        await asyncio.sleep(0.5)

                async with self.session_factory() as cache_session:
                    cache_result = await DescriptionCacheService(
                        self.session_factory, self.settings
                    ).cleanup(cache_session)
                    logger.info(
                        "Ingestion cache maintenance finished: %s", cache_result
                    )

                finished_at = datetime.now(UTC)
                totals = {
                    "companies": len(results),
                    "jobs_fetched": sum(
                        item.get("stats", {}).get("jobs_fetched", 0)
                        for item in results
                    ),
                    "jobs_inserted": sum(
                        item.get("stats", {}).get("jobs_inserted", 0)
                        for item in results
                    ),
                    "jobs_updated": sum(
                        item.get("stats", {}).get("jobs_updated", 0)
                        for item in results
                    ),
                    "jobs_deactivated": sum(
                        item.get("stats", {}).get("jobs_deactivated", 0)
                        for item in results
                    ),
                    "jobs_skipped": sum(
                        item.get("stats", {}).get("jobs_skipped", 0)
                        for item in results
                    ),
                    "failed_companies": sum(
                        1 for item in results if item.get("status") == "failed"
                    ),
                }
                status = (
                    "failed"
                    if totals["companies"] and totals["failed_companies"] == totals["companies"]
                    else "partial"
                    if totals["failed_companies"]
                    else "success"
                )
                return {
                    "status": status,
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "totals": totals,
                    "companies": results,
                }
            finally:
                await lock_session.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:name))"),
                    {"name": _ADVISORY_LOCK_NAME},
                )
                await lock_session.commit()

    async def _load_companies(
        self,
        company_ids: list[uuid.UUID] | None,
        providers: list[str] | None,
    ) -> list[Company]:
        async with self.session_factory() as session:
            stmt = (
                select(Company)
                .where(Company.is_active.is_(True))
                .order_by(Company.company_name.asc())
            )
            if company_ids:
                stmt = stmt.where(Company.company_id.in_(company_ids))
            if providers:
                stmt = stmt.where(Company.ats_provider.in_(providers))
            return list((await session.scalars(stmt)).all())

    async def _sync_one(
        self,
        company: Company,
        client: httpx.AsyncClient,
        request_manager: ATSRequestManager,
    ) -> dict[str, Any]:
        run_id = await self._start_run(company)
        started_at = datetime.now(UTC)
        before = request_manager.metrics().get(company.ats_provider, {})
        try:
            adapter = build_adapter(
                company.ats_provider, client, self.settings, request_manager
            )
            async with self.session_factory() as session:
                canonical_company = await session.get(Company, company.company_id)
                if canonical_company is None:
                    raise RuntimeError("Company disappeared before synchronization")
                stats = await self.sync_service.sync_company(
                    session, canonical_company, adapter
                )
                await session.commit()
            status = "success" if not stats.errors else "partial"
            after = request_manager.metrics().get(company.ats_provider, {})
            await self._finish_run(
                run_id,
                status,
                stats,
                request_metrics=self._metric_delta(before, after),
            )
            return {
                "run_id": str(run_id),
                "company_id": str(company.company_id),
                "company_name": company.company_name,
                "ats_provider": company.ats_provider,
                "status": status,
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(UTC).isoformat(),
                "stats": stats.as_dict(),
            }
        except Exception as exc:  # noqa: BLE001 - one source must not stop the cycle
            logger.exception(
                "Ingestion failed for %s (%s)",
                company.company_name,
                company.ats_provider,
            )
            after = request_manager.metrics().get(company.ats_provider, {})
            await self._finish_run(
                run_id,
                "failed",
                None,
                error=str(exc),
                request_metrics=self._metric_delta(before, after),
            )
            return {
                "run_id": str(run_id),
                "company_id": str(company.company_id),
                "company_name": company.company_name,
                "ats_provider": company.ats_provider,
                "status": "failed",
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(UTC).isoformat(),
                "error": str(exc),
                "stats": SyncStats().as_dict(),
            }

    async def _start_run(self, company: Company) -> uuid.UUID:
        async with self.session_factory() as session:
            run = IngestionRun(
                run_id=uuid.uuid4(),
                ats_provider=company.ats_provider,
                company_id=company.company_id,
                company_name=company.company_name,
                status="running",
            )
            session.add(run)
            await session.commit()
            return run.run_id

    async def _finish_run(
        self,
        run_id: uuid.UUID,
        status: str,
        stats: SyncStats | None,
        *,
        error: str | None = None,
        request_metrics: dict[str, float] | None = None,
    ) -> None:
        async with self.session_factory() as session:
            run = await session.get(IngestionRun, run_id)
            if run is None:
                return
            previous = await session.scalar(
                select(IngestionRun)
                .where(
                    IngestionRun.company_id == run.company_id,
                    IngestionRun.run_id != run_id,
                    IngestionRun.finished_at.is_not(None),
                )
                .order_by(IngestionRun.started_at.desc())
                .limit(1)
            )
            run.status = status
            run.finished_at = datetime.now(UTC)
            if stats is not None:
                run.jobs_fetched = stats.fetched
                run.jobs_inserted = stats.inserted
                run.jobs_updated = stats.updated
                run.jobs_deactivated = stats.deactivated
                run.jobs_skipped = stats.skipped
                run.errors = stats.errors
            metrics = request_metrics or {}
            run.api_requests = int(metrics.get("requests", 0))
            run.api_rate_limits = int(metrics.get("rate_limits", 0))
            run.api_failures = int(metrics.get("failures", 0))
            run.average_response_ms = float(metrics.get("average_response_ms", 0))
            if status == "failed":
                run.consecutive_failures = (
                    (previous.consecutive_failures if previous else 0) + 1
                )
            else:
                run.consecutive_failures = 0
            run.error_message = error
            await session.commit()

    @staticmethod
    def _metric_delta(
        before: dict[str, float], after: dict[str, float]
    ) -> dict[str, float]:
        return {
            key: max(0, after.get(key, 0) - before.get(key, 0))
            for key in ("requests", "rate_limits", "failures")
        } | {
            "average_response_ms": (
                (
                    after.get("total_response_ms", 0)
                    - before.get("total_response_ms", 0)
                )
                / max(
                    1,
                    after.get("requests", 0) - before.get("requests", 0),
                )
            )
        }


async def run_scheduled_sync(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    service = IngestionService(session_factory, settings)
    try:
        result = await service.sync_all()
        logger.info(
            "Scheduled ingestion finished with status=%s totals=%s",
            result.get("status"),
            result.get("totals"),
        )
    except Exception:  # noqa: BLE001 - scheduler must keep running
        logger.exception("Scheduled ingestion cycle crashed")
