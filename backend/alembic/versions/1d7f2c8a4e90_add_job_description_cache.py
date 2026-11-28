"""add permanent ledger timestamps and bounded description caches

Revision ID: 1d7f2c8a4e90
Revises: 9a4e6d2f1b77
Create Date: 2026-11-29 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "1d7f2c8a4e90"
down_revision: Union[str, None] = "9a4e6d2f1b77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for name, column in (
        ("api_requests", sa.Integer()),
        ("api_rate_limits", sa.Integer()),
        ("api_failures", sa.Integer()),
        ("average_response_ms", sa.Float()),
        ("consecutive_failures", sa.Integer()),
    ):
        op.add_column(
            "ingestion_runs",
            sa.Column(name, column, nullable=False, server_default=sa.text("0")),
        )
    op.add_column(
        "jobs",
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("description_snippet", sa.String(length=500), nullable=True),
    )
    op.execute(
        """
        UPDATE jobs AS j
        SET last_verified_at = source.last_verified_at
        FROM (
            SELECT job_id, MAX(COALESCE(last_verified_at, fetched_at)) AS last_verified_at
            FROM job_sources
            GROUP BY job_id
        ) AS source
        WHERE source.job_id = j.job_id
        """
    )
    op.execute(
        """
        UPDATE jobs
        SET description_snippet = left(
            regexp_replace(
                regexp_replace(coalesce(description, ''), '<[^>]+>', ' ', 'g'),
                '\\s+', ' ', 'g'
            ),
            500
        )
        WHERE description IS NOT NULL
        """
    )

    op.create_table(
        "job_description_cache",
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.job_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("responsibilities", sa.Text(), nullable=True),
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "cached_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_provider", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetch_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_job_description_cache_expires_at",
        "job_description_cache",
        ["expires_at"],
    )
    op.create_index(
        "ix_job_description_cache_last_accessed_at",
        "job_description_cache",
        ["last_accessed_at"],
    )

    op.create_table(
        "job_description_negative_cache",
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.job_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("failure_reason", sa.String(length=64), nullable=False),
        sa.Column(
            "failed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("retry_after_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_job_description_negative_cache_retry_after",
        "job_description_negative_cache",
        ["retry_after_at"],
    )

    # Copy every existing description into the cache before clearing the
    # legacy ledger columns. The scheduled maintenance job applies the
    # configured LRU capacity after migration; this avoids data loss during
    # the upgrade itself.
    op.execute(
        """
        INSERT INTO job_description_cache (
            job_id, description, requirements, responsibilities, skills,
            cached_at, last_accessed_at, expires_at, source_provider,
            source_updated_at, fetch_count, created_at, updated_at
        )
        SELECT
            j.job_id, j.description, j.requirements, j.responsibilities, j.skills,
            now(), now(), now() + interval '24 hours',
            (
                SELECT js.ats_provider
                FROM job_sources js
                WHERE js.job_id = j.job_id
                ORDER BY COALESCE(js.last_verified_at, js.fetched_at) DESC
                LIMIT 1
            ),
            j.last_verified_at, 0, now(), now()
        FROM jobs j
        WHERE j.description IS NOT NULL
           OR j.requirements IS NOT NULL
           OR j.responsibilities IS NOT NULL
        ORDER BY j.updated_at DESC
        """
    )
    op.execute(
        """
        UPDATE jobs AS j
        SET description = NULL, requirements = NULL, responsibilities = NULL
        WHERE EXISTS (
            SELECT 1 FROM job_description_cache c WHERE c.job_id = j.job_id
        )
        """
    )


def downgrade() -> None:
    for name in (
        "consecutive_failures",
        "average_response_ms",
        "api_failures",
        "api_rate_limits",
        "api_requests",
    ):
        op.drop_column("ingestion_runs", name)
    op.execute(
        """
        UPDATE jobs AS j
        SET description = c.description,
            requirements = c.requirements,
            responsibilities = c.responsibilities,
            skills = COALESCE(j.skills, c.skills)
        FROM job_description_cache c
        WHERE c.job_id = j.job_id
        """
    )
    op.drop_index(
        "ix_job_description_negative_cache_retry_after",
        table_name="job_description_negative_cache",
    )
    op.drop_table("job_description_negative_cache")
    op.drop_index(
        "ix_job_description_cache_last_accessed_at",
        table_name="job_description_cache",
    )
    op.drop_index(
        "ix_job_description_cache_expires_at",
        table_name="job_description_cache",
    )
    op.drop_table("job_description_cache")
    op.drop_column("jobs", "last_verified_at")
    op.drop_column("jobs", "description_snippet")
