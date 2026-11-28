from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CompanyBase(BaseModel):
    company_id: uuid.UUID
    company_name: str
    company_slug: str
    company_logo_url: str | None = None
    company_website: str | None = None
    careers_url: str | None = None
    ats_provider: str
    board_identifier: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CompanyOut(CompanyBase):
    active_job_count: int = 0
    total_job_count: int = 0
    last_successful_sync: datetime | None = None
    verification_note: str | None = None


class CompanySummary(BaseModel):
    company_id: uuid.UUID
    company_name: str
    company_logo_url: str | None = None
    company_website: str | None = None


class CompaniesResponse(BaseModel):
    items: list[CompanyOut]
    total: int


class SourceProviderOut(BaseModel):
    provider: str
    display_name: str
    documentation_url: str
    is_integrated: bool
    company_count: int
    active_job_count: int
    last_successful_sync: datetime | None = None
    status: str = "not_configured"


class SourcesResponse(BaseModel):
    items: list[SourceProviderOut]
    total_integrated: int
    generated_at: datetime


class FacetCount(BaseModel):
    value: str
    label: str
    count: int


class FacetsResponse(BaseModel):
    locations: list[FacetCount]
    departments: list[FacetCount]
    employment_types: list[FacetCount]
    workplace_types: list[FacetCount]
    experience_levels: list[FacetCount]
    ats_providers: list[FacetCount]
    total_active_jobs: int


class JobCompany(BaseModel):
    company_id: uuid.UUID
    company_name: str
    company_logo_url: str | None = None
    company_website: str | None = None
    careers_url: str | None = None


class JobSourceRef(BaseModel):
    source_id: uuid.UUID
    ats_provider: str
    external_job_id: str
    original_job_url: str | None = None
    fetched_at: datetime
    last_verified_at: datetime | None = None


class JobListItem(BaseModel):
    job_id: uuid.UUID
    title: str
    company: JobCompany
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    workplace_type: str | None = None
    experience_level: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    description_snippet: str | None = None
    posted_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime
    last_synced_at: datetime | None = None
    application_url: str
    ats_sources: list[str] = Field(default_factory=list)
    primary_ats_provider: str | None = None
    is_active: bool


class JobDetail(JobListItem):
    description: str | None = None
    description_available: bool = False
    requirements: str | None = None
    responsibilities: str | None = None
    skills: list[str] | None = None
    expires_at: datetime | None = None
    requisition_id: str | None = None
    sources: list[JobSourceRef] = Field(default_factory=list)
    duplicate_of_job_id: uuid.UUID | None = None


class JobListResponse(BaseModel):
    items: list[JobListItem]
    total: int
    page: int
    limit: int
    pages: int
    sort: str


class StatsResponse(BaseModel):
    total_active_jobs: int
    total_companies: int
    active_companies: int
    integrated_sources: int
    total_job_sources: int
    last_successful_sync: datetime | None = None
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    provider_job_counts: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime


class IngestionRunOut(BaseModel):
    run_id: uuid.UUID
    ats_provider: str
    company_id: uuid.UUID | None = None
    company_name: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    jobs_fetched: int
    jobs_inserted: int
    jobs_updated: int
    jobs_deactivated: int
    jobs_skipped: int
    api_requests: int = 0
    api_rate_limits: int = 0
    api_failures: int = 0
    average_response_ms: float = 0
    consecutive_failures: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class IngestionRunsResponse(BaseModel):
    items: list[IngestionRunOut]
    total: int


class SyncTriggerResponse(BaseModel):
    status: str
    message: str
    started_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
    environment: str
    scheduler_enabled: bool
    timestamp: datetime
