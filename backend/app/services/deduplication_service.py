from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_source import JobSource
from app.services.normalization_service import NormalizedJob


async def find_requisition_match(
    session: AsyncSession,
    company_id: uuid.UUID,
    requisition_id: str | None,
    *,
    exclude_job_id: uuid.UUID | None = None,
) -> Job | None:
    """Match a requisition identifier inside one company.

    This is level 2 of the deduplication hierarchy. It is intentionally scoped
    to a single company; a requisition number is not globally unique.
    """
    if not requisition_id:
        return None
    stmt = (
        select(Job)
        .where(
            Job.company_id == company_id,
            Job.requisition_id == requisition_id,
            Job.is_active.is_(True),
        )
        .order_by(Job.created_at.asc())
        .limit(1)
    )
    if exclude_job_id is not None:
        stmt = stmt.where(Job.job_id != exclude_job_id)
    return await session.scalar(stmt)


async def find_cross_source_candidate(
    session: AsyncSession,
    company_id: uuid.UUID,
    job: NormalizedJob,
    provider: str,
    *,
    exclude_job_id: uuid.UUID | None = None,
) -> Job | None:
    """Find a possible cross-provider duplicate without merging it.

    Level 3 of the hierarchy is deliberately conservative: exact normalized
    title + location within the same registered company, plus a different ATS
    provider. The caller stores the candidate on the new job as a review flag
    instead of silently collapsing two vacancies into one.
    """
    if not job.normalized_title:
        return None
    stmt = (
        select(Job)
        .where(
            Job.company_id == company_id,
            Job.normalized_title == job.normalized_title,
            Job.is_active.is_(True),
            Job.sources.any(JobSource.ats_provider != provider),
        )
        .order_by(Job.created_at.asc())
        .limit(1)
    )
    if job.normalized_location is None:
        stmt = stmt.where(Job.normalized_location.is_(None))
    else:
        stmt = stmt.where(Job.normalized_location == job.normalized_location)
    if exclude_job_id is not None:
        stmt = stmt.where(Job.job_id != exclude_job_id)
    return await session.scalar(stmt)
