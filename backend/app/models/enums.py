"""Canonical enum values shared by models, schemas and normalization."""

from __future__ import annotations

from enum import StrEnum


class ATSProvider(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"


class EmploymentType(StrEnum):
    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    CONTRACT = "Contract"
    INTERNSHIP = "Internship"
    TEMPORARY = "Temporary"
    OTHER = "Other"


class WorkplaceType(StrEnum):
    REMOTE = "Remote"
    HYBRID = "Hybrid"
    ON_SITE = "On-site"
    UNKNOWN = "Unknown"


class ExperienceLevel(StrEnum):
    ENTRY = "Entry"
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"
    LEAD = "Lead"
    EXECUTIVE = "Executive"
    UNKNOWN = "Unknown"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


ATS_PROVIDERS: tuple[str, ...] = tuple(provider.value for provider in ATSProvider)
EMPLOYMENT_TYPES: tuple[str, ...] = tuple(value.value for value in EmploymentType)
WORKPLACE_TYPES: tuple[str, ...] = tuple(value.value for value in WorkplaceType)
EXPERIENCE_LEVELS: tuple[str, ...] = tuple(value.value for value in ExperienceLevel)
RUN_STATUSES: tuple[str, ...] = tuple(value.value for value in RunStatus)

PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    ATSProvider.GREENHOUSE.value: "Greenhouse",
    ATSProvider.LEVER.value: "Lever",
    ATSProvider.ASHBY.value: "Ashby",
    ATSProvider.SMARTRECRUITERS.value: "SmartRecruiters",
}

PROVIDER_DOCS: dict[str, str] = {
    ATSProvider.GREENHOUSE.value: "https://developers.greenhouse.io/job-board.html",
    ATSProvider.LEVER.value: "https://github.com/lever/postings-api",
    ATSProvider.ASHBY.value: "https://developers.ashbyhq.com/docs/public-job-posting-api",
    ATSProvider.SMARTRECRUITERS.value: "https://dev.smartrecruiters.com/",
}
