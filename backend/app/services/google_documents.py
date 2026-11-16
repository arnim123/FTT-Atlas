"""Link, create, embed, and delete Google files.

Routers and future MCP tools call these functions. Drive sharing is pushed
by the handlers in `drive_sync` after the commit, using the same database rows.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import (
    DocumentStatus,
    DriveSyncStatus,
    EventType,
    ExtractionStatus,
    SourceType,
    UserRole,
)
from app.core.errors import ApiError
from app.core.events import DOCUMENT_CREATED, DOCUMENT_DELETED, GOOGLE_MODIFIED
from app.core.principal import AuthMethod, Principal
from app.integrations.drive import (
    MIME_BY_SOURCE,
    DriveError,
    DriveForbidden,
    DriveNotFound,
    GoogleDriveClient,
    InvalidGoogleUrl,
    build_drive_client,
    google_urls,
    parse_google_file_reference,
    parse_google_url,
    shared_drive_folder_id,
)
from app.integrations.drive_sync import GOOGLE_SOURCES, sync_document_sharing
from app.models.base import utcnow
from app.models.document import Document
from app.models.permission import DocumentPermission
from app.permissions.engine import access_level
from app.schemas.documents import GoogleFileCreate, GoogleLinkCreate
from app.services.activity import commit_and_emit, record_document_event
from app.services.documents import (
    DocumentResult,
    _commit_document,
    _one,
    _replace_tags,
    _require_category,
    _require_department,
    require_document,
)
from app.services.folders import require_folder
from app.services.grants import load_grants
from app.services.search import refresh_search_vector

_ADMIN_ROLES = {UserRole.super_admin, UserRole.admin}


@dataclass(frozen=True)
class EmbedLinks:
    preview_url: str
    edit_url: str | None
    open_url: str


def link_google_document(session: Session, principal: Principal, payload: GoogleLinkCreate) -> DocumentResult:
    """Register a file the service account can already open. The Atlas folder is only a catalog location."""
    try:
        parsed = parse_google_url(payload.url)
    except InvalidGoogleUrl as exc:
        raise ApiError(422, "INVALID_GOOGLE_URL", "Enter a Google Docs, Sheets, or Slides link.") from exc
    folder_id = payload.metadata.folder_id
    if folder_id is None:
        raise ApiError(422, "INVALID_FOLDER", "Choose a folder for this document.")
    require_folder(session, principal, folder_id, "edit")
    _require_category(session, payload.metadata.category_id)
    _require_department(session, payload.metadata.department_id)
    _reject_duplicate(session, parsed.file_id)

    client = build_drive_client()
    metadata = _opened_file(client, parsed.file_id)
    if metadata.trashed:
        raise _not_shared(client, parsed.file_id, "This Google file is in the trash. Restore it in Drive, then link it again.")
    expected = MIME_BY_SOURCE[parsed.source_type]
    if metadata.mime_type != expected:
        raise ApiError(422, "GOOGLE_TYPE_MISMATCH", "That link points at a different kind of Google file.")

    document = _new_document(
        principal,
        name=_document_name(payload.metadata.name, metadata.name),
        description=payload.metadata.description,
        folder_id=folder_id,
        category_id=payload.metadata.category_id,
        department_id=payload.metadata.department_id,
        source_type=parsed.source_type,
        visibility=payload.metadata.visibility,
        default_access=payload.metadata.default_access,
        file_id=parsed.file_id,
        mime_type=metadata.mime_type,
    )
    _save_new_document(session, principal, document, payload.metadata.tag_ids, client=None, created_file_id=None)
    return _one(session, principal, document)


def create_google_document(session: Session, principal: Principal, payload: GoogleFileCreate) -> DocumentResult:
    """Create a file in the Shared Drive and register it. Atlas folders stay virtual."""
    require_folder(session, principal, payload.folder_id, "edit")
    _require_category(session, payload.metadata.category_id)
    _require_department(session, payload.metadata.department_id)
    source_type = _source_for(payload.type)
    mime_type = MIME_BY_SOURCE[source_type]
    client = build_drive_client()
    template_id = _template_id(client, payload.template, mime_type)
    try:
        created = client.create_file(
            title=payload.title.strip(),
            mime_type=mime_type,
            folder_id=shared_drive_folder_id(),
            template_id=template_id,
        )
    except (DriveNotFound, DriveForbidden) as exc:
        raise _not_shared(client, template_id or "", "Share the template with the service account, then try again.") from exc
    except DriveError as exc:
        raise ApiError(503, "DRIVE_UNAVAILABLE", "Google Drive is temporarily unavailable. Try again shortly.") from exc

    document = _new_document(
        principal,
        name=payload.title.strip(),
        description=payload.metadata.description,
        folder_id=payload.folder_id,
        category_id=payload.metadata.category_id,
        department_id=payload.metadata.department_id,
        source_type=source_type,
        visibility=payload.metadata.visibility,
        default_access=payload.metadata.default_access,
        file_id=created.id,
        mime_type=created.mime_type or mime_type,
    )
    _save_new_document(session, principal, document, payload.metadata.tag_ids, client=client, created_file_id=created.id)
    return _one(session, principal, document)


def embed_document(session: Session, principal: Principal, document_id: UUID) -> EmbedLinks:
    """Preview and open links. `edit_url` is present only when the caller can edit."""
    document = require_document(session, principal, document_id, "view")
    if document.source_type not in GOOGLE_SOURCES or not document.google_file_id:
        raise ApiError(409, "NOT_A_GOOGLE_FILE", "This document is not a Google file.")
    grants = load_grants(session, DocumentPermission, document.id)
    level = access_level(principal.user, document, grants, principal.scopes)
    record_document_event(session, principal, document.id, EventType.view, {"surface": "embed"})
    modified = _refresh_if_drive_is_newer(session, document, build_drive_client())
    if modified:
        commit_and_emit(session, GOOGLE_MODIFIED, document_id=str(document.id))
    else:
        commit_and_emit(session)
    urls = google_urls(document.source_type, document.google_file_id)
    open_url = document.google_web_url or urls.open_url
    return EmbedLinks(
        preview_url=urls.preview_url,
        edit_url=urls.edit_url if level in {"edit", "manage"} else None,
        open_url=open_url,
    )


def resync_document(session: Session, principal: Principal, document_id: UUID) -> Document:
    """Push shares for one file again. Requires manage permission on the document."""
    document = require_document(session, principal, document_id, "manage")
    if document.source_type not in GOOGLE_SOURCES or not document.google_file_id:
        raise ApiError(409, "NOT_A_GOOGLE_FILE", "This document is not a Google file.")
    sync_document_sharing(session, document)
    commit_and_emit(session)
    return document


def permanently_delete_document(session: Session, principal: Principal, document_id: UUID) -> None:
    """Admin-only delete from the archive. A linked Google file is moved to trash."""
    document = require_document(session, principal, document_id, "manage")
    if document.status != DocumentStatus.archived:
        raise ApiError(409, "NOT_ARCHIVED", "Permanent delete is available from the archive.")
    if principal.auth_method is not AuthMethod.session:
        raise ApiError(403, "SESSION_REQUIRED", "Permanent delete is only available in the signed-in app.")
    if principal.user.role not in _ADMIN_ROLES:
        raise ApiError(403, "FORBIDDEN", "Only an admin can permanently delete a document.")
    if document.google_file_id and document.source_type in GOOGLE_SOURCES:
        client = build_drive_client()
        try:
            client.trash_file(document.google_file_id)
        except DriveNotFound:
            pass
        except DriveError as exc:
            raise ApiError(502, "DRIVE_ERROR", "The Google file could not be moved to trash.") from exc
        document.drive_sync_status = DriveSyncStatus.synced
        document.drive_sync_error = None
    document.deleted_at = utcnow()
    record_document_event(session, principal, document.id, EventType.delete, {"permanent": True})
    _commit_document(session, DOCUMENT_DELETED, document, principal, permanent=True)


def _save_new_document(
    session: Session,
    principal: Principal,
    document: Document,
    tag_ids: list[UUID],
    *,
    client: GoogleDriveClient | None,
    created_file_id: str | None,
) -> None:
    saved = False
    try:
        session.add(document)
        session.flush()
        if tag_ids:
            _replace_tags(session, document.id, tag_ids)
        session.flush()
        refresh_search_vector(session, document.id)
        record_document_event(
            session,
            principal,
            document.id,
            EventType.create,
            {"source_type": document.source_type.value, "google_file_id": document.google_file_id},
        )
        _commit_document(session, DOCUMENT_CREATED, document, principal)
        saved = True
    except IntegrityError as exc:
        session.rollback()
        existing = _existing(session, document.google_file_id)
        if existing is not None:
            raise ApiError(
                409,
                "DUPLICATE_GOOGLE_FILE",
                "This Google file is already linked.",
                details={"document_id": str(existing.id)},
            ) from exc
        raise ApiError(409, "CONFLICT", "The change conflicts with an existing record.") from exc
    except Exception:
        if not saved:
            session.rollback()
        raise
    finally:
        if not saved and client is not None and created_file_id:
            try:
                client.trash_file(created_file_id)
            except DriveError:
                pass


def _new_document(principal: Principal, **fields) -> Document:
    source_type: SourceType = fields["source_type"]
    file_id: str = fields["file_id"]
    return Document(
        name=fields["name"],
        description=fields["description"],
        folder_id=fields["folder_id"],
        category_id=fields["category_id"],
        department_id=fields["department_id"],
        owner_id=principal.user.id,
        source_type=source_type,
        google_file_id=file_id,
        google_mime_type=fields["mime_type"],
        google_web_url=google_urls(source_type, file_id).edit_url,
        visibility=fields["visibility"],
        default_access=fields["default_access"],
        status=DocumentStatus.active,
        drive_sync_status=DriveSyncStatus.pending,
        last_modified_at=utcnow(),
    )


def preview_google_link(url: str) -> dict:
    """Say whether the service account can open a Docs, Sheets, or Slides URL."""
    client = build_drive_client()
    try:
        parsed = parse_google_url(url.strip())
    except InvalidGoogleUrl as exc:
        raise ApiError(422, "INVALID_GOOGLE_URL", "Enter a valid Google Docs, Sheets, or Slides URL.") from exc
    email = client.service_account_email
    try:
        metadata = client.get_file_metadata(parsed.file_id)
    except DriveNotFound:
        return {"shared": False, "file_id": parsed.file_id, "name": None, "service_account_email": email}
    except DriveForbidden:
        return {"shared": False, "file_id": parsed.file_id, "name": None, "service_account_email": email}
    except DriveError as exc:
        raise ApiError(503, "DRIVE_UNAVAILABLE", "Google Drive is temporarily unavailable. Try again shortly.") from exc
    if metadata.trashed:
        return {"shared": False, "file_id": parsed.file_id, "name": metadata.name, "service_account_email": email}
    return {"shared": True, "file_id": parsed.file_id, "name": metadata.name, "service_account_email": email}


def _opened_file(client: GoogleDriveClient, file_id: str):
    try:
        return client.get_file_metadata(file_id)
    except (DriveNotFound, DriveForbidden) as exc:
        raise _not_shared(client, file_id) from exc
    except DriveError as exc:
        raise ApiError(503, "DRIVE_UNAVAILABLE", "Google Drive is temporarily unavailable. Try again shortly.") from exc


def _template_id(client: GoogleDriveClient, template: str | None, mime_type: str) -> str | None:
    if template is None or not template.strip():
        return None
    try:
        file_id = parse_google_file_reference(template)
    except InvalidGoogleUrl as exc:
        raise ApiError(422, "INVALID_GOOGLE_URL", "Enter a Google file id or a Docs, Sheets, or Slides link.") from exc
    metadata = _opened_file(client, file_id)
    if metadata.mime_type != mime_type:
        raise ApiError(422, "GOOGLE_TYPE_MISMATCH", "The template has to be the same kind of Google file.")
    return file_id


def _refresh_if_drive_is_newer(session: Session, document: Document, client: GoogleDriveClient) -> bool:
    """Mark the document for extraction when Drive's modifiedTime moved forward.

    The ingestion handler enqueues the job after this transaction commits.
    """
    if not document.google_file_id:
        return False
    try:
        metadata = client.get_file_metadata(document.google_file_id)
    except DriveError:
        return False
    modified = metadata.modified_time
    if modified is None:
        return False
    modified = modified if modified.tzinfo is not None else modified.replace(tzinfo=UTC)
    current = document.last_modified_at
    if current is not None:
        current = current if current.tzinfo is not None else current.replace(tzinfo=UTC)
        if current >= modified:
            return False
    document.last_modified_at = modified.astimezone(UTC)
    document.extraction_status = ExtractionStatus.pending
    document.extraction_error = None
    return True


def _reject_duplicate(session: Session, file_id: str) -> None:
    existing = _existing(session, file_id)
    if existing is not None:
        raise ApiError(
            409,
            "DUPLICATE_GOOGLE_FILE",
            "This Google file is already linked.",
            details={"document_id": str(existing.id)},
        )


def _existing(session: Session, file_id: str | None) -> Document | None:
    if not file_id:
        return None
    return session.scalar(select(Document).where(Document.google_file_id == file_id))


def _not_shared(client: GoogleDriveClient, file_id: str, message: str | None = None) -> ApiError:
    email = client.service_account_email
    return ApiError(
        422,
        "GOOGLE_NOT_SHARED",
        message or f"Share the file with {email} as a viewer or editor, then try again.",
        details={"service_account_email": email, "google_file_id": file_id},
    )


def _document_name(preferred: str | None, fallback: str | None) -> str:
    raw = (preferred or fallback or "Untitled").strip() or "Untitled"
    return raw[:300]


def _source_for(kind: str) -> SourceType:
    return {"doc": SourceType.google_doc, "sheet": SourceType.google_sheet, "slide": SourceType.google_slide}[kind]
