"""clear descriptions left outside the bounded cache

Revision ID: 2f8a6c1d9b44
Revises: 1d7f2c8a4e90
Create Date: 2026-11-29 00:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2f8a6c1d9b44"
down_revision: Union[str, None] = "1d7f2c8a4e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # If an earlier deployment already ran the first cache migration with a
    # smaller snapshot, recover any remaining legacy text before clearing the
    # ledger columns. Fresh upgrades simply find no remaining legacy rows.
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
        FROM jobs AS j
        WHERE j.description IS NOT NULL
           OR j.requirements IS NOT NULL
           OR j.responsibilities IS NOT NULL
        ON CONFLICT (job_id) DO UPDATE SET
            description = COALESCE(
                job_description_cache.description,
                EXCLUDED.description
            ),
            requirements = COALESCE(
                job_description_cache.requirements,
                EXCLUDED.requirements
            ),
            responsibilities = COALESCE(
                job_description_cache.responsibilities,
                EXCLUDED.responsibilities
            ),
            skills = COALESCE(job_description_cache.skills, EXCLUDED.skills),
            updated_at = now()
        """
    )
    # The job rows remain permanent ledger records. Full text that was not in
    # the bounded migration snapshot is intentionally removed from the ledger;
    # future detail requests refill the cache through the adapter capability
    # path instead of growing the permanent table.
    op.execute(
        """
        UPDATE jobs
        SET description = NULL,
            requirements = NULL,
            responsibilities = NULL
        WHERE description IS NOT NULL
           OR requirements IS NOT NULL
           OR responsibilities IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION employboard_compact_payload(value jsonb)
        RETURNS jsonb
        LANGUAGE sql
        IMMUTABLE
        AS $function$
        SELECT CASE jsonb_typeof(value)
            WHEN 'object' THEN (
                SELECT COALESCE(
                    jsonb_object_agg(
                        item.key,
                        employboard_compact_payload(item.value)
                    ),
                    '{}'::jsonb
                )
                FROM jsonb_each(value) AS item
                WHERE lower(replace(item.key, '_', '')) NOT IN (
                    'description',
                    'descriptionhtml',
                    'descriptionplain',
                    'content',
                    'jobad',
                    'sharingdescription',
                    'requirements',
                    'responsibilities',
                    'openingplain'
                )
            )
            WHEN 'array' THEN (
                SELECT COALESCE(
                    jsonb_agg(employboard_compact_payload(item)),
                    '[]'::jsonb
                )
                FROM jsonb_array_elements(value) AS item
            )
            WHEN 'string' THEN to_jsonb(left(value #>> '{}', 2000))
            ELSE value
        END
        $function$
        """
    )
    op.execute(
        """
        UPDATE job_sources
        SET source_payload = employboard_compact_payload(source_payload)
        WHERE source_payload IS NOT NULL
        """
    )
    op.execute("DROP FUNCTION employboard_compact_payload(jsonb)")


def downgrade() -> None:
    # Full legacy text cannot be reconstructed for rows that were outside the
    # bounded cache. Keep the downgrade non-destructive to ledger records.
    # Payload descriptions are intentionally not restored because the
    # migration removes unbounded raw documents from permanent storage.
    pass
