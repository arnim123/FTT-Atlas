from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ActorChannel, EventType, actor_channel_enum, event_type_enum
from app.models.base import Base, UUIDPrimaryKeyMixin, utcnow


class DocumentEvent(UUIDPrimaryKeyMixin, Base):
    """Audit trail and the source for dashboard activity. Append-only."""

    __tablename__ = "document_events"
    __table_args__ = (Index("ix_document_events_document_id_created_at", "document_id", "created_at"),)

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[EventType] = mapped_column(event_type_enum, nullable=False)
    actor_channel: Mapped[ActorChannel] = mapped_column(actor_channel_enum, nullable=False)
    token_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("api_tokens.id", ondelete="SET NULL"), index=True
    )
    client_name: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()"))
