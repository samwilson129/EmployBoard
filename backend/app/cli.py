from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from typing import Any

import httpx
from sqlalchemy import select

from app.adapters.registry import build_adapter
from app.config import get_settings
from app.database.connection import SessionLocal, dispose_engine
from app.database.repositories import get_stats, list_ingestion_runs
from app.database.seed import seed_companies
from app.logging_config import configure_logging
from app.models.company import Company
from app.services.ingestion_service import IngestionService


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, default=str, ensure_ascii=False)


async def _load_companies(
    provider: str | None = None, company: str | None = None
) -> list[Company]:
    async with SessionLocal() as session:
        stmt = select(Company).where(Company.is_active.is_(True)).order_by(
            Company.company_name.asc()
        )
        if provider:
            stmt = stmt.where(Company.ats_provider == provider)
        if company:
            try:
                company_id = uuid.UUID(company)
                stmt = stmt.where(Company.company_id == company_id)
            except ValueError:
                stmt = stmt.where(Company.company_slug == company)
        return list((await session.scalars(stmt)).all())


async def cmd_seed() -> int:
    async with SessionLocal() as session:
        result = await seed_companies(session)
    print(_json(result))
    return 0


async def cmd_sync(provider: str | None, company: str | None) -> int:
    companies = await _load_companies(provider, company)
    if not companies:
        print("No matching active companies.", file=sys.stderr)
        return 1
    service = IngestionService(SessionLocal, get_settings())
    result = await service.sync_all(
        company_ids=[item.company_id for item in companies],
        providers=[provider] if provider else None,
    )
    print(_json(result))
    return 0 if result.get("status") in ("success", "partial", "already_running") else 1


async def cmd_verify(provider: str | None, company: str | None) -> int:
    settings = get_settings()
    companies = await _load_companies(provider, company)
    if not companies:
        print("No matching active companies.", file=sys.stderr)
        return 1

    failures = 0
    results: list[dict[str, Any]] = []
    headers = {"User-Agent": settings.user_agent, "Accept": "application/json"}
    timeout = httpx.Timeout(settings.http_timeout_seconds, connect=10)
    async with httpx.AsyncClient(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        for item in companies:
            adapter = build_adapter(item.ats_provider, client, settings)
            try:
                jobs = await adapter.fetch_jobs(item)
                results.append(
                    {
                        "company": item.company_name,
                        "provider": item.ats_provider,
                        "board": item.board_identifier,
                        "status": "ok",
                        "jobs": len(jobs),
                        "sample_title": jobs[0].title if jobs else None,
                        "sample_url": jobs[0].application_url if jobs else None,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - verification reports all
                failures += 1
                results.append(
                    {
                        "company": item.company_name,
                        "provider": item.ats_provider,
                        "board": item.board_identifier,
                        "status": "failed",
                        "error": str(exc),
                    }
                )
    print(_json({"ok": failures == 0, "failures": failures, "results": results}))
    return 0 if failures == 0 else 1


async def cmd_stats() -> int:
    async with SessionLocal() as session:
        stats = await get_stats(session)
    print(_json(stats.model_dump()))
    return 0


async def cmd_runs(limit: int) -> int:
    async with SessionLocal() as session:
        runs = await list_ingestion_runs(session, limit)
    print(_json(runs.model_dump()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="EmployBoard ingestion utilities"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Insert or update the verified company registry")

    sync = sub.add_parser("sync", help="Run ingestion now")
    sync.add_argument(
        "--provider",
        choices=[
            "greenhouse",
            "lever",
            "ashby",
            "smartrecruiters",
            "recruitee",
            "workable",
            "personio",
            "teamtailor",
        ],
    )
    sync.add_argument("--company", help="Company slug or UUID")

    verify = sub.add_parser(
        "verify", help="Fetch each configured source without writing to the database"
    )
    verify.add_argument(
        "--provider",
        choices=[
            "greenhouse",
            "lever",
            "ashby",
            "smartrecruiters",
            "recruitee",
            "workable",
            "personio",
            "teamtailor",
        ],
    )
    verify.add_argument("--company", help="Company slug or UUID")

    sub.add_parser("stats", help="Print dashboard statistics")

    runs = sub.add_parser("runs", help="Print recent ingestion runs")
    runs.add_argument("--limit", type=int, default=20)
    return parser


async def _async_main(args: argparse.Namespace) -> int:
    configure_logging(get_settings().log_level)
    try:
        if args.command == "seed":
            return await cmd_seed()
        if args.command == "sync":
            return await cmd_sync(args.provider, args.company)
        if args.command == "verify":
            return await cmd_verify(args.provider, args.company)
        if args.command == "stats":
            return await cmd_stats()
        if args.command == "runs":
            return await cmd_runs(args.limit)
        return 2
    finally:
        await dispose_engine()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()
