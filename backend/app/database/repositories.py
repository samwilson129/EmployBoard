from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.company import Company
from app.models.enums import (
    EMPLOYMENT_TYPES,
    EXPERIENCE_LEVELS,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_DOCS,
    WORKPLACE_TYPES,
)
from app.models.ingestion_run import IngestionRun
from app.models.job import Job
from app.models.job_source import JobSource
from app.schemas.job import (
    CompaniesResponse,
    FacetCount,
    FacetsResponse,
    IngestionRunOut,
    IngestionRunsResponse,
    JobListResponse,
    SourcesResponse,
    SourceProviderOut,
    StatsResponse,
)
from app.schemas.serializers import company_out, job_to_detail, job_to_list_item


@dataclass(slots=True)
class JobFilters:
    q: str | None = None
    location: str | None = None
    company: str | None = None
    ats: str | None = None
    employment_type: str | None = None
    workplace_type: str | None = None
    experience_level: str | None = None
    department: str | None = None
    posted_since: datetime | None = None
    sort: str = "posted_desc"
    page: int = 1
    limit: int = 20
    include_inactive: bool = False


def _company_id_or_name(value: str) -> Any:
    try:
        return Job.company_id == uuid.UUID(value)
    except ValueError:
        return Company.company_name.ilike(f"%{value.strip()}%")


def _sort_clause(sort: str):
    if sort == "updated_desc":
        return (Job.updated_at.desc(), Job.job_id.desc())
    if sort == "company_asc":
        return (
            Company.company_name.asc(),
            Job.posted_at.desc().nullslast(),
            Job.job_id.desc(),
        )
    return (Job.posted_at.desc().nullslast(), Job.first_seen_at.desc(), Job.job_id.desc())


async def list_jobs(session: AsyncSession, filters: JobFilters) -> JobListResponse:
    conditions = []
    if not filters.include_inactive:
        conditions.append(Job.is_active.is_(True))
    if filters.q:
        query = filters.q.strip()
        if query:
            pattern = f"%{query}%"
            conditions.append(
                or_(
                    Job.title.ilike(pattern),
                    Company.company_name.ilike(pattern),
                    Job.location.ilike(pattern),
                    Job.department.ilike(pattern),
                    cast(Job.skills, Text).ilike(pattern),
                )
            )
    if filters.location:
        conditions.append(Job.location.ilike(f"%{filters.location.strip()}%"))
    if filters.company:
        conditions.append(_company_id_or_name(filters.company))
    if filters.ats:
        conditions.append(Job.sources.any(JobSource.ats_provider == filters.ats))
    if filters.employment_type:
        conditions.append(Job.employment_type == filters.employment_type)
    if filters.workplace_type:
        conditions.append(Job.workplace_type == filters.workplace_type)
    if filters.experience_level:
        conditions.append(Job.experience_level == filters.experience_level)
    if filters.department:
        conditions.append(Job.department == filters.department)
    if filters.posted_since:
        conditions.append(Job.posted_at >= filters.posted_since)

    count_stmt = (
        select(func.count(Job.job_id))
        .select_from(Job)
        .join(Company, Company.company_id == Job.company_id)
        .where(*conditions)
    )
    total = int(await session.scalar(count_stmt) or 0)

    limit = max(1, min(filters.limit, 100))
    page = max(1, filters.page)
    pages = max(1, math.ceil(total / limit)) if total else 0
    if pages and page > pages:
        page = pages

    stmt = (
        select(Job)
        .join(Company, Company.company_id == Job.company_id)
        .where(*conditions)
        .options(selectinload(Job.company), selectinload(Job.sources))
        .order_by(*_sort_clause(filters.sort))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    jobs = (await session.scalars(stmt)).all()
    return JobListResponse(
        items=[job_to_list_item(job) for job in jobs],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        sort=filters.sort,
    )


async def get_job(session: AsyncSession, job_id: uuid.UUID):
    stmt = (
        select(Job)
        .where(Job.job_id == job_id)
        .options(selectinload(Job.company), selectinload(Job.sources))
    )
    job = await session.scalar(stmt)
    return job_to_detail(job) if job is not None else None


async def get_job_record(session: AsyncSession, job_id: uuid.UUID) -> Job | None:
    stmt = (
        select(Job)
        .where(Job.job_id == job_id)
        .options(selectinload(Job.company), selectinload(Job.sources))
    )
    return await session.scalar(stmt)


def _ordered_facets(
    rows: list[tuple[str, int]],
    preferred_order: tuple[str, ...] | None = None,
) -> list[FacetCount]:
    counts = {value: count for value, count in rows if value}
    if preferred_order:
        ordered = [value for value in preferred_order if value in counts]
        ordered.extend(sorted(value for value in counts if value not in preferred_order))
    else:
        ordered = sorted(counts)
    return [
        FacetCount(value=value, label=value, count=counts[value]) for value in ordered
    ]


async def get_facets(session: AsyncSession) -> FacetsResponse:
    total_active = int(
        await session.scalar(
            select(func.count(Job.job_id)).where(Job.is_active.is_(True))
        )
        or 0
    )

    async def grouped(column, limit: int = 200) -> list[tuple[str, int]]:
        stmt = (
            select(column, func.count(Job.job_id))
            .where(Job.is_active.is_(True), column.is_not(None), column != "")
            .group_by(column)
            .order_by(func.count(Job.job_id).desc(), column.asc())
            .limit(limit)
        )
        return [(str(value), int(count)) for value, count in (await session.execute(stmt)).all()]

    locations = await grouped(Job.location)
    departments = await grouped(Job.department)
    employment = await grouped(Job.employment_type)
    workplace = await grouped(Job.workplace_type)
    experience = await grouped(Job.experience_level)

    ats_stmt = (
        select(JobSource.ats_provider, func.count(func.distinct(Job.job_id)))
        .join(Job, Job.job_id == JobSource.job_id)
        .where(Job.is_active.is_(True))
        .group_by(JobSource.ats_provider)
        .order_by(func.count(func.distinct(Job.job_id)).desc())
    )
    ats_rows = [
        (provider, int(count))
        for provider, count in (await session.execute(ats_stmt)).all()
    ]
    ats_facets = [
        FacetCount(
            value=provider,
            label=PROVIDER_DISPLAY_NAMES.get(provider, provider),
            count=count,
        )
        for provider, count in ats_rows
    ]

    return FacetsResponse(
        locations=_ordered_facets(locations),
        departments=_ordered_facets(departments),
        employment_types=_ordered_facets(employment, EMPLOYMENT_TYPES),
        workplace_types=_ordered_facets(workplace, WORKPLACE_TYPES),
        experience_levels=_ordered_facets(experience, EXPERIENCE_LEVELS),
        ats_providers=ats_facets,
        total_active_jobs=total_active,
    )


async def list_companies(session: AsyncSession) -> CompaniesResponse:
    companies = list(
        (
            await session.scalars(
                select(Company)
                .where(Company.jobs.any(Job.is_active.is_(True)))
                .order_by(Company.company_name.asc())
            )
        ).all()
    )
    active_counts = {
        company_id: int(count)
        for company_id, count in (
            await session.execute(
                select(Job.company_id, func.count(Job.job_id))
                .where(Job.is_active.is_(True))
                .group_by(Job.company_id)
            )
        ).all()
    }
    total_counts = {
        company_id: int(count)
        for company_id, count in (
            await session.execute(
                select(Job.company_id, func.count(Job.job_id)).group_by(Job.company_id)
            )
        ).all()
    }
    last_syncs = {
        company_id: finished_at
        for company_id, finished_at in (
            await session.execute(
                select(
                    IngestionRun.company_id, func.max(IngestionRun.finished_at)
                )
                .where(
                    IngestionRun.status.in_(("success", "partial")),
                    IngestionRun.company_id.is_not(None),
                )
                .group_by(IngestionRun.company_id)
            )
        ).all()
    }

    items = [
        company_out(
            company,
            active_job_count=active_counts.get(company.company_id, 0),
            total_job_count=total_counts.get(company.company_id, 0),
            last_successful_sync=last_syncs.get(company.company_id),
        )
        for company in companies
    ]
    return CompaniesResponse(items=items, total=len(items))


async def list_sources(session: AsyncSession) -> SourcesResponse:
    company_counts = {
        provider: int(count)
        for provider, count in (
            await session.execute(
                select(Company.ats_provider, func.count(Company.company_id))
                .where(Company.is_active.is_(True))
                .group_by(Company.ats_provider)
            )
        ).all()
    }
    job_counts = {
        provider: int(count)
        for provider, count in (
            await session.execute(
                select(
                    JobSource.ats_provider, func.count(func.distinct(Job.job_id))
                )
                .join(Job, Job.job_id == JobSource.job_id)
                .where(Job.is_active.is_(True))
                .group_by(JobSource.ats_provider)
            )
        ).all()
    }
    last_syncs = {
        provider: finished_at
        for provider, finished_at in (
            await session.execute(
                select(
                    IngestionRun.ats_provider, func.max(IngestionRun.finished_at)
                )
                .where(IngestionRun.status.in_(("success", "partial")))
                .group_by(IngestionRun.ats_provider)
            )
        ).all()
    }
    last_statuses = {
        provider: status
        for provider, status in (
            await session.execute(
                select(IngestionRun.ats_provider, IngestionRun.status)
                .distinct(IngestionRun.ats_provider)
                .order_by(IngestionRun.ats_provider, IngestionRun.started_at.desc())
            )
        ).all()
    }

    items = []
    for provider, display_name in PROVIDER_DISPLAY_NAMES.items():
        company_count = company_counts.get(provider, 0)
        status = "not_configured"
        if company_count:
            latest = last_statuses.get(provider)
            if latest is None:
                status = "pending"
            elif latest == "failed":
                status = "degraded"
            else:
                status = "operational"
        items.append(
            SourceProviderOut(
                provider=provider,
                display_name=display_name,
                documentation_url=PROVIDER_DOCS[provider],
                is_integrated=company_count > 0,
                company_count=company_count,
                active_job_count=job_counts.get(provider, 0),
                last_successful_sync=last_syncs.get(provider),
                status=status,
            )
        )
    return SourcesResponse(
        items=items,
        total_integrated=sum(1 for item in items if item.is_integrated),
        generated_at=datetime.now(UTC),
    )


async def get_stats(session: AsyncSession) -> StatsResponse:
    total_active_jobs = int(
        await session.scalar(
            select(func.count(Job.job_id)).where(Job.is_active.is_(True))
        )
        or 0
    )
    total_companies = int(
        await session.scalar(select(func.count(Company.company_id))) or 0
    )
    active_companies = int(
        await session.scalar(
            select(func.count(Company.company_id)).where(Company.is_active.is_(True))
        )
        or 0
    )
    integrated_sources = int(
        await session.scalar(
            select(func.count(func.distinct(Company.ats_provider))).where(
                Company.is_active.is_(True)
            )
        )
        or 0
    )
    total_job_sources = int(
        await session.scalar(select(func.count(JobSource.source_id))) or 0
    )
    last_successful_sync = await session.scalar(
        select(func.max(IngestionRun.finished_at)).where(
            IngestionRun.status.in_(("success", "partial")),
            IngestionRun.jobs_fetched > 0,
        )
    )
    last_run = (
        await session.execute(
            select(IngestionRun.started_at, IngestionRun.status)
            .order_by(IngestionRun.started_at.desc())
            .limit(1)
        )
    ).first()
    provider_rows = (
        await session.execute(
            select(JobSource.ats_provider, func.count(func.distinct(Job.job_id)))
            .join(Job, Job.job_id == JobSource.job_id)
            .where(Job.is_active.is_(True))
            .group_by(JobSource.ats_provider)
        )
    ).all()
    return StatsResponse(
        total_active_jobs=total_active_jobs,
        total_companies=total_companies,
        active_companies=active_companies,
        integrated_sources=integrated_sources,
        total_job_sources=total_job_sources,
        last_successful_sync=last_successful_sync,
        last_run_at=last_run[0] if last_run else None,
        last_run_status=last_run[1] if last_run else None,
        provider_job_counts={
            str(provider): int(count) for provider, count in provider_rows
        },
        generated_at=datetime.now(UTC),
    )


async def list_ingestion_runs(
    session: AsyncSession, limit: int = 20
) -> IngestionRunsResponse:
    limit = max(1, min(limit, 100))
    total = int(
        await session.scalar(select(func.count(IngestionRun.run_id))) or 0
    )
    runs = (
        await session.scalars(
            select(IngestionRun)
            .order_by(IngestionRun.started_at.desc())
            .limit(limit)
        )
    ).all()
    return IngestionRunsResponse(
        items=[IngestionRunOut.model_validate(run) for run in runs],
        total=total,
    )
