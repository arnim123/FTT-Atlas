"""Tokens, organization policy, and external audit rows."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import AuditChannel
from app.models.access import ApiAuditLog, ApiToken, OrgSettings


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[str] | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)
    user_id: UUID | None = None


class TokenRead(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    token_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    last_used_ip: str | None
    revoked_at: datetime | None
    created_at: datetime


class TokenCreated(TokenRead):
    token: str


class TokenPage(BaseModel):
    items: list[TokenRead]


class OrgSettingsRead(BaseModel):
    external_ai_enabled: bool
    allow_write_scopes: bool
    max_token_days: int


class OrgSettingsUpdate(BaseModel):
    external_ai_enabled: bool | None = None
    allow_write_scopes: bool | None = None
    max_token_days: int | None = Field(default=None, ge=1, le=3650)


class AuditRead(BaseModel):
    id: UUID
    token_id: UUID | None
    oauth_client_id: UUID | None = None
    user_id: UUID
    channel: AuditChannel
    operation: str
    status_code: int
    duration_ms: int
    ip: str | None
    user_agent: str | None
    request_summary: dict
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditRead]
    next_cursor: str | None = None


def to_token_read(row: ApiToken) -> TokenRead:
    return TokenRead(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        token_prefix=row.token_prefix,
        scopes=list(row.scopes),
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        last_used_ip=row.last_used_ip,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


def to_token_created(row: ApiToken, secret: str) -> TokenCreated:
    return TokenCreated(**to_token_read(row).model_dump(), token=secret)


def to_org_settings(row: OrgSettings) -> OrgSettingsRead:
    return OrgSettingsRead(
        external_ai_enabled=row.external_ai_enabled,
        allow_write_scopes=row.allow_write_scopes,
        max_token_days=row.max_token_days,
    )


def to_audit(row: ApiAuditLog) -> AuditRead:
    return AuditRead(
        id=row.id,
        token_id=row.token_id,
        oauth_client_id=row.oauth_client_id,
        user_id=row.user_id,
        channel=row.channel,
        operation=row.operation,
        status_code=row.status_code,
        duration_ms=row.duration_ms,
        ip=row.ip,
        user_agent=row.user_agent,
        request_summary=row.request_summary or {},
        created_at=row.created_at,
    )
