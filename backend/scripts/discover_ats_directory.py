"""Verify public ATS boards listed by a public directory.

The directory is only a candidate source. No directory count or company name
is trusted until the provider's own credential-free feed returns live jobs and
its reported identity matches the candidate.

Usage (from backend/):

    python scripts/discover_ats_directory.py
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path

import httpx

from scripts.discover_boards import Hit, same_company

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "scripts" / "board_discovery.json"
REGISTRY_PATH = ROOT / "app" / "database" / "registry.json"
DIRECTORY_BASE = "https://deriverge.com/tools/data/ats"
PROVIDERS = ("recruitee", "workable", "personio", "teamtailor")
USER_AGENT = "EmployBoard/1.0 (public job aggregation; board discovery)"
CONCURRENCY = 16


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _candidate_rows(payload: dict) -> list[tuple[str, str, str]]:
    candidates = []
    for row in payload.get("rows", []):
        if not isinstance(row, list) or len(row) < 4:
            continue
        name, board, _country, open_jobs = row[:4]
        if not isinstance(name, str) or not isinstance(board, str):
            continue
        if not isinstance(open_jobs, int) or open_jobs <= 0:
            continue
        candidates.append((name.strip(), board.strip(), str(open_jobs)))
    return candidates


def _parse_xml(payload: str, provider: str) -> tuple[int, str | None]:
    root = ET.fromstring(payload)
    if provider == "teamtailor":
        return len(root.findall("./channel/item")), root.findtext("./channel/title")
    positions = root.findall("./position")
    reported = next(
        (
            element.text.strip()
            for position in positions
            for element in [position.find("subcompany")]
            if element is not None and element.text and element.text.strip()
        ),
        None,
    )
    return len(positions), reported


async def _get(
    client: httpx.AsyncClient, url: str, **kwargs: object
) -> httpx.Response | None:
    for attempt in range(3):
        try:
            response = await client.get(url, **kwargs)
        except httpx.HTTPError:
            response = None
        if response is not None and response.status_code not in {429, 500, 502, 503, 504}:
            return response
        if attempt < 2:
            await asyncio.sleep(1.5 * (attempt + 1))
    return None


async def _probe(
    client: httpx.AsyncClient,
    provider: str,
    candidate: tuple[str, str, str],
) -> Hit | None:
    name, board, _directory_count = candidate
    try:
        if provider == "recruitee":
            response = await _get(client, f"https://{board}.recruitee.com/api/offers")
            payload = response.json() if response and response.status_code == 200 else {}
            offers = payload.get("offers", []) if isinstance(payload, dict) else []
            offers = [item for item in offers if isinstance(item, dict)]
            reported = next(
                (
                    str(item["company_name"])
                    for item in offers
                    if item.get("company_name")
                ),
                None,
            )
            count = len(offers)
            source_url = f"https://{board}.recruitee.com/"
            domain = f"{board}.recruitee.com"
        elif provider == "workable":
            response = await _get(
                client,
                f"https://apply.workable.com/api/v1/widget/accounts/{board}",
                params={"details": "true"},
            )
            payload = response.json() if response and response.status_code == 200 else {}
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            jobs = [item for item in jobs if isinstance(item, dict)]
            count = len(jobs)
            reported = str(payload["name"]) if payload.get("name") else None
            source_url = f"https://apply.workable.com/{board}/"
            domain = f"apply.workable.com"
        elif provider == "personio":
            response = await _get(
                client,
                f"https://{board}.jobs.personio.de/xml",
                params={"language": "en"},
            )
            count, reported = (
                _parse_xml(response.text, provider)
                if response and response.status_code == 200
                else (0, None)
            )
            source_url = f"https://{board}.jobs.personio.de/"
            domain = f"{board}.jobs.personio.de"
        else:
            response = await _get(
                client,
                f"https://{board}.teamtailor.com/jobs.rss",
                params={"per_page": 200},
            )
            count, reported = (
                _parse_xml(response.text, provider)
                if response and response.status_code == 200
                else (0, None)
            )
            source_url = f"https://{board}.teamtailor.com/jobs"
            domain = f"{board}.teamtailor.com"
        if count <= 0:
            return None
        return Hit(
            candidate=name,
            domain=domain,
            provider=provider,
            board=board,
            reported_name=reported.strip() if reported else None,
            jobs=count,
            source_url=source_url,
            identity_ok=same_company(name, reported),
        )
    except (ET.ParseError, httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


async def main() -> None:
    started = time.perf_counter()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/rss+xml, text/xml",
    }
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(45.0, connect=15.0),
        follow_redirects=True,
        headers=headers,
        limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
    ) as client:
        directory_data = {}
        for provider in PROVIDERS:
            response = await client.get(f"{DIRECTORY_BASE}/{provider}.json")
            response.raise_for_status()
            directory_data[provider] = response.json()

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def guarded(
            provider: str, candidate: tuple[str, str, str]
        ) -> Hit | None:
            async with semaphore:
                return await _probe(client, provider, candidate)

        tasks = [
            guarded(provider, candidate)
            for provider, payload in directory_data.items()
            for candidate in _candidate_rows(payload)
        ]
        hits = [
            hit for hit in await asyncio.gather(*tasks) if hit is not None
        ]

    with REPORT_PATH.open(encoding="utf-8") as handle:
        report = json.load(handle)
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        registry = json.load(handle)

    existing_boards = {
        (hit["provider"], hit["board"]) for hit in report.get("verified", [])
    }
    existing_slugs = {_slug(entry["company_slug"]) for entry in registry}
    existing_slugs.update(
        _slug(hit["candidate"]) for hit in report.get("verified", [])
    )
    accepted = []
    for hit in hits:
        if not hit.identity_ok or hit.jobs <= 0:
            continue
        if (hit.provider, hit.board) in existing_boards:
            continue
        # The application stores one company row per company. Avoid adding a
        # second provider board for a company already represented in the
        # registry; this also prevents same-name directory collisions.
        display_name = hit.reported_name or hit.candidate
        if _slug(hit.candidate) in existing_slugs or _slug(display_name) in existing_slugs:
            continue
        # Use the provider's own spelling in the registry. This avoids
        # propagating stale directory transliteration or replacement
        # characters into company names.
        hit.candidate = display_name
        accepted.append(hit)
        existing_boards.add((hit.provider, hit.board))
        existing_slugs.add(_slug(hit.candidate))

    report["verified"].extend(
        asdict(hit)
        for hit in sorted(accepted, key=lambda item: (-item.jobs, item.candidate))
    )
    report.setdefault("rejected_identity", []).extend(
        asdict(hit) for hit in hits if not hit.identity_ok
    )
    report.setdefault("all_hits", []).extend(asdict(hit) for hit in hits)
    report["directory_sources"] = {
        provider: f"{DIRECTORY_BASE}/{provider}.json" for provider in PROVIDERS
    }
    report["directory_candidates"] = sum(
        len(_candidate_rows(payload)) for payload in directory_data.values()
    )
    report["directory_direct_hits"] = len(hits)
    report["directory_verified"] = len(accepted)
    report["directory_elapsed_seconds"] = round(time.perf_counter() - started, 1)
    with REPORT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    by_provider: dict[str, tuple[int, int]] = {}
    for hit in accepted:
        count, jobs = by_provider.get(hit.provider, (0, 0))
        by_provider[hit.provider] = (count + 1, jobs + hit.jobs)
    print(
        f"checked {report['directory_candidates']} live directory candidates; "
        f"direct hits={len(hits)}, new verified={len(accepted)}, "
        f"elapsed={report['directory_elapsed_seconds']}s"
    )
    for provider in PROVIDERS:
        boards, jobs = by_provider.get(provider, (0, 0))
        print(f"  {provider:12} boards={boards:4} jobs={jobs:7,}")


if __name__ == "__main__":
    asyncio.run(main())
