"""Consent and connected-app payloads for the OAuth UI."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConsentView(BaseModel):
    request_id: UUID
    app_name: str
    redirect_domain: str
    redirect_uri: str
    verified: bool
    localhost_redirect: bool
    scopes: list[str]
    write_requested: bool
    allow_write: bool
    external_access: bool
    user_name: str


class ConsentSubmit(BaseModel):
    request_id: UUID
    decision: str = Field(pattern="^(allow|deny)$")
    scopes: list[str] = Field(default_factory=list, max_length=2)


class ConsentResult(BaseModel):
    decision: str
    redirect_to: str


class OAuthGrantRead(BaseModel):
    id: UUID
    user_id: UUID
    client_name: str
    client_id: str
    redirect_domain: str
    verified: bool
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class OAuthGrantPage(BaseModel):
    items: list[OAuthGrantRead]
