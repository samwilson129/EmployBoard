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


class RecruiteeAdapter(ATSAdapter):
    """Adapter for Recruitee's public company offers feed."""

    provider = ATSProvider.RECRUITEE.value
    display_name = "Recruitee"
    documentation_url = "https://docs.recruitee.com/reference/offers"

    async def fetch_jobs(self, company: Company) -> list[AdapterJob]:
        payload = await self._get(
            f"https://{company.board_identifier}.recruitee.com/api/offers"
        )
        return self.parse_jobs(payload, company)

    def parse_jobs(self, payload: Any, company: Company) -> list[AdapterJob]:
        if not isinstance(payload, dict) or not isinstance(payload.get("offers"), list):
            raise ValueError("Recruitee response did not contain an offers list")
        return [
            job
            for raw in payload["offers"]
            if isinstance(raw, dict) and (job := self._parse_job(raw, company))
        ]

    def _parse_job(
        self, raw: dict[str, Any], company: Company
    ) -> AdapterJob | None:
        if str(raw.get("status", "published")).lower() not in {
            "published",
            "open",
            "active",
        }:
            return None
        external_id = raw.get("id") or raw.get("guid") or raw.get("position")
        title = normalize_whitespace(raw.get("title"))
        original_url = clean_url(raw.get("careers_url"))
        application_url = clean_url(raw.get("careers_apply_url")) or original_url
        if external_id in (None, "") or not title or not application_url:
            return None

        location = normalize_whitespace(raw.get("location"))
        salary = raw.get("salary") or {}
        if not isinstance(salary, dict):
            salary = {}
        salary_min = parse_decimal(salary.get("min"))
        salary_max = parse_decimal(salary.get("max"))
        currency = normalize_currency(salary.get("currency"))
        interval = normalize_whitespace(salary.get("period"))

        workplace: str | None = None
        if raw.get("remote") is True:
            workplace = "Remote"
        elif raw.get("hybrid") is True:
            workplace = "Hybrid"
        elif raw.get("on_site") is True:
            workplace = "On-site"

        tags = raw.get("tags")
        skills = tags if isinstance(tags, list) else None
        return AdapterJob(
            external_job_id=str(external_id),
            title=title,
            application_url=application_url,
            original_job_url=original_url or application_url,
            department=normalize_whitespace(raw.get("department")),
            location=location,
            employment_type_raw=normalize_whitespace(
                raw.get("employment_type_code") or raw.get("employment_type")
            ),
            workplace_type_raw=workplace,
            experience_level_raw=normalize_whitespace(raw.get("experience_code")),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_interval=interval,
            description_html=raw.get("description") or raw.get("sharing_description"),
            posted_at=parse_datetime(raw.get("published_at") or raw.get("created_at")),
            expires_at=parse_datetime(raw.get("close_at")),
            skills=skills,
            source_payload=raw,
        )
