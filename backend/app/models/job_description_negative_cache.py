from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.job import Job


class JobDescriptionNegativeCache(Base, TimestampMixin):
    __tablename__ = "job_description_negative_cache"
    __table_args__ = (
        Index("ix_job_description_negative_cache_retry_after", "retry_after_at"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("jobs.job_id", ondelete="CASCADE"),
        primary_key=True,
    )
    failure_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    retry_after_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    job: Mapped["Job"] = relationship(back_populates="description_negative_cache")
