from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.adapters.base import AdapterJob
from app.models.company import Company
from app.models.enums import EmploymentType, ExperienceLevel, WorkplaceType
from app.utils.text import (
    clean_url,
    normalize_currency,
    normalize_location,
    normalize_title,
    normalize_whitespace,
    parse_decimal,
    unescape_html,
)


class NormalizationError(ValueError):
    pass


@dataclass(slots=True)
class NormalizedJob:
    external_job_id: str
    title: str
    normalized_title: str
    application_url: str
    normalized_location: str | None = None
    original_job_url: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    workplace_type: str | None = None
    experience_level: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    description: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    skills: list[str] | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    requisition_id: str | None = None
    source_payload: dict[str, Any] = field(default_factory=dict)
    detail_fetched: bool = False


def _key(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower().replace("&", " and ")
    key = re.sub(r"[^a-z0-9]+", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key or None


_EMPLOYMENT_MAP: dict[str, str] = {
    "full time": EmploymentType.FULL_TIME.value,
    "fulltime": EmploymentType.FULL_TIME.value,
    "full time employment": EmploymentType.FULL_TIME.value,
    "permanent": EmploymentType.FULL_TIME.value,
    "regular": EmploymentType.FULL_TIME.value,
    "regular full time": EmploymentType.FULL_TIME.value,
    "full time regular": EmploymentType.FULL_TIME.value,
    "fulltime permanent": EmploymentType.FULL_TIME.value,
    "permanent full time": EmploymentType.FULL_TIME.value,
    "part time": EmploymentType.PART_TIME.value,
    "parttime": EmploymentType.PART_TIME.value,
    "part time employment": EmploymentType.PART_TIME.value,
    "contract": EmploymentType.CONTRACT.value,
    "contractor": EmploymentType.CONTRACT.value,
    "fixed term": EmploymentType.CONTRACT.value,
    "fixed term contract": EmploymentType.CONTRACT.value,
    "fulltime fixed term": EmploymentType.CONTRACT.value,
    "freelance full time": EmploymentType.CONTRACT.value,
    "freelance": EmploymentType.CONTRACT.value,
    "b2b": EmploymentType.CONTRACT.value,
    "intern": EmploymentType.INTERNSHIP.value,
    "internship": EmploymentType.INTERNSHIP.value,
    "trainee": EmploymentType.INTERNSHIP.value,
    "apprentice": EmploymentType.INTERNSHIP.value,
    "working student": EmploymentType.INTERNSHIP.value,
    "summer intern": EmploymentType.INTERNSHIP.value,
    "temporary": EmploymentType.TEMPORARY.value,
    "temp": EmploymentType.TEMPORARY.value,
    "seasonal": EmploymentType.TEMPORARY.value,
    "casual": EmploymentType.TEMPORARY.value,
    "interim": EmploymentType.TEMPORARY.value,
    "other": EmploymentType.OTHER.value,
}

_WORKPLACE_MAP: dict[str, str] = {
    "remote": WorkplaceType.REMOTE.value,
    "fully remote": WorkplaceType.REMOTE.value,
    "remote first": WorkplaceType.REMOTE.value,
    "work from home": WorkplaceType.REMOTE.value,
    "wfh": WorkplaceType.REMOTE.value,
    "distributed": WorkplaceType.REMOTE.value,
    "hybrid": WorkplaceType.HYBRID.value,
    "hybrid remote": WorkplaceType.HYBRID.value,
    "flexible hybrid": WorkplaceType.HYBRID.value,
    "on site": WorkplaceType.ON_SITE.value,
    "onsite": WorkplaceType.ON_SITE.value,
    "office": WorkplaceType.ON_SITE.value,
    "in office": WorkplaceType.ON_SITE.value,
    "in person": WorkplaceType.ON_SITE.value,
    "unknown": WorkplaceType.UNKNOWN.value,
}

_EXPERIENCE_MAP: dict[str, str] = {
    "entry": ExperienceLevel.ENTRY.value,
    "entry level": ExperienceLevel.ENTRY.value,
    "intern": ExperienceLevel.ENTRY.value,
    "internship": ExperienceLevel.ENTRY.value,
    "graduate": ExperienceLevel.ENTRY.value,
    "junior": ExperienceLevel.JUNIOR.value,
    "jr": ExperienceLevel.JUNIOR.value,
    "associate": ExperienceLevel.JUNIOR.value,
    "mid": ExperienceLevel.MID.value,
    "mid level": ExperienceLevel.MID.value,
    "mid senior": ExperienceLevel.MID.value,
    "mid senior level": ExperienceLevel.MID.value,
    "intermediate": ExperienceLevel.MID.value,
    "professional": ExperienceLevel.MID.value,
    "experienced": ExperienceLevel.MID.value,
    "student": ExperienceLevel.ENTRY.value,
    "senior": ExperienceLevel.SENIOR.value,
    "senior level": ExperienceLevel.SENIOR.value,
    "sr": ExperienceLevel.SENIOR.value,
    "lead": ExperienceLevel.LEAD.value,
    "principal": ExperienceLevel.LEAD.value,
    "staff": ExperienceLevel.LEAD.value,
    "manager": ExperienceLevel.LEAD.value,
    "executive": ExperienceLevel.EXECUTIVE.value,
    "director": ExperienceLevel.EXECUTIVE.value,
    "vp": ExperienceLevel.EXECUTIVE.value,
    "vice president": ExperienceLevel.EXECUTIVE.value,
    "c level": ExperienceLevel.EXECUTIVE.value,
    "chief": ExperienceLevel.EXECUTIVE.value,
    "unknown": ExperienceLevel.UNKNOWN.value,
    "not applicable": ExperienceLevel.UNKNOWN.value,
}

_INTERVAL_MAP = {
    "year": "year",
    "yearly": "year",
    "annual": "year",
    "annually": "year",
    "1 year": "year",
    "month": "month",
    "monthly": "month",
    "1 month": "month",
    "week": "week",
    "weekly": "week",
    "1 week": "week",
    "day": "day",
    "daily": "day",
    "1 day": "day",
    "hour": "hour",
    "hourly": "hour",
    "1 hour": "hour",
}


def normalize_employment_type(value: str | None) -> str | None:
    key = _key(value)
    if key is None:
        return None
    return _EMPLOYMENT_MAP.get(key, EmploymentType.OTHER.value)


def normalize_workplace_type(value: str | None) -> str | None:
    key = _key(value)
    if key is None:
        return None
    return _WORKPLACE_MAP.get(key, WorkplaceType.UNKNOWN.value)


def normalize_experience_level(value: str | None) -> str | None:
    key = _key(value)
    if key is None:
        return None
    return _EXPERIENCE_MAP.get(key, ExperienceLevel.UNKNOWN.value)


def normalize_salary_interval(value: str | None) -> str | None:
    key = _key(value)
    if key is None:
        return None
    return _INTERVAL_MAP.get(key, key[:32])


def _clip(value: str | None, length: int) -> str | None:
    if value is None:
        return None
    return value[:length]


def _clean_skills(values: Any) -> list[str] | None:
    if not isinstance(values, list):
        return None
    seen: set[str] = set()
    skills: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        skill = normalize_whitespace(value)
        if not skill:
            continue
        key = skill.lower()
        if key in seen:
            continue
        seen.add(key)
        skills.append(skill[:80])
        if len(skills) >= 50:
            break
    return skills or None


def normalize_adapter_job(job: AdapterJob, company: Company) -> NormalizedJob:
    title = normalize_whitespace(job.title)
    if not title:
        raise NormalizationError("missing title")

    application_url = clean_url(job.application_url)
    if not application_url:
        raise NormalizationError("missing or invalid application_url")

    external_job_id = str(job.external_job_id).strip()
    if not external_job_id:
        raise NormalizationError("missing external_job_id")
    if len(external_job_id) > 255:
        raise NormalizationError("external_job_id is too long")

    location = normalize_whitespace(job.location)
    department = normalize_whitespace(job.department)
    requisition_id = normalize_whitespace(job.requisition_id)
    original_job_url = clean_url(job.original_job_url) or application_url

    salary_min = parse_decimal(job.salary_min)
    salary_max = parse_decimal(job.salary_max)
    if salary_min is not None and salary_min < 0:
        salary_min = None
    if salary_max is not None and salary_max < 0:
        salary_max = None
    if (
        salary_min is not None
        and salary_max is not None
        and salary_min > salary_max
    ):
        salary_min = None
        salary_max = None
    currency = normalize_currency(job.salary_currency)
    if salary_min is None and salary_max is None:
        currency = None

    description = job.description_html
    if description is not None:
        description = description.strip() or None
    # Greenhouse HTML is escaped at the source; other adapters already return
    # real markup. Decoding here is idempotent for markup without entities.
    if description and "&lt;" in description and "<" not in description:
        description = unescape_html(description)

    return NormalizedJob(
        external_job_id=external_job_id,
        title=_clip(title, 500) or title,
        normalized_title=normalize_title(title)[:500],
        application_url=application_url,
        normalized_location=normalize_location(location),
        original_job_url=original_job_url,
        department=_clip(department, 255),
        location=_clip(location, 500),
        employment_type=normalize_employment_type(job.employment_type_raw),
        workplace_type=normalize_workplace_type(job.workplace_type_raw),
        experience_level=normalize_experience_level(job.experience_level_raw),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        salary_interval=normalize_salary_interval(job.salary_interval),
        description=description,
        requirements=job.requirements_html.strip() if job.requirements_html else None,
        responsibilities=(
            job.responsibilities_html.strip() if job.responsibilities_html else None
        ),
        skills=_clean_skills(job.skills),
        posted_at=job.posted_at,
        expires_at=job.expires_at,
        requisition_id=_clip(requisition_id, 255),
        source_payload=job.source_payload,
        detail_fetched=job.detail_fetched,
    )
