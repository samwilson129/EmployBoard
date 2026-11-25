from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from typing import Any

from app.adapters.base import ATSAdapter, AdapterJob
from app.models.company import Company
from app.models.enums import ATSProvider
from app.utils.text import clean_url, normalize_whitespace, parse_datetime


def _text(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    child = element.find(name)
    return normalize_whitespace(child.text if child is not None else None)


class PersonioAdapter(ATSAdapter):
    """Adapter for Personio's official public career-site XML feed."""

    provider = ATSProvider.PERSONIO.value
    display_name = "Personio"
    documentation_url = "https://developer.personio.de/v1.0/reference/get_xml"

    async def fetch_jobs(self, company: Company) -> list[AdapterJob]:
        payload = await self._get_text(
            f"https://{company.board_identifier}.jobs.personio.de/xml",
            params={"language": "en"},
        )
        return self.parse_jobs(payload, company)

    def parse_jobs(self, payload: Any, company: Company) -> list[AdapterJob]:
        if not isinstance(payload, str):
            raise ValueError("Personio response was not XML text")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ValueError("Personio response was not valid XML") from exc
        return [
            job
            for raw in root.findall("./position")
            if (job := self._parse_job(raw, company)) is not None
        ]

    def _parse_job(
        self, raw: ET.Element, company: Company
    ) -> AdapterJob | None:
        external_id = _text(raw, "id")
        title = _text(raw, "name")
        if not external_id or not title:
            return None
        application_url = (
            f"https://{company.board_identifier}.jobs.personio.de/job/"
            f"{external_id}?language=en"
        )
        descriptions: list[str] = []
        for section in raw.findall("./jobDescriptions/jobDescription"):
            heading = _text(section, "name")
            value_node = section.find("value")
            value = value_node.text if value_node is not None else None
            if not isinstance(value, str) or not value.strip():
                continue
            content = html.unescape(value.strip())
            descriptions.append(
                f"<h3>{html.escape(heading)}</h3>{content}"
                if heading
                else content
            )
        schedule = _text(raw, "schedule")
        employment = _text(raw, "employmentType")
        employment_raw = " ".join(
            value for value in (employment, schedule) if value
        ) or None
        return AdapterJob(
            external_job_id=external_id,
            title=title,
            application_url=clean_url(application_url) or application_url,
            original_job_url=application_url,
            department=_text(raw, "department"),
            location=_text(raw, "office"),
            employment_type_raw=employment_raw,
            experience_level_raw=_text(raw, "seniority"),
            description_html="\n".join(descriptions) or None,
            posted_at=parse_datetime(_text(raw, "createdAt")),
            source_payload={
                child.tag: child.text
                for child in raw
                if child.tag != "jobDescriptions"
            },
        )
