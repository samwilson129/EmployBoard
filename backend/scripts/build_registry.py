"""Build the company registry from a verified ATS discovery report.

The discovery report is produced by ``scripts/discover_boards.py``. This script
turns the verified boards into ``app/database/registry.json``, which is the
single source of truth loaded by ``app.database.seed``.

Only boards that were verified against a public provider API are written. The
small exclusion list below contains boards whose provider-reported identity did
not match the candidate, or whose newest posting is years old (abandoned
boards). Nothing is invented: every entry keeps the provider-reported job count
and identity note that were observed during discovery.

Usage (from backend/):

    python scripts/build_registry.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_PATH = ROOT / "scripts" / "board_discovery.json"
OUTPUT_PATH = ROOT / "app" / "database" / "registry.json"

VERIFIED_AT = "2026-11-25"


def _logo(domain: str) -> str:
    return f"https://www.google.com/s2/favicons?sz=128&domain={domain}"


# Existing registry entries verified before the bulk discovery pass. Keeping
# them here (rather than only in the generated JSON) documents their original
# provider mapping and careers URL.
EXISTING: list[dict[str, Any]] = [
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

# (provider, board) pairs that must not enter the registry.
#
# * greenhouse/remote reports "General Assembly Remote Jobs", not Remote.com.
# * lever/neon reports "Neon Pagamentos", a Brazilian fintech, not Neon.
# * smartrecruiters/Together reports a UK property lender called Together, not
#   Together AI.
# * The remaining SmartRecruiters boards still respond but their newest posting
#   is years old (2017-2023); they are abandoned boards, not live job sources.
EXCLUDED: set[tuple[str, str]] = {
    ("greenhouse", "remote"),
    ("lever", "neon"),
    ("smartrecruiters", "Together"),
    ("smartrecruiters", "Wayfair"),
    ("smartrecruiters", "GONG"),
    ("smartrecruiters", "Glean"),
    ("smartrecruiters", "Uber"),
    ("smartrecruiters", "DevotedHealth"),
}

# Boards whose provider-reported name failed the conservative token check but
# were confirmed manually to be the intended company. The verification note
# still records the exact provider-reported name.
ALLOW_REJECTED: set[tuple[str, str]] = {
    # Intercom rebranded the company to Fin; the board identifier is unchanged.
    ("greenhouse", "intercom"),
    # The provider uses the stylised "ŌURA".
    ("greenhouse", "oura"),
    # The provider reports the product name "YugabyteDB".
    ("greenhouse", "yugabyte"),
}

NAME_OVERRIDES: dict[tuple[str, str], str] = {
    # Intercom rebranded the company to Fin; the board identifier is unchanged.
    ("greenhouse", "intercom"): "Intercom (Fin)",
    # Provider-reported names include accents or product suffixes.
    ("greenhouse", "oura"): "Oura",
    ("greenhouse", "yugabyte"): "Yugabyte",
}

SLUG_OVERRIDES: dict[tuple[str, str], str] = {
    ("greenhouse", "intercom"): "intercom",
}

CAREERS_URLS = {
    "greenhouse": "https://boards.greenhouse.io/{board}",
    "lever": "https://jobs.lever.co/{board}",
    "ashby": "https://jobs.ashbyhq.com/{board}",
    "smartrecruiters": "https://careers.smartrecruiters.com/{board}",
}

PROVIDER_LABELS = {
    "greenhouse": "Greenhouse job board API",
    "lever": "Lever public postings API",
    "ashby": "Ashby public job posting API",
    "smartrecruiters": "SmartRecruiters public postings API",
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _entry(hit: dict[str, Any]) -> dict[str, Any]:
    provider = hit["provider"]
    board = hit["board"]
    name = NAME_OVERRIDES.get((provider, board), hit["candidate"])
    slug = SLUG_OVERRIDES.get((provider, board), _slug(name))
    domain = hit["domain"]
    reported = hit["reported_name"] or "unknown"
    jobs = int(hit["jobs"])

    note = (
        f"{PROVIDER_LABELS[provider]} returned {jobs:,} live jobs; "
        f"provider reports company name {reported!r}."
    )
    if provider == "smartrecruiters":
        note += (
            " Descriptions are enriched from the documented posting detail "
            "endpoint for a bounded number of jobs per sync."
        )

    return {
        "company_name": name,
        "company_slug": slug,
        "company_logo_url": _logo(domain),
        "company_website": f"https://{domain}",
        "careers_url": CAREERS_URLS[provider].format(board=board),
        "ats_provider": provider,
        "board_identifier": board,
        "config": {
            "verified_at": VERIFIED_AT,
            "verification_note": note,
            "detail_limit": 100 if provider == "smartrecruiters" else 0,
            "source_url": hit["source_url"],
        },
    }


def main() -> None:
    with DISCOVERY_PATH.open(encoding="utf-8") as handle:
        report = json.load(handle)

    hits = list(report["verified"])
    hits.extend(
        hit
        for hit in report.get("rejected_identity", [])
        if (hit["provider"], hit["board"]) in ALLOW_REJECTED
    )

    candidates = []
    for hit in hits:
        provider = hit["provider"]
        board = hit["board"]
        if (provider, board) in EXCLUDED:
            continue
        if (provider, board) not in ALLOW_REJECTED and not hit.get("identity_ok"):
            continue
        if int(hit.get("jobs") or 0) <= 0:
            continue
        candidates.append(hit)

    entries = [dict(entry) for entry in EXISTING]
    for hit in candidates:
        entries.append(_entry(hit))

    slugs = [entry["company_slug"] for entry in entries]
    duplicates = {slug for slug in slugs if slugs.count(slug) > 1}
    if duplicates:
        raise SystemExit(f"duplicate company slugs: {sorted(duplicates)}")

    boards = [(entry["ats_provider"], entry["board_identifier"]) for entry in entries]
    duplicate_boards = {board for board in boards if boards.count(board) > 1}
    if duplicate_boards:
        raise SystemExit(f"duplicate provider boards: {sorted(duplicate_boards)}")

    entries.sort(key=lambda entry: entry["company_name"].lower())
    OUTPUT_PATH.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    provider_counts: dict[str, int] = {}
    provider_jobs: dict[str, int] = {}
    for hit in candidates:
        provider_counts[hit["provider"]] = provider_counts.get(hit["provider"], 0) + 1
        provider_jobs[hit["provider"]] = provider_jobs.get(hit["provider"], 0) + int(
            hit["jobs"]
        )
    print(
        f"Wrote {len(entries)} companies to {OUTPUT_PATH} "
        f"({len(candidates)} newly discovered)."
    )
    print(f"Discovery report generated at {report.get('generated_at')}")
    for provider in sorted(provider_counts):
        print(
            f"  {provider:16} boards={provider_counts[provider]:3} "
            f"jobs={provider_jobs[provider]:6,}"
        )
    print(f"Excluded {len(EXCLUDED)} boards: {sorted(EXCLUDED)}")


if __name__ == "__main__":
    main()
