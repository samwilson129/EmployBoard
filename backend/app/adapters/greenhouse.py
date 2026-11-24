from __future__ import annotations

from typing import Any

from app.adapters.base import ATSAdapter, AdapterJob
from app.models.company import Company
from app.models.enums import ATSProvider
from app.utils.text import (
    clean_url,
    normalize_whitespace,
    parse_datetime,
    unescape_html,
)

_METADATA_FIELDS = {
    "employment_type": (
        "employment type",
        "employment_type",
        "worker type",
        "job type",
    ),
    "workplace_type": (
        "workplace type",
        "workplace_type",
        "remote type",
        "work environment",
    ),
    "experience_level": (
        "experience level",
        "experience_level",
        "seniority",
    ),
}


class GreenhouseAdapter(ATSAdapter):
    provider = ATSProvider.GREENHOUSE.value
    display_name = "Greenhouse"
    documentation_url = "https://developers.greenhouse.io/job-board.html"

    async def fetch_jobs(self, company: Company) -> list[AdapterJob]:
        url = (
            "https://boards-api.greenhouse.io/v1/boards/"
            f"{company.board_identifier}/jobs"
        )
        payload = await self._get(url, params={"content": "true"})
        return self.parse_jobs(payload, company)

    def parse_jobs(self, payload: Any, company: Company) -> list[AdapterJob]:
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Greenhouse response did not contain a jobs list")
        return [
            job
            for raw in payload["jobs"]
            if isinstance(raw, dict) and (job := self._parse_job(raw, company))
        ]

    def _parse_job(self, raw: dict[str, Any], company: Company) -> AdapterJob | None:
        external_id = raw.get("id")
        title = normalize_whitespace(raw.get("title"))
        application_url = clean_url(raw.get("absolute_url"))
        if external_id in (None, "") or not title or not application_url:
            return None

        location = normalize_whitespace((raw.get("location") or {}).get("name"))
        if not location:
            offices = [
                normalize_whitespace(office.get("name"))
                for office in raw.get("offices") or []
                if isinstance(office, dict)
            ]
            location = next((office for office in offices if office), None)

        department = None
        departments = [
            normalize_whitespace(item.get("name"))
            for item in raw.get("departments") or []
            if isinstance(item, dict)
        ]
        department = next((item for item in departments if item), None)

        metadata = {
            str(item.get("name", "")).strip().lower(): item.get("value")
            for item in raw.get("metadata") or []
            if isinstance(item, dict)
        }
        employment_type = self._metadata(metadata, "employment_type")
        workplace_type = self._metadata(metadata, "workplace_type")
        experience_level = self._metadata(metadata, "experience_level")

        requisition_id = raw.get("requisition_id")
        if requisition_id is not None:
            requisition_id = str(requisition_id).strip() or None

        return AdapterJob(
            external_job_id=str(external_id),
            title=title,
            application_url=application_url,
            original_job_url=application_url,
            department=department,
            location=location,
            employment_type_raw=str(employment_type) if employment_type else None,
            workplace_type_raw=str(workplace_type) if workplace_type else None,
            experience_level_raw=str(experience_level) if experience_level else None,
            description_html=unescape_html(raw.get("content")),
            posted_at=parse_datetime(
                raw.get("first_published") or raw.get("updated_at")
            ),
            expires_at=parse_datetime(raw.get("application_deadline")),
            requisition_id=requisition_id,
            source_payload=raw,
        )

    @staticmethod
    def _metadata(metadata: dict[str, Any], key: str) -> Any:
        for candidate in _METADATA_FIELDS[key]:
            if candidate in metadata:
                value = metadata[candidate]
                if value not in (None, "", "n/a"):
                    return value
        return None
