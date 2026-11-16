"""OAuth clients, grants, authorization codes, and hashed tokens."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OAuthClient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    client_secret_hash: Mapped[str | None] = mapped_column(Text)
    client_name: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    grant_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    response_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    token_endpoint_auth_method: Mapped[str] = mapped_column(Text, nullable=False)
    registration_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_ip: Mapped[str | None] = mapped_column(Text, index=True)


class OAuthGrant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_grants"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    oauth_client_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("oauth_clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'::text[]"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthAuthorizationCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_authorization_codes"

    oauth_client_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("oauth_clients.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    grant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("oauth_grants.id", ondelete="SET NULL")
    )
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    requested_scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    granted_scopes: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    code_challenge: Mapped[str] = mapped_column(Text, nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str | None] = mapped_column(Text)
    code_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    denied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_tokens"

    grant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("oauth_grants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    oauth_client_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("oauth_clients.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    audience: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'::text[]"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
