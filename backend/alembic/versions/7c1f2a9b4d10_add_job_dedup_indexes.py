"""add job deduplication indexes

Revision ID: 7c1f2a9b4d10
Revises: 4549418ed49a
Create Date: 2026-11-25 18:10:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c1f2a9b4d10"
down_revision: Union[str, None] = "4549418ed49a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both indexes back the per-job deduplication lookups in JobSyncService.
    # Without them, importing a large board scans the company's whole job set
    # for every incoming posting.
    op.create_index(
        "ix_jobs_company_requisition",
        "jobs",
        ["company_id", "requisition_id"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_company_normalized_title",
        "jobs",
        ["company_id", "normalized_title"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_company_normalized_title", table_name="jobs")
    op.drop_index("ix_jobs_company_requisition", table_name="jobs")
