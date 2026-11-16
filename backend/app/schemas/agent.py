"""Stable, flat shapes returned to external agents."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.permissions import AccessName


class TagRef(BaseModel):
    id: UUID
    name: str


class NameRef(BaseModel):
    id: UUID
    name: str


class AgentDocument(BaseModel):
    id: UUID
    name: str
    description: str | None
    path: str
    source_type: str
    mime_type: str | None
    tags: list[TagRef]
    category: NameRef | None
    department: NameRef | None
    owner_name: str
    version: int
    last_modified_at: datetime | None
    my_access: AccessName
    web_url: str
    google_url: str | None
    content_available: bool


class AgentSearchHit(AgentDocument):
    snippet: str = ""


class AgentRelatedItem(AgentDocument):
    score: float
    reasons: list[str]


class AgentPage(BaseModel):
    items: list[AgentSearchHit]
    next_cursor: str | None = None


class AgentRelatedPage(BaseModel):
    items: list[AgentRelatedItem]


class AgentContent(BaseModel):
    notice: str
    document_content: str | None = None
    offset: int
    next_offset: int | None = None
    total_chars: int
    truncated: bool
    extraction_status: str
    detail: str | None = None


class AgentIdentity(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    is_bot: bool
    department_id: UUID
    scopes: list[str]
    auth_method: str
    token_id: UUID | None = None
    client_name: str | None = None


class TaxonomyEntry(BaseModel):
    id: UUID
    name: str
    code: str | None = None


class AgentTaxonomy(BaseModel):
    departments: list[TaxonomyEntry]
    categories: list[TaxonomyEntry]
    tags: list[TaxonomyEntry]


class AgentFolder(BaseModel):
    id: UUID
    name: str
    path: str | None = None
    my_access: str
    path_only: bool
    children: list["AgentFolder"] = Field(default_factory=list)


class DownloadLink(BaseModel):
    url: str
    expires_at: datetime


class AgentFolderPage(BaseModel):
    items: list[AgentFolder]
