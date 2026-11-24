from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin
from app.models.enums import ATS_PROVIDERS

if TYPE_CHECKING:
    from app.models.job import Job


class JobSource(Base, TimestampMixin):
    __tablename__ = "job_sources"
    __table_args__ = (
        UniqueConstraint(
            "ats_provider", "external_job_id", name="uq_job_sources_provider_external"
        ),
        CheckConstraint(
            "ats_provider IN ("
            + ", ".join(f"'{provider}'" for provider in ATS_PROVIDERS)
            + ")",
            name="ck_job_sources_ats_provider",
        ),
        Index("ix_job_sources_job_provider", "job_id", "ats_provider"),
        Index("ix_job_sources_provider_verified", "ats_provider", "last_verified_at"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ats_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    original_job_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job: Mapped["Job"] = relationship(back_populates="sources")
