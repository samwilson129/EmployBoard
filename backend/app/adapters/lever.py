from __future__ import annotations

import html
from typing import Any

from app.adapters.base import ATSAdapter, AdapterJob
from app.models.company import Company
from app.models.enums import ATSProvider
from app.utils.text import clean_url, normalize_whitespace, parse_datetime

_RESPONSIBILITY_HINTS = (
    "what you'll do",
    "what you will do",
    "what you’ll do",
    "responsibilities",
    "the role",
    "your role",
    "what you'll be doing",
    "what you will be doing",
    "day to day",
    "key responsibilities",
)
_REQUIREMENT_HINTS = (
    "who you are",
    "requirements",
    "qualifications",
    "what you bring",
    "about you",
    "you have",
    "skills",
    "experience",
    "what we're looking for",
    "what we are looking for",
)


class LeverAdapter(ATSAdapter):
    provider = ATSProvider.LEVER.value
    display_name = "Lever"
    documentation_url = "https://github.com/lever/postings-api"

    async def fetch_jobs(self, company: Company) -> list[AdapterJob]:
        url = f"https://api.lever.co/v0/postings/{company.board_identifier}"
        payload = await self._get(url, params={"mode": "json"})
        return self.parse_jobs(payload, company)

    def parse_jobs(self, payload: Any, company: Company) -> list[AdapterJob]:
        if not isinstance(payload, list):
            raise ValueError("Lever response was not a list")
        return [
            job
            for raw in payload
            if isinstance(raw, dict) and (job := self._parse_job(raw, company))
        ]

    def _parse_job(self, raw: dict[str, Any], company: Company) -> AdapterJob | None:
        external_id = raw.get("id")
        title = normalize_whitespace(raw.get("text"))
        hosted_url = clean_url(raw.get("hostedUrl"))
        apply_url = clean_url(raw.get("applyUrl")) or hosted_url
        if external_id in (None, "") or not title or not apply_url:
            return None

        categories = raw.get("categories") or {}
        location = normalize_whitespace(categories.get("location"))
        if not location:
            all_locations = [
                normalize_whitespace(item)
                for item in categories.get("allLocations") or []
                if isinstance(item, str)
            ]
            location = ", ".join(item for item in all_locations if item) or None

        sections = raw.get("lists") or []
        description_parts: list[str] = []
        intro = raw.get("description") or raw.get("descriptionBody")
        if isinstance(intro, str) and intro.strip():
            description_parts.append(intro.strip())

        responsibilities: list[str] = []
        requirements: list[str] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            heading = normalize_whitespace(section.get("text"))
            content = section.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            if heading:
                description_parts.append(
                    f"<h3>{html.escape(heading)}</h3>{content.strip()}"
                )
            else:
                description_parts.append(content.strip())
            lowered = (heading or "").lower()
            if any(hint in lowered for hint in _RESPONSIBILITY_HINTS):
                responsibilities.append(content.strip())
            elif any(hint in lowered for hint in _REQUIREMENT_HINTS):
                requirements.append(content.strip())

        additional = raw.get("additional")
        if isinstance(additional, str) and additional.strip():
            description_parts.append(additional.strip())

        description = "\n".join(description_parts) if description_parts else None
        if description is None:
            plain = raw.get("descriptionPlain") or raw.get("openingPlain")
            if isinstance(plain, str) and plain.strip():
                description = f"<p>{html.escape(plain.strip())}</p>"

        return AdapterJob(
            external_job_id=str(external_id),
            title=title,
            application_url=apply_url,
            original_job_url=hosted_url,
            department=normalize_whitespace(
                categories.get("department") or categories.get("team")
            ),
            location=location,
            employment_type_raw=normalize_whitespace(categories.get("commitment")),
            workplace_type_raw=normalize_whitespace(raw.get("workplaceType")),
            description_html=description,
            requirements_html="\n".join(requirements) or None,
            responsibilities_html="\n".join(responsibilities) or None,
            posted_at=parse_datetime(raw.get("createdAt")),
            source_payload=raw,
        )
