from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.config import get_settings
from app.database.connection import SessionLocal, get_session
from app.database.repositories import list_ingestion_runs
from app.models.enums import ATS_PROVIDERS
from app.schemas.job import IngestionRunsResponse, SyncTriggerResponse
from app.services.ingestion_service import IngestionService
from app.services.description_cache_service import DescriptionCacheService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


class SyncRequest(BaseModel):
    company_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
    providers: list[str] | None = Field(default=None)


async def _run_sync_in_background(
    company_ids: list[uuid.UUID] | None, providers: list[str] | None
) -> None:
    settings = get_settings()
    service = IngestionService(SessionLocal, settings)
    try:
        result = await service.sync_all(company_ids=company_ids, providers=providers)
        logger.info("Manual ingestion finished: %s", result.get("status"))
    except Exception:  # noqa: BLE001 - background task must log, not crash
        logger.exception("Manual ingestion crashed")


@router.post(
    "/sync",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    body: SyncRequest | None = None,
    wait: Annotated[bool, Query()] = False,
):
    """Trigger ingestion for all active sources (or a filtered subset).

    Protected by ``X-Admin-Secret`` or ``Authorization: Bearer <secret>``.
    By default the work runs in the background; use ``?wait=true`` for a
    synchronous result (suitable for small subsets or local testing).
    """
    settings = get_settings()
    company_ids = body.company_ids if body else None
    providers = body.providers if body else None
    if providers:
        invalid = [provider for provider in providers if provider not in ATS_PROVIDERS]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported providers: {', '.join(invalid)}",
            )

    started_at = datetime.now(UTC)
    if wait:
        service = IngestionService(SessionLocal, settings)
        result = await service.sync_all(company_ids=company_ids, providers=providers)
        return result

    background_tasks.add_task(_run_sync_in_background, company_ids, providers)
    return SyncTriggerResponse(
        status="started",
        message="Ingestion started in the background. Inspect /api/admin/sync/runs for results.",
        started_at=started_at,
    )


@router.get(
    "/sync/runs",
    response_model=IngestionRunsResponse,
    dependencies=[Depends(require_admin)],
)
async def get_sync_runs(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> IngestionRunsResponse:
    return await list_ingestion_runs(session, limit)


@router.get(
    "/cache",
    dependencies=[Depends(require_admin)],
)
async def get_cache_metrics(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, int | float]:
    return await DescriptionCacheService(SessionLocal, get_settings()).metrics(session)
