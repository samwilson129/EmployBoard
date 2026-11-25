"""add public ATS providers

Revision ID: 9a4e6d2f1b77
Revises: 7c1f2a9b4d10
Create Date: 2026-11-26 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "9a4e6d2f1b77"
down_revision: Union[str, None] = "7c1f2a9b4d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PUBLIC_PROVIDERS = (
    "'greenhouse', 'lever', 'ashby', 'smartrecruiters', "
    "'recruitee', 'workable', 'personio', 'teamtailor'"
)
_ORIGINAL_PROVIDERS = "'greenhouse', 'lever', 'ashby', 'smartrecruiters'"


def _replace_provider_constraints(values: str) -> None:
    for table, name in (
        ("companies", "ck_companies_ats_provider"),
        ("job_sources", "ck_job_sources_ats_provider"),
        ("ingestion_runs", "ck_ingestion_runs_ats_provider"),
    ):
        op.drop_constraint(name, table_name=table, type_="check")
        op.create_check_constraint(
            name,
            table,
            f"ats_provider IN ({values})",
        )


def upgrade() -> None:
    _replace_provider_constraints(_PUBLIC_PROVIDERS)


def downgrade() -> None:
    _replace_provider_constraints(_ORIGINAL_PROVIDERS)
