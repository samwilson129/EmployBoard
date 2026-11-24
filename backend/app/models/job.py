from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin
from app.models.enums import EMPLOYMENT_TYPES, EXPERIENCE_LEVELS, WORKPLACE_TYPES

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.job_source import JobSource


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{value}'" for value in values) + ")"


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            _in_clause("employment_type", EMPLOYMENT_TYPES),
            name="ck_jobs_employment_type",
        ),
        CheckConstraint(
            _in_clause("workplace_type", WORKPLACE_TYPES),
            name="ck_jobs_workplace_type",
        ),
        CheckConstraint(
            _in_clause("experience_level", EXPERIENCE_LEVELS),
            name="ck_jobs_experience_level",
        ),
        CheckConstraint(
            "salary_min IS NULL OR salary_min >= 0", name="ck_jobs_salary_min"
        ),
        CheckConstraint(
            "salary_max IS NULL OR salary_max >= 0", name="ck_jobs_salary_max"
        ),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="ck_jobs_salary_order",
        ),
        Index("ix_jobs_company_active", "company_id", "is_active"),
        Index("ix_jobs_active_posted", "is_active", text("posted_at DESC")),
        Index("ix_jobs_active_updated", "is_active", text("updated_at DESC")),
        Index("ix_jobs_employment_type", "employment_type"),
        Index("ix_jobs_workplace_type", "workplace_type"),
        Index("ix_jobs_experience_level", "experience_level"),
        Index("ix_jobs_department", "department"),
        Index("ix_jobs_location", "location"),
        Index("ix_jobs_normalized_title", "normalized_title"),
        Index("ix_jobs_normalized_location", "normalized_location"),
        Index("ix_jobs_skills", "skills", postgresql_using="gin"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requisition_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workplace_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(32), nullable=True)

    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    salary_interval: Mapped[str | None] = mapped_column(String(32), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    application_url: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    missing_sync_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    duplicate_of_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("jobs.job_id", ondelete="SET NULL"),
        nullable=True,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    company: Mapped["Company"] = relationship(back_populates="jobs")
    sources: Mapped[list["JobSource"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def source_providers(self) -> list[str]:
        return sorted({source.ats_provider for source in self.sources})

    @property
    def last_verified_at(self) -> datetime | None:
        values = [
            source.last_verified_at or source.fetched_at for source in self.sources
        ]
        return max(values) if values else None

    @property
    def metadata_json(self) -> dict[str, Any]:
        return {"missing_sync_count": self.missing_sync_count}
