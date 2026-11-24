from __future__ import annotations

import html
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

_INTERVALS = {
    "1 YEAR": "year",
    "1 MONTH": "month",
    "1 WEEK": "week",
    "1 DAY": "day",
    "1 HOUR": "hour",
}


class AshbyAdapter(ATSAdapter):
    provider = ATSProvider.ASHBY.value
    display_name = "Ashby"
    documentation_url = "https://developers.ashbyhq.com/docs/public-job-posting-api"

    async def fetch_jobs(self, company: Company) -> list[AdapterJob]:
        url = (
            "https://api.ashbyhq.com/posting-api/job-board/"
            f"{company.board_identifier}"
        )
        payload = await self._get(
            url, params={"includeCompensation": "true"}
        )
        return self.parse_jobs(payload, company)

    def parse_jobs(self, payload: Any, company: Company) -> list[AdapterJob]:
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Ashby response did not contain a jobs list")
        return [
            job
            for raw in payload["jobs"]
            if isinstance(raw, dict) and (job := self._parse_job(raw, company))
        ]

    def _parse_job(self, raw: dict[str, Any], company: Company) -> AdapterJob | None:
        if raw.get("isListed") is False:
            return None
        external_id = raw.get("id")
        title = normalize_whitespace(raw.get("title"))
        job_url = clean_url(raw.get("jobUrl"))
        apply_url = clean_url(raw.get("applyUrl")) or job_url
        if external_id in (None, "") or not title or not apply_url:
            return None

        location = normalize_whitespace(raw.get("location"))
        if not location:
            address = (raw.get("address") or {}).get("postalAddress") or {}
            parts = [
                normalize_whitespace(address.get("addressLocality")),
                normalize_whitespace(address.get("addressRegion")),
                normalize_whitespace(address.get("addressCountry")),
            ]
            location = ", ".join(part for part in parts if part) or None

        salary_min, salary_max, currency, interval = self._parse_salary(
            raw.get("compensation") or {}
        )

        description = raw.get("descriptionHtml")
        if not isinstance(description, str) or not description.strip():
            plain = raw.get("descriptionPlain")
            description = (
                f"<p>{html.escape(plain.strip())}</p>"
                if isinstance(plain, str) and plain.strip()
                else None
            )

        return AdapterJob(
            external_job_id=str(external_id),
            title=title,
            application_url=apply_url,
            original_job_url=job_url,
            department=normalize_whitespace(raw.get("department") or raw.get("team")),
            location=location,
            employment_type_raw=normalize_whitespace(raw.get("employmentType")),
            workplace_type_raw=normalize_whitespace(raw.get("workplaceType")),
            description_html=description,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_interval=interval,
            posted_at=parse_datetime(raw.get("publishedAt")),
            source_payload=raw,
        )

    def _parse_salary(
        self, compensation: dict[str, Any]
    ) -> tuple[Any, Any, str | None, str | None]:
        components = compensation.get("summaryComponents")
        if not isinstance(components, list):
            components = []
        for component in components:
            if not isinstance(component, dict):
                continue
            if str(component.get("compensationType", "")).lower() != "salary":
                continue
            salary_min = parse_decimal(component.get("minValue"))
            salary_max = parse_decimal(component.get("maxValue"))
            if salary_min is None and salary_max is None:
                continue
            interval = _INTERVALS.get(
                str(component.get("interval", "")).strip().upper()
            )
            return (
                salary_min,
                salary_max,
                normalize_currency(component.get("currencyCode")),
                interval,
            )
        return None, None, None, None
