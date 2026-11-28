from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base
from app.models.enums import ATS_PROVIDERS, RUN_STATUSES


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "ats_provider IN ("
            + ", ".join(f"'{provider}'" for provider in ATS_PROVIDERS)
            + ")",
            name="ck_ingestion_runs_ats_provider",
        ),
        CheckConstraint(
            "status IN ("
            + ", ".join(f"'{status}'" for status in RUN_STATUSES)
            + ")",
            name="ck_ingestion_runs_status",
        ),
        Index("ix_ingestion_runs_started", text("started_at DESC")),
        Index("ix_ingestion_runs_company", "company_id", text("started_at DESC")),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ats_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="SET NULL"),
        nullable=True,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="running", server_default=text("'running'")
    )

    jobs_fetched: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    jobs_inserted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    jobs_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    jobs_deactivated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    jobs_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    api_requests: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    api_rate_limits: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    api_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    average_response_ms: Mapped[float] = mapped_column(
        Float(), nullable=False, default=0, server_default=text("0")
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    errors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
