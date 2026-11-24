from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_session
from app.database.repositories import get_stats
from app.schemas.job import StatsResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
async def get_dashboard_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StatsResponse:
    return await get_stats(session)
