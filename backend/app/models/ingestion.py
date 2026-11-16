from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import JobStatus, job_status_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IngestionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (CheckConstraint("attempts >= 0", name="attempts_nonnegative"),)

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        job_status_enum, nullable=False, default=JobStatus.pending, server_default=text("'pending'::job_status")
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    run_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
