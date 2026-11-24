from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import get_settings
from app.database.connection import get_session
from app.schemas.job import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthResponse:
    settings = get_settings()
    database_status = "connected"
    overall = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - health must report, not raise
        logger.warning("Health check database failure: %s", exc)
        database_status = "unavailable"
        overall = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall,
        database=database_status,
        version=__version__,
        environment=settings.environment,
        scheduler_enabled=settings.enable_scheduler,
        timestamp=datetime.now(UTC),
    )
