from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_session
from app.database.repositories import list_companies
from app.schemas.job import CompaniesResponse

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=CompaniesResponse)
async def get_companies(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CompaniesResponse:
    return await list_companies(session)
