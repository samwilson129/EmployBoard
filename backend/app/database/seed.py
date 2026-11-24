from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company


def _logo(domain: str) -> str:
    return f"https://www.google.com/s2/favicons?sz=128&domain={domain}"


# Every entry below was verified against the provider's public posting API on
# 2026-11-24. The verification note records the live response size so that the
# registry documents reality rather than assumptions.
COMPANY_REGISTRY: list[dict[str, Any]] = [
    {
        "company_name": "Notion",
        "company_slug": "notion",
        "company_logo_url": _logo("notion.so"),
        "company_website": "https://www.notion.com",
        "careers_url": "https://www.notion.com/careers",
        "ats_provider": "ashby",
        "board_identifier": "notion",
        "config": {
            "verified_at": "2026-11-24",
            "verification_note": "Ashby public job posting API returned 172 listed jobs.",
            "detail_limit": 0,
        },
    },
    {
        "company_name": "OpenAI",
        "company_slug": "openai",
        "company_logo_url": _logo("openai.com"),
        "company_website": "https://openai.com",
        "careers_url": "https://openai.com/careers",
        "ats_provider": "ashby",
        "board_identifier": "openai",
        "config": {
            "verified_at": "2026-11-24",
            "verification_note": "Ashby public job posting API returned listed jobs with compensation.",
            "detail_limit": 0,
        },
    },
    {
        "company_name": "Snowflake",
        "company_slug": "snowflake",
        "company_logo_url": _logo("snowflake.com"),
        "company_website": "https://www.snowflake.com",
        "careers_url": "https://careers.snowflake.com",
        "ats_provider": "ashby",
        "board_identifier": "snowflake",
        "config": {
            "verified_at": "2026-11-24",
            "verification_note": "Ashby public job posting API returned 374 listed jobs.",
            "detail_limit": 0,
        },
    },
    {
        "company_name": "Spotify",
        "company_slug": "spotify",
        "company_logo_url": _logo("spotify.com"),
        "company_website": "https://www.spotify.com",
        "careers_url": "https://www.lifeatspotify.com",
        "ats_provider": "lever",
        "board_identifier": "spotify",
        "config": {
            "verified_at": "2026-11-24",
            "verification_note": "Lever public postings API returned live postings.",
            "detail_limit": 0,
        },
    },
    {
        "company_name": "Paytm",
        "company_slug": "paytm",
        "company_logo_url": _logo("paytm.com"),
        "company_website": "https://paytm.com",
        "careers_url": "https://paytm.com/careers",
        "ats_provider": "lever",
        "board_identifier": "paytm",
        "config": {
            "verified_at": "2026-11-24",
            "verification_note": "Lever public postings API returned 189 live postings.",
            "detail_limit": 0,
        },
    },
    {
        "company_name": "Bosch",
        "company_slug": "bosch",
        "company_logo_url": _logo("bosch.com"),
        "company_website": "https://www.bosch.com",
        "careers_url": "https://careers.smartrecruiters.com/BoschGroup",
        "ats_provider": "smartrecruiters",
        "board_identifier": "BoschGroup",
        "config": {
            "verified_at": "2026-11-24",
            "verification_note": (
                "SmartRecruiters public postings API returned 5,195 postings. "
                "Descriptions are enriched from the documented posting detail endpoint "
                "for a bounded number of jobs per sync."
            ),
            "detail_limit": 100,
        },
    },
    {
        "company_name": "GitLab",
        "company_slug": "gitlab",
        "company_logo_url": _logo("gitlab.com"),
        "company_website": "https://about.gitlab.com",
        "careers_url": "https://about.gitlab.com/jobs/",
        "ats_provider": "greenhouse",
        "board_identifier": "gitlab",
        "config": {
            "verified_at": "2026-11-24",
            "verification_note": "Greenhouse job board API returned 252 jobs with content.",
            "detail_limit": 0,
        },
    },
]


async def seed_companies(session: AsyncSession) -> dict[str, int]:
    """Insert or update the verified company registry.

    The registry is keyed by (ats_provider, board_identifier), so adding a new
    company only requires a new entry here (or an INSERT through SQL). No
    frontend change is needed.
    """
    inserted = 0
    updated = 0
    for entry in COMPANY_REGISTRY:
        existing = await session.scalar(
            select(Company).where(
                Company.ats_provider == entry["ats_provider"],
                Company.board_identifier == entry["board_identifier"],
            )
        )
        if existing is None:
            session.add(Company(**entry))
            inserted += 1
            continue

        changed = False
        for field, value in entry.items():
            if getattr(existing, field) != value:
                setattr(existing, field, value)
                changed = True
        if changed:
            updated += 1

    await session.commit()
    return {"inserted": inserted, "updated": updated, "total": len(COMPANY_REGISTRY)}
