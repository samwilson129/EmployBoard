from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company

_REGISTRY_PATH = Path(__file__).with_name("registry.json")


def _load_registry() -> list[dict[str, Any]]:
    with _REGISTRY_PATH.open(encoding="utf-8") as handle:
        entries = json.load(handle)
    if not isinstance(entries, list):
        raise ValueError("registry.json must contain a list of company entries")
    return entries


# Every entry is verified against the provider's public posting API. The
# verification note records the live response size and provider-reported
# identity so that the registry documents reality rather than assumptions.
# Regenerate it with ``python scripts/build_registry.py`` after a discovery run.
COMPANY_REGISTRY: list[dict[str, Any]] = _load_registry()


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
