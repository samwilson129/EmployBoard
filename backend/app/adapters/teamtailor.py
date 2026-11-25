from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from app.adapters.base import ATSAdapter, AdapterJob
from app.models.company import Company
from app.models.enums import ATSProvider
from app.utils.text import clean_url, normalize_whitespace, parse_datetime

_LOCATION_NS = "{https://teamtailor.com/locations}"


def _child_text(element: ET.Element, tag: str) -> str | None:
    child = element.find(tag)
    return normalize_whitespace(child.text if child is not None else None)


def _locations(item: ET.Element) -> str | None:
    values: list[str] = []
    for location in item.findall(f"{_LOCATION_NS}locations/{_LOCATION_NS}location"):
        parts = [
            _child_text(location, f"{_LOCATION_NS}name"),
            _child_text(location, f"{_LOCATION_NS}city"),
            _child_text(location, f"{_LOCATION_NS}country"),
        ]
        value = ", ".join(part for part in parts if part)
        if value and value not in values:
            values.append(value)
    return "; ".join(values) or None


class TeamtailorAdapter(ATSAdapter):
    """Adapter for Teamtailor's public RSS careers feed."""

    provider = ATSProvider.TEAMTAILOR.value
    display_name = "Teamtailor"
    documentation_url = (
        "https://support.teamtailor.com/en/articles/11171756-rss-feed-how-to-guide"
    )

    async def fetch_jobs(self, company: Company) -> list[AdapterJob]:
        payload = await self._get_text(
            f"https://{company.board_identifier}.teamtailor.com/jobs.rss",
            params={"per_page": 200},
        )
        return self.parse_jobs(payload, company)

    def parse_jobs(self, payload: Any, company: Company) -> list[AdapterJob]:
        if not isinstance(payload, str):
            raise ValueError("Teamtailor response was not RSS text")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ValueError("Teamtailor response was not valid RSS") from exc
        return [
            job
            for item in root.findall("./channel/item")
            if (job := self._parse_job(item, company)) is not None
        ]

    def _parse_job(
        self, item: ET.Element, company: Company
    ) -> AdapterJob | None:
        title = _child_text(item, "title")
        link = clean_url(_child_text(item, "link"))
        guid = _child_text(item, "guid") or link
        if not title or not link or not guid:
            return None
        remote_status = (_child_text(item, "remoteStatus") or "").lower()
        workplace = {
            "remote": "Remote",
            "hybrid": "Hybrid",
            "none": "On-site",
        }.get(remote_status)
        description = _child_text(item, "description")
        return AdapterJob(
            external_job_id=guid,
            title=title,
            application_url=link,
            original_job_url=link,
            department=_child_text(item, f"{_LOCATION_NS}department"),
            location=_locations(item),
            workplace_type_raw=workplace,
            description_html=description,
            posted_at=parse_datetime(_child_text(item, "pubDate")),
            source_payload={
                "title": title,
                "link": link,
                "guid": guid,
                "pubDate": _child_text(item, "pubDate"),
                "remoteStatus": _child_text(item, "remoteStatus"),
                "department": _child_text(item, f"{_LOCATION_NS}department"),
                "location": _locations(item),
            },
        )
