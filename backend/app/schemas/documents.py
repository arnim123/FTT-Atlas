from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import get_settings
from app.core.enums import AccessGrant, DocumentStatus, DriveSyncStatus, SourceType, Visibility
from app.schemas.permissions import AccessName

_DOCUMENT_ID = "55555555-5555-4555-8555-555555555555"
_FOLDER_ID = "22222222-2222-4222-8222-222222222222"
_CATEGORY_ID = "66666666-6666-4666-8666-666666666666"
_DEPARTMENT_ID = "33333333-3333-4333-8333-333333333333"
_OWNER_ID = "44444444-4444-4444-8444-444444444444"


def _strip(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class TagBrief(BaseModel):
    id: UUID
    name: str


class DocumentCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Inventory handbook",
                    "description": "How the warehouse counts stock.",
                    "folder_id": _FOLDER_ID,
                    "category_id": _CATEGORY_ID,
                    "department_id": _DEPARTMENT_ID,
                    "source_type": "pdf",
                    "visibility": "department",
                    "default_access": "view",
                    "tag_ids": [],
                }
            ]
        }
    )

    name: str = Field(min_length=1, max_length=300, examples=["Inventory handbook"])
    description: str | None = Field(default=None, max_length=8000)
    folder_id: UUID
    category_id: UUID
    department_id: UUID
    source_type: SourceType
    visibility: Visibility = Visibility.department
    default_access: AccessGrant = AccessGrant.view
    tag_ids: list[UUID] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return _strip(value)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return _blank_to_none(value)


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"name": "Inventory handbook (revised)", "description": "Updated count process."}]}
    )

    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=8000)
    category_id: UUID | None = None
    department_id: UUID | None = None
    tag_ids: list[UUID] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return _strip(value)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def at_least_one(self) -> "DocumentUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide a field to update.")
        return self


class DocumentMove(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"folder_id": _FOLDER_ID}]})

    folder_id: UUID


class DocumentRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": _DOCUMENT_ID,
                    "name": "Inventory handbook",
                    "description": "How the warehouse counts stock.",
                    "folder_id": _FOLDER_ID,
                    "category_id": _CATEGORY_ID,
                    "department_id": _DEPARTMENT_ID,
                    "owner_id": _OWNER_ID,
                    "source_type": "pdf",
                    "mime_type": "application/pdf",
                    "original_filename": "handbook.pdf",
                    "size_bytes": 12000,
                    "current_version_number": 1,
                    "has_file": True,
                    "file_url": f"/api/v1/documents/{_DOCUMENT_ID}/file",
                    "visibility": "department",
                    "default_access": "view",
                    "status": "active",
                    "archived_at": None,
                    "tags": [{"id": "77777777-7777-4777-8777-777777777777", "name": "Inventory"}],
                    "my_access": "view",
                    "web_url": f"https://atlas.example/documents/{_DOCUMENT_ID}",
                    "google_web_url": None,
                    "last_modified_at": "2026-11-16T09:00:00Z",
                    "created_at": "2026-11-16T09:00:00Z",
                    "updated_at": "2026-11-16T09:00:00Z",
                }
            ]
        }
    )

    id: UUID
    name: str
    description: str | None
    folder_id: UUID
    category_id: UUID
    department_id: UUID
    owner_id: UUID
    source_type: SourceType
    mime_type: str | None
    original_filename: str | None
    size_bytes: int | None
    current_version_number: int
    has_file: bool
    file_url: str | None
    visibility: Visibility
    default_access: AccessGrant
    status: DocumentStatus
    archived_at: datetime | None
    tags: list[TagBrief]
    my_access: AccessName
    web_url: str
    google_web_url: str | None
    drive_sync_status: DriveSyncStatus
    drive_sync_error: str | None = None
    last_modified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentPage(BaseModel):
    items: list[DocumentRead]
    total: int
    page: int
    page_size: int


class VersionRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "88888888-8888-4888-8888-888888888888",
                    "version_number": 2,
                    "original_filename": "handbook.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 14000,
                    "uploaded_by": _OWNER_ID,
                    "change_note": "Restored from version 1",
                    "created_at": "2026-11-16T10:00:00Z",
                    "download_url": f"/api/v1/documents/{_DOCUMENT_ID}/versions/2/file",
                }
            ]
        }
    )

    id: UUID
    version_number: int
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    uploaded_by: UUID | None
    change_note: str | None
    created_at: datetime
    download_url: str


class VersionRestore(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"change_note": "Restored the approved copy"}]})

    change_note: str | None = Field(default=None, max_length=500)

    @field_validator("change_note", mode="before")
    @classmethod
    def strip_note(cls, value: object) -> object:
        return _blank_to_none(value)


class GoogleMetadata(BaseModel):
    """Catalog fields stored on the Atlas document. The Drive folder is not one of them."""

    name: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=8000)
    folder_id: UUID | None = None
    category_id: UUID
    department_id: UUID
    visibility: Visibility = Visibility.department
    default_access: AccessGrant = AccessGrant.view
    tag_ids: list[UUID] = Field(default_factory=list)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class GoogleLinkCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "url": "https://docs.google.com/document/u/0/d/1AbCdEfGhIjKlMnOpQrStUvWxYz12/edit?usp=sharing",
                    "metadata": {
                        "folder_id": _FOLDER_ID,
                        "category_id": _CATEGORY_ID,
                        "department_id": _DEPARTMENT_ID,
                        "visibility": "department",
                        "default_access": "view",
                    },
                }
            ]
        }
    )

    url: str = Field(min_length=1)
    metadata: GoogleMetadata

    @field_validator("url", mode="before")
    @classmethod
    def strip_url(cls, value: object) -> object:
        return _strip(value)

    @model_validator(mode="after")
    def folder_is_required(self) -> "GoogleLinkCreate":
        if self.metadata.folder_id is None:
            raise ValueError("Choose a folder for this document.")
        return self


class GoogleFileCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Q4 roadmap",
                    "type": "sheet",
                    "template": None,
                    "folder_id": _FOLDER_ID,
                    "metadata": {
                        "category_id": _CATEGORY_ID,
                        "department_id": _DEPARTMENT_ID,
                        "visibility": "organization",
                        "default_access": "view",
                    },
                }
            ]
        }
    )

    title: str = Field(min_length=1, max_length=300)
    type: Literal["doc", "sheet", "slide"]
    template: str | None = None
    folder_id: UUID
    metadata: GoogleMetadata

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: object) -> object:
        return _strip(value)

    @field_validator("template", mode="before")
    @classmethod
    def strip_template(cls, value: object) -> object:
        return _blank_to_none(value)


class GooglePreviewRequest(BaseModel):
    url: str = Field(min_length=1)

    @field_validator("url", mode="before")
    @classmethod
    def strip_url(cls, value: object) -> object:
        return _strip(value)


class GooglePreviewRead(BaseModel):
    shared: bool
    file_id: str | None = None
    name: str | None = None
    service_account_email: str


class EmbedRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "preview_url": "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz12/preview",
                    "edit_url": "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz12/edit",
                    "open_url": "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz12/edit",
                }
            ]
        }
    )

    preview_url: str
    edit_url: str | None
    open_url: str


class DriveSyncRead(BaseModel):
    drive_sync_status: DriveSyncStatus
    drive_sync_error: str | None


def document_web_url(document_id: UUID) -> str:
    base = get_settings().public_app_url.rstrip("/")
    return f"{base}/documents/{document_id}"


def to_document_read(document, tags, my_access: AccessName) -> DocumentRead:
    has_file = bool(document.storage_key)
    return DocumentRead(
        id=document.id,
        name=document.name,
        description=document.description,
        folder_id=document.folder_id,
        category_id=document.category_id,
        department_id=document.department_id,
        owner_id=document.owner_id,
        source_type=document.source_type,
        mime_type=document.mime_type,
        original_filename=document.original_filename,
        size_bytes=document.size_bytes,
        current_version_number=document.current_version_number,
        has_file=has_file,
        file_url=f"/api/v1/documents/{document.id}/file" if has_file else None,
        visibility=document.visibility,
        default_access=document.default_access,
        status=document.status,
        archived_at=document.archived_at,
        tags=[TagBrief(id=tag.id, name=tag.name) for tag in tags],
        my_access=my_access,
        web_url=document_web_url(document.id),
        google_web_url=document.google_web_url,
        drive_sync_status=document.drive_sync_status,
        drive_sync_error=document.drive_sync_error,
        last_modified_at=document.last_modified_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def to_version_read(document_id: UUID, version) -> VersionRead:
    return VersionRead(
        id=version.id,
        version_number=version.version_number,
        original_filename=version.original_filename,
        mime_type=version.mime_type,
        size_bytes=version.size_bytes,
        uploaded_by=version.uploaded_by,
        change_note=version.change_note,
        created_at=version.created_at,
        download_url=f"/api/v1/documents/{document_id}/versions/{version.version_number}/file",
    )
