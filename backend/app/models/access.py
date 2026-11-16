from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AuditChannel, audit_channel_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class ApiToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_tokens"
    __table_args__ = (Index("ix_api_tokens_token_prefix", "token_prefix"),)

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    token_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'::text[]"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_ip: Mapped[str | None] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)


class ApiAuditLog(UUIDPrimaryKeyMixin, Base):
    """External REST and MCP calls. request_summary must never contain document content."""

    __tablename__ = "api_audit_logs"
    __table_args__ = (
        CheckConstraint("duration_ms >= 0", name="duration_nonnegative"),
        Index("ix_api_audit_logs_created_at", "created_at"),
        Index("ix_api_audit_logs_user_id_created_at", "user_id", "created_at"),
    )

    token_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("api_tokens.id", ondelete="SET NULL"), index=True)
    oauth_client_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("oauth_clients.id", ondelete="SET NULL")
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    channel: Mapped[AuditChannel] = mapped_column(audit_channel_enum, nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    ip: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    request_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()"))


class OrgSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Single-row organization policy for external access."""

    __tablename__ = "org_settings"
    __table_args__ = (
        CheckConstraint("singleton", name="singleton"),
        CheckConstraint("max_token_days > 0", name="max_token_days_positive"),
    )

    external_ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    allow_write_scopes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    max_token_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365, server_default=text("365"))
    singleton: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"), unique=True)
