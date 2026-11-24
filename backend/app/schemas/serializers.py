from __future__ import annotations

from app.models.company import Company
from app.models.job import Job
from app.schemas.job import (
    CompanyOut,
    JobCompany,
    JobDetail,
    JobListItem,
    JobSourceRef,
)
from app.utils.text import make_snippet


def job_company(company: Company) -> JobCompany:
    return JobCompany(
        company_id=company.company_id,
        company_name=company.company_name,
        company_logo_url=company.company_logo_url,
        company_website=company.company_website,
        careers_url=company.careers_url,
    )


def source_refs(job: Job) -> list[JobSourceRef]:
    return [
        JobSourceRef(
            source_id=source.source_id,
            ats_provider=source.ats_provider,
            external_job_id=source.external_job_id,
            original_job_url=source.original_job_url,
            fetched_at=source.fetched_at,
            last_verified_at=source.last_verified_at,
        )
        for source in sorted(job.sources, key=lambda item: item.ats_provider)
    ]


def _primary_provider(job: Job) -> str | None:
    if not job.sources:
        return None
    latest = max(
        job.sources,
        key=lambda source: source.last_verified_at or source.fetched_at,
    )
    return latest.ats_provider


def job_to_list_item(job: Job) -> JobListItem:
    return JobListItem(
        job_id=job.job_id,
        title=job.title,
        company=job_company(job.company),
        department=job.department,
        location=job.location,
        employment_type=job.employment_type,
        workplace_type=job.workplace_type,
        experience_level=job.experience_level,
        salary_min=float(job.salary_min) if job.salary_min is not None else None,
        salary_max=float(job.salary_max) if job.salary_max is not None else None,
        salary_currency=job.salary_currency,
        salary_interval=job.salary_interval,
        description_snippet=make_snippet(job.description),
        posted_at=job.posted_at,
        first_seen_at=job.first_seen_at,
        last_seen_at=job.last_seen_at,
        updated_at=job.updated_at,
        last_synced_at=job.last_verified_at,
        application_url=job.application_url,
        ats_sources=job.source_providers,
        primary_ats_provider=_primary_provider(job),
        is_active=job.is_active,
    )


def job_to_detail(job: Job) -> JobDetail:
    item = job_to_list_item(job)
    return JobDetail(
        **item.model_dump(),
        description=job.description,
        requirements=job.requirements,
        responsibilities=job.responsibilities,
        skills=job.skills,
        expires_at=job.expires_at,
        requisition_id=job.requisition_id,
        sources=source_refs(job),
        duplicate_of_job_id=job.duplicate_of_job_id,
    )


def company_out(
    company: Company,
    *,
    active_job_count: int = 0,
    total_job_count: int = 0,
    last_successful_sync=None,
) -> CompanyOut:
    return CompanyOut(
        company_id=company.company_id,
        company_name=company.company_name,
        company_slug=company.company_slug,
        company_logo_url=company.company_logo_url,
        company_website=company.company_website,
        careers_url=company.careers_url,
        ats_provider=company.ats_provider,
        board_identifier=company.board_identifier,
        is_active=company.is_active,
        active_job_count=active_job_count,
        total_job_count=total_job_count,
        last_successful_sync=last_successful_sync,
        verification_note=(company.config or {}).get("verification_note"),
    )
