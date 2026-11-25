from __future__ import annotations

import re
from typing import Any

from app.adapters.base import ATSAdapter, AdapterJob
from app.models.company import Company
from app.models.enums import ATSProvider
from app.utils.text import (
    clean_requisition_id,
    clean_url,
    normalize_whitespace,
    parse_datetime,
)

_SPACE_AROUND_COMMA = re.compile(r"\s*,\s*")


def _location_from(raw: dict[str, Any]) -> str | None:
    location = raw.get("location") or {}
    if not isinstance(location, dict):
        return None
    full = normalize_whitespace(location.get("fullLocation"))
    if full:
        parts = [part.strip() for part in _SPACE_AROUND_COMMA.split(full)]
        return ", ".join(part for part in parts if part) or None
    parts = [
        normalize_whitespace(location.get("city")),
        normalize_whitespace(location.get("region")),
        normalize_whitespace(location.get("country")),
    ]
    joined = ", ".join(part for part in parts if part)
    return joined or None


def _workplace_from(raw: dict[str, Any]) -> str | None:
    location = raw.get("location") or {}
    if not isinstance(location, dict):
        return None
    if location.get("remote") is True:
        return "Remote"
    if location.get("hybrid") is True:
        return "Hybrid"
    if "remote" in location and "hybrid" in location:
        if location.get("remote") is False and location.get("hybrid") is False:
            return "On-site"
    return None


def _label(value: Any) -> str | None:
    if isinstance(value, dict):
        return normalize_whitespace(value.get("label") or value.get("name"))
    if isinstance(value, str):
        return normalize_whitespace(value)
    return None


class SmartRecruitersAdapter(ATSAdapter):
    provider = ATSProvider.SMARTRECRUITERS.value
    display_name = "SmartRecruiters"
    documentation_url = "https://dev.smartrecruiters.com/"
    supports_detail = True

    async def fetch_jobs(self, company: Company) -> list[AdapterJob]:
        base = (
            "https://api.smartrecruiters.com/v1/companies/"
            f"{company.board_identifier}/postings"
        )
        sync_limit = company.config.get("sync_limit") if company.config else None
        sync_limit = int(sync_limit) if isinstance(sync_limit, (int, float)) else None

        jobs: list[AdapterJob] = []
        offset = 0
        page_size = 100
        while True:
            payload = await self._get(
                base, params={"limit": page_size, "offset": offset}
            )
            if not isinstance(payload, dict) or not isinstance(
                payload.get("content"), list
            ):
                raise ValueError("SmartRecruiters response did not contain content")
            content = payload["content"]
            for raw in content:
                if not isinstance(raw, dict):
                    continue
                parsed = self._parse_listing(raw, company)
                if parsed is not None:
                    jobs.append(parsed)
                if sync_limit is not None and len(jobs) >= sync_limit:
                    return jobs
            if not content:
                break
            offset += len(content)
            total = payload.get("totalFound")
            if isinstance(total, int) and offset >= total:
                break
            if len(content) < page_size:
                break
            if offset > 100_000:
                break
        return jobs

    async def fetch_detail(
        self,
        company: Company,
        external_job_id: str,
        existing_payload: dict[str, Any] | None = None,
    ) -> AdapterJob | None:
        url = (
            "https://api.smartrecruiters.com/v1/companies/"
            f"{company.board_identifier}/postings/{external_job_id}"
        )
        payload = await self._get(url)
        if not isinstance(payload, dict):
            return None
        job = self._parse_detail(payload, company)
        if job is not None:
            job.source_payload = {
                "listing": existing_payload or {},
                "detail": payload,
            }
        return job

    def parse_jobs(self, payload: Any, company: Company) -> list[AdapterJob]:
        if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
            raise ValueError("SmartRecruiters response did not contain content")
        return [
            job
            for raw in payload["content"]
            if isinstance(raw, dict) and (job := self._parse_listing(raw, company))
        ]

    def _parse_listing(
        self, raw: dict[str, Any], company: Company
    ) -> AdapterJob | None:
        external_id = raw.get("id")
        title = normalize_whitespace(raw.get("name"))
        if external_id in (None, "") or not title:
            return None
        posting_url = (
            f"https://jobs.smartrecruiters.com/{company.board_identifier}/{external_id}"
        )
        requisition_id = clean_requisition_id(raw.get("refNumber"))

        return AdapterJob(
            external_job_id=str(external_id),
            title=title,
            application_url=posting_url,
            original_job_url=posting_url,
            department=_label(raw.get("department")) or _label(raw.get("function")),
            location=_location_from(raw),
            employment_type_raw=_label(raw.get("typeOfEmployment")),
            workplace_type_raw=_workplace_from(raw),
            experience_level_raw=_label(raw.get("experienceLevel")),
            posted_at=parse_datetime(raw.get("releasedDate")),
            requisition_id=requisition_id,
            source_payload=raw,
        )

    def _parse_detail(
        self, raw: dict[str, Any], company: Company
    ) -> AdapterJob | None:
        external_id = raw.get("id")
        title = normalize_whitespace(raw.get("name"))
        if external_id in (None, "") or not title:
            return None

        posting_url = clean_url(raw.get("postingUrl"))
        apply_url = clean_url(raw.get("applyUrl")) or posting_url
        if not apply_url:
            apply_url = (
                "https://jobs.smartrecruiters.com/"
                f"{company.board_identifier}/{external_id}"
            )

        sections = ((raw.get("jobAd") or {}).get("sections")) or {}
        description_parts: list[str] = []
        responsibilities: list[str] = []
        requirements: list[str] = []
        if isinstance(sections, dict):
            for key in (
                "companyDescription",
                "jobDescription",
                "qualifications",
                "additionalInformation",
            ):
                section = sections.get(key)
                if not isinstance(section, dict):
                    continue
                text = section.get("text")
                if not isinstance(text, str) or not text.strip():
                    continue
                heading = normalize_whitespace(section.get("title"))
                description_parts.append(
                    f"<h3>{heading}</h3>{text.strip()}"
                    if heading
                    else text.strip()
                )
                if key == "qualifications":
                    requirements.append(text.strip())
                elif key == "jobDescription":
                    responsibilities.append(text.strip())

        requisition_id = clean_requisition_id(raw.get("refNumber"))

        return AdapterJob(
            external_job_id=str(external_id),
            title=title,
            application_url=apply_url,
            original_job_url=posting_url,
            department=_label(raw.get("department")) or _label(raw.get("function")),
            location=_location_from(raw),
            employment_type_raw=_label(raw.get("typeOfEmployment")),
            workplace_type_raw=_workplace_from(raw),
            experience_level_raw=_label(raw.get("experienceLevel")),
            description_html="\n".join(description_parts) or None,
            requirements_html="\n".join(requirements) or None,
            responsibilities_html="\n".join(responsibilities) or None,
            posted_at=parse_datetime(raw.get("releasedDate")),
            requisition_id=requisition_id,
            source_payload={"detail": raw},
            detail_fetched=True,
        )
