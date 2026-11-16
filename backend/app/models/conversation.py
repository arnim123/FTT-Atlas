from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ConversationScope, MessageRole, conversation_scope_enum, message_role_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AiConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Created for Phase 2. Unused by Phase 1 behavior."""

    __tablename__ = "ai_conversations"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'organization'::conversation_scope AND document_id IS NULL) "
            "OR (scope = 'document'::conversation_scope AND document_id IS NOT NULL)",
            name="scope_document",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    scope: Mapped[ConversationScope] = mapped_column(conversation_scope_enum, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)


class AiMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Created for Phase 2. Unused by Phase 1 behavior."""

    __tablename__ = "ai_messages"

    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(message_role_enum, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
