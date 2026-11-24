from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_session
from app.database.repositories import list_sources
from app.schemas.job import SourcesResponse

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=SourcesResponse)
async def get_sources(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourcesResponse:
    return await list_sources(session)
