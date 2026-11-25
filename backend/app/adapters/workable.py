from __future__ import annotations

from typing import Any

from app.adapters.base import ATSAdapter, AdapterJob
from app.models.company import Company
from app.models.enums import ATSProvider
from app.utils.text import (
    clean_url,
    normalize_currency,
    normalize_whitespace,
    parse_datetime,
    parse_decimal,
)


def _location_from(raw: dict[str, Any]) -> str | None:
    location = raw.get("location")
    if isinstance(location, dict):
        value = normalize_whitespace(location.get("location_str"))
        if value:
            return value
        parts = [
            normalize_whitespace(location.get("city")),
            normalize_whitespace(location.get("region")),
            normalize_whitespace(location.get("country")),
        ]
        return ", ".join(part for part in parts if part) or None
    locations = raw.get("locations")
    if isinstance(locations, list):
        values: list[str] = []
        for item in locations:
            if not isinstance(item, dict):
                continue
            parts = [
                normalize_whitespace(item.get("city")),
                normalize_whitespace(item.get("region")),
                normalize_whitespace(item.get("country")),
            ]
            value = ", ".join(part for part in parts if part)
            if value and value not in values:
                values.append(value)
        return ", ".join(values) or None
    return None


class WorkableAdapter(ATSAdapter):
    """Adapter for Workable's public careers widget feed."""

    provider = ATSProvider.WORKABLE.value
    display_name = "Workable"
    documentation_url = (
        "https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API"
    )

    async def fetch_jobs(self, company: Company) -> list[AdapterJob]:
        payload = await self._get(
            "https://apply.workable.com/api/v1/widget/accounts/"
            f"{company.board_identifier}",
            params={"details": "true"},
        )
        return self.parse_jobs(payload, company)

    def parse_jobs(self, payload: Any, company: Company) -> list[AdapterJob]:
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Workable response did not contain a jobs list")
        return [
            job
            for raw in payload["jobs"]
            if isinstance(raw, dict) and (job := self._parse_job(raw, company))
        ]

    def _parse_job(
        self, raw: dict[str, Any], company: Company
    ) -> AdapterJob | None:
        external_id = raw.get("shortcode") or raw.get("id")
        title = normalize_whitespace(raw.get("title") or raw.get("full_title"))
        hosted_url = clean_url(raw.get("url") or raw.get("shortlink"))
        application_url = clean_url(raw.get("application_url")) or hosted_url
        if external_id in (None, "") or not title or not application_url:
            return None

        workplace: str | None = None
        if raw.get("telecommuting") is True:
            workplace = "Remote"
        elif raw.get("workplace_type"):
            workplace = normalize_whitespace(raw.get("workplace_type"))

        salary = raw.get("salary") or {}
        if not isinstance(salary, dict):
            salary = {}
        return AdapterJob(
            external_job_id=str(external_id),
            title=title,
            application_url=application_url,
            original_job_url=hosted_url or application_url,
            department=normalize_whitespace(
                raw.get("department") or raw.get("function")
            ),
            location=_location_from(raw),
            employment_type_raw=normalize_whitespace(raw.get("employment_type")),
            workplace_type_raw=workplace,
            experience_level_raw=normalize_whitespace(raw.get("experience")),
            salary_min=parse_decimal(salary.get("salary_from")),
            salary_max=parse_decimal(salary.get("salary_to")),
            salary_currency=normalize_currency(salary.get("salary_currency")),
            description_html=raw.get("description"),
            posted_at=parse_datetime(raw.get("published_on") or raw.get("created_at")),
            source_payload=raw,
        )
