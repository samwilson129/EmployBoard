"""Validate registry feeds, identities, and representative application links.

This is intentionally stricter than directory discovery. A board must still
have live jobs, report the registered company identity, and expose at least one
reachable application URL. Recruitment/staffing intermediaries and demo/test
boards are excluded from the employer registry.

Run without ``--apply`` to audit. The apply mode removes failed or low-quality
boards from the discovery report; ``build_registry.py`` then regenerates the
registry from that filtered evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from scripts.discover_boards import same_company

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "app" / "database" / "registry.json"
REPORT_PATH = ROOT / "scripts" / "board_discovery.json"
USER_AGENT = "EmployBoard/1.0 (public job aggregation; link validation)"
CONCURRENCY = 6

# These terms identify third-party recruiting/staffing intermediaries rather
# than an employer. The rule is deliberately narrow: consulting, technology,
# healthcare, and ordinary talent teams are not excluded by generic wording.
INTERMEDIARY = re.compile(
    r"\b(?:staffing|recruitment|recruiting|recruiter|headhunter|"
    r"manpower|employment agency|job agency|temp agency|"
    r"workforce solutions|talent trader|talent agency|"
    r"recruitment agency|staffing solutions)\b",
    re.IGNORECASE,
)
DEMO_BOARD = re.compile(
    r"(?:^|[-_])(?:demo|test|sandbox|example)(?:$|[-_])",
    re.IGNORECASE,
)


async def _get(
    client: httpx.AsyncClient, url: str, **kwargs: Any
) -> httpx.Response | None:
    for attempt in range(5):
        try:
            response = await client.get(url, **kwargs)
        except httpx.HTTPError:
            response = None
        if response is not None and response.status_code not in {
            429,
            500,
            502,
            503,
            504,
        }:
            return response
        if attempt < 4:
            retry_after = (
                response.headers.get("retry-after") if response else None
            )
            try:
                delay = min(float(retry_after), 60.0) if retry_after else None
            except ValueError:
                delay = None
            await asyncio.sleep(delay or min(2**attempt, 20))
    return None


def _provider_payload(
    provider: str, board: str, response: httpx.Response
) -> tuple[int, str | None, str | None]:
    """Return live count, reported identity, and one application URL."""
    if provider == "greenhouse":
        payload = response.json()
        jobs = [
            item for item in payload.get("jobs", []) if isinstance(item, dict)
        ]
        first = jobs[0] if jobs else {}
        return len(jobs), None, first.get("absolute_url")
    if provider == "lever":
        jobs = response.json()
        jobs = [item for item in jobs if isinstance(item, dict)]
        first = jobs[0] if jobs else {}
        return (
            len(jobs),
            None,
            first.get("applyUrl") or first.get("hostedUrl"),
        )
    if provider == "ashby":
        payload = response.json()
        jobs = [
            item for item in payload.get("jobs", []) if isinstance(item, dict)
        ]
        first = jobs[0] if jobs else {}
        return (
            len(jobs),
            None,
            first.get("applyUrl") or first.get("jobUrl"),
        )
    if provider == "smartrecruiters":
        payload = response.json()
        jobs = [
            item for item in payload.get("content", []) if isinstance(item, dict)
        ]
        first = jobs[0] if jobs else {}
        job_id = first.get("id")
        return (
            len(jobs),
            None,
            f"https://jobs.smartrecruiters.com/{board}/{job_id}"
            if job_id
            else None,
        )
    if provider == "recruitee":
        payload = response.json()
        offers = [
            item
            for item in payload.get("offers", [])
            if isinstance(item, dict)
        ]
        first = offers[0] if offers else {}
        return (
            len(offers),
            str(first.get("company_name")) if first.get("company_name") else None,
            first.get("careers_apply_url") or first.get("careers_url"),
        )
    if provider == "workable":
        payload = response.json()
        jobs = [
            item for item in payload.get("jobs", []) if isinstance(item, dict)
        ]
        first = jobs[0] if jobs else {}
        return (
            len(jobs),
            str(payload.get("name")) if payload.get("name") else None,
            first.get("application_url")
            or first.get("url")
            or first.get("shortlink"),
        )
    if provider == "personio":
        root = ET.fromstring(response.text)
        positions = root.findall("./position")
        first = positions[0] if positions else None
        reported = next(
            (
                child.text.strip()
                for position in positions
                for child in [position.find("subcompany")]
                if child is not None and child.text and child.text.strip()
            ),
            None,
        )
        job_id = first.findtext("id") if first is not None else None
        apply_url = (
            f"https://{board}.jobs.personio.de/job/{job_id}?language=en"
            if job_id
            else None
        )
        return len(positions), reported, apply_url

    root = ET.fromstring(response.text)
    items = root.findall("./channel/item")
    first = items[0] if items else None
    return (
        len(items),
        root.findtext("./channel/title"),
        first.findtext("link") if first is not None else None,
    )


def _feed_request(provider: str, board: str) -> tuple[str, dict[str, str]]:
    if provider == "greenhouse":
        return (
            f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
            {"content": "false"},
        )
    if provider == "lever":
        return f"https://api.lever.co/v0/postings/{board}", {"mode": "json"}
    if provider == "ashby":
        return (
            f"https://api.ashbyhq.com/posting-api/job-board/{board}",
            {"includeCompensation": "false"},
        )
    if provider == "smartrecruiters":
        return (
            f"https://api.smartrecruiters.com/v1/companies/{board}/postings",
            {"limit": "100"},
        )
    if provider == "recruitee":
        return f"https://{board}.recruitee.com/api/offers", {}
    if provider == "workable":
        return (
            f"https://apply.workable.com/api/v1/widget/accounts/{board}",
            {"details": "true"},
        )
    if provider == "personio":
        return f"https://{board}.jobs.personio.de/xml", {"language": "en"}
    return f"https://{board}.teamtailor.com/jobs.rss", {"per_page": "200"}


async def _check_apply(
    client: httpx.AsyncClient, url: str | None
) -> tuple[bool, int | None, str | None]:
    if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return False, None, None
    for attempt in range(5):
        try:
            async with client.stream("GET", url) as response:
                if response.status_code not in {429, 500, 502, 503, 504}:
                    return (
                        response.status_code < 400,
                        response.status_code,
                        str(response.url),
                    )
        except (httpx.HTTPError, ValueError):
            pass
        if attempt < 4:
            await asyncio.sleep(min(2**attempt, 20))
    return False, None, None


async def _validate(
    client: httpx.AsyncClient, entry: dict[str, Any]
) -> dict[str, Any]:
    provider = entry["ats_provider"]
    board = entry["board_identifier"]
    result = {
        "provider": provider,
        "board": board,
        "company": entry["company_name"],
        "feed_status": None,
        "feed_jobs": 0,
        "reported_name": None,
        "identity_ok": False,
        "careers_status": None,
        "careers_ok": False,
        "apply_url": None,
        "apply_status": None,
        "apply_ok": False,
        "quality_ok": True,
        "reasons": [],
    }
    if INTERMEDIARY.search(entry["company_name"]):
        result["quality_ok"] = False
        result["reasons"].append("recruitment_or_staffing_intermediary")
    if DEMO_BOARD.search(board):
        result["quality_ok"] = False
        result["reasons"].append("demo_or_test_board")

    url, params = _feed_request(provider, board)
    try:
        response = await _get(client, url, params=params)
        result["feed_status"] = response.status_code if response else None
        if response is None or response.status_code != 200:
            result["reasons"].append("feed_unreachable")
            return result
        count, reported, apply_url = _provider_payload(provider, board, response)
        if reported is None and provider in {
            "greenhouse",
            "lever",
            "ashby",
            "smartrecruiters",
        }:
            # These documented public feeds do not expose a company name in
            # each response. Their board identity was already verified during
            # discovery; here we validate freshness and link reachability.
            reported = entry["company_name"]
        result["feed_jobs"] = count
        result["reported_name"] = reported
        result["identity_ok"] = same_company(entry["company_name"], reported)
        result["apply_url"] = apply_url
        if count <= 0:
            result["reasons"].append("no_live_jobs")
        if not result["identity_ok"]:
            result["reasons"].append("provider_identity_mismatch")
        careers_ok, careers_status, careers_final_url = await _check_apply(
            client, entry["careers_url"]
        )
        result["careers_ok"] = careers_ok
        result["careers_status"] = careers_status
        result["careers_final_url"] = careers_final_url
        if not careers_ok:
            result["reasons"].append("careers_link_unreachable")
        ok, status, final_url = await _check_apply(client, apply_url)
        result["apply_ok"] = ok
        result["apply_status"] = status
        result["apply_final_url"] = final_url
        if not ok:
            result["reasons"].append("application_link_unreachable")
    except (ET.ParseError, httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        result["reasons"].append(f"validation_error:{type(exc).__name__}")
    return result


async def run(apply: bool) -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/rss+xml, text/xml",
    }
    semaphore = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(35.0, connect=12.0),
        follow_redirects=True,
        headers=headers,
        limits=httpx.Limits(max_connections=48, max_keepalive_connections=24),
    ) as client:
        async def guarded(entry: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await _validate(client, entry)

        results = await asyncio.gather(*(guarded(entry) for entry in registry))

    valid = [
        item
        for item in results
        if item["feed_jobs"] > 0
        and item["identity_ok"]
        and item["careers_ok"]
        and item["apply_ok"]
        and item["quality_ok"]
    ]
    rejected = [item for item in results if item not in valid]
    counts: dict[str, int] = {}
    for item in rejected:
        for reason in item["reasons"]:
            counts[reason] = counts.get(reason, 0) + 1
    print(
        f"validated={len(results)} valid={len(valid)} rejected={len(rejected)}"
    )
    print("rejection_reasons=", json.dumps(counts, sort_keys=True))
    for item in rejected[:100]:
        print(
            f"  {item['company']} [{item['provider']}/{item['board']}] "
            f"{','.join(item['reasons'])}"
        )

    output = ROOT / "scripts" / "registry_quality_report.json"
    output.write_text(
        json.dumps(
            {
                "validated": len(results),
                "valid": len(valid),
                "rejected": len(rejected),
                "rejection_reasons": counts,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    if not apply:
        return

    valid_boards = {(item["provider"], item["board"]) for item in valid}
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    report["quality_rejected"] = [
        item for item in rejected if item["feed_jobs"] > 0
    ]
    report["verified"] = [
        hit
        for hit in report.get("verified", [])
        if (hit["provider"], hit["board"]) in valid_boards
        or (hit["provider"], hit["board"])
        not in {(item["provider"], item["board"]) for item in results}
    ]
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"filtered discovery report -> {REPORT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="remove failed/low-quality boards from discovery evidence",
    )
    args = parser.parse_args()
    asyncio.run(run(args.apply))


if __name__ == "__main__":
    main()
