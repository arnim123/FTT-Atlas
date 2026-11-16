from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ActorChannel, actor_channel_enum
from app.models.base import Base, UUIDPrimaryKeyMixin, utcnow


class SearchLog(UUIDPrimaryKeyMixin, Base):
    """One row per search. The query is the caller's text, never document content."""

    __tablename__ = "search_logs"
    __table_args__ = (
        CheckConstraint("result_count >= 0", name="result_count_nonnegative"),
        Index("ix_search_logs_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[ActorChannel] = mapped_column(actor_channel_enum, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
