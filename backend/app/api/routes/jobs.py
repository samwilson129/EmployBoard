from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import SessionLocal, get_session
from app.database.repositories import (
    JobFilters,
    get_facets,
    get_job_record,
    list_jobs,
)
from app.models.enums import (
    ATS_PROVIDERS,
    EMPLOYMENT_TYPES,
    EXPERIENCE_LEVELS,
    WORKPLACE_TYPES,
)
from app.schemas.job import FacetsResponse, JobDetail, JobListResponse
from app.schemas.serializers import job_to_detail
from app.services.description_cache_service import DescriptionCacheService
from app.config import get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])

SortOption = Literal["posted_desc", "updated_desc", "company_asc"]
DateOption = Literal["all", "24h", "7d", "30d"]


def _validate_choice(value: str | None, allowed: tuple[str, ...], name: str) -> None:
    if value is not None and value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {name}. Allowed values: {', '.join(allowed)}",
        )


@router.get("", response_model=JobListResponse)
async def get_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    location: Annotated[str | None, Query(max_length=200)] = None,
    company: Annotated[str | None, Query(max_length=200)] = None,
    ats: Annotated[str | None, Query()] = None,
    employment_type: Annotated[str | None, Query()] = None,
    workplace_type: Annotated[str | None, Query()] = None,
    experience_level: Annotated[str | None, Query()] = None,
    department: Annotated[str | None, Query(max_length=200)] = None,
    date_posted: Annotated[DateOption, Query()] = "all",
    sort: Annotated[SortOption, Query()] = "posted_desc",
) -> JobListResponse:
    _validate_choice(ats, ATS_PROVIDERS, "ats")
    _validate_choice(employment_type, EMPLOYMENT_TYPES, "employment_type")
    _validate_choice(workplace_type, WORKPLACE_TYPES, "workplace_type")
    _validate_choice(experience_level, EXPERIENCE_LEVELS, "experience_level")

    posted_since = None
    if date_posted == "24h":
        posted_since = datetime.now(UTC) - timedelta(hours=24)
    elif date_posted == "7d":
        posted_since = datetime.now(UTC) - timedelta(days=7)
    elif date_posted == "30d":
        posted_since = datetime.now(UTC) - timedelta(days=30)

    filters = JobFilters(
        q=q,
        location=location,
        company=company,
        ats=ats,
        employment_type=employment_type,
        workplace_type=workplace_type,
        experience_level=experience_level,
        department=department,
        posted_since=posted_since,
        sort=sort,
        page=page,
        limit=limit,
    )
    return await list_jobs(session, filters)


@router.get("/facets", response_model=FacetsResponse)
async def get_job_facets(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FacetsResponse:
    return await get_facets(session)


@router.get("/{job_id}", response_model=JobDetail)
async def get_job_detail(
    job_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobDetail:
    job = await get_job_record(session, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    cached = await DescriptionCacheService(
        SessionLocal, get_settings()
    ).get_or_fetch(session, job)
    return job_to_detail(
        job,
        description=cached.description if cached else None,
        requirements=cached.requirements if cached else None,
        responsibilities=cached.responsibilities if cached else None,
        skills=cached.skills if cached else None,
    )
