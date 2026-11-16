"""Documents, uploaded files, and versions.

List and get go through `accessible_documents_query`. A caller who cannot view
a document gets 404. Mutations require edit or manage on top of that, and the
router requires `docs:write`. Archived documents accept restore, delete, and
permission changes; other writes wait until the document is restored.

Uploads are sniffed before they are stored. A new version is a new object key.
Restoring an old version copies its bytes into a new version and leaves the
old row in place. Search vectors are refreshed after name, description, tag,
or category changes. Every recorded action copies the principal's channel,
token, and client name onto `document_events`.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import DocumentStatus, DriveSyncStatus, EventType, SourceType
from app.core.errors import ApiError
from app.core.events import (
    DOCUMENT_ARCHIVED,
    DOCUMENT_CREATED,
    DOCUMENT_DELETED,
    DOCUMENT_PERMISSIONS_CHANGED,
    DOCUMENT_RESTORED,
    DOCUMENT_UPDATED,
    DOCUMENT_VERSION_ADDED,
)
from app.core.principal import Principal
from app.integrations.storage import (
    StorageBackend,
    StorageError,
    detect_file,
    filename_for,
)
from app.models.base import utcnow
from app.models.department import Department
from app.models.document import Document, DocumentVersion
from app.models.event import DocumentEvent
from app.models.folder import Folder
from app.models.permission import DocumentPermission
from app.models.taxonomy import Category, DocumentTag, Tag
from app.permissions.engine import access_level, accessible_documents_query, accessible_folders_query, can
from app.schemas.documents import DocumentCreate, DocumentUpdate
from app.schemas.permissions import AccessName, PermissionsUpdate
from app.services.activity import commit_and_emit, emit_with_session, record_document_event
from app.services.folders import require_folder
from app.services.grants import load_grants, load_grants_for, replace_grants, validate_grants
from app.services.search import refresh_search_vector

_GOOGLE = {SourceType.google_doc, SourceType.google_sheet, SourceType.google_slide}
_ORDER = {
    "name": (Document.name.asc(), Document.id.asc()),
    "oldest": (Document.created_at.asc(), Document.id.asc()),
    "created": (Document.created_at.desc(), Document.id.desc()),
    "size": (Document.size_bytes.desc().nulls_last(), Document.id.asc()),
    "modified": (Document.last_modified_at.desc().nulls_last(), Document.id.desc()),
}


@dataclass(frozen=True)
class DocumentFilters:
    folder_id: UUID | None = None
    department_id: UUID | None = None
    category_id: UUID | None = None
    tag_ids: tuple[UUID, ...] = ()
    source_type: SourceType | None = None
    owner_id: UUID | None = None
    status: str = "active"
    sort: str = "modified"
    page: int = 1
    page_size: int = 50


@dataclass
class DocumentResult:
    document: Document
    tags: list[Tag]
    my_access: AccessName


@dataclass
class DocumentPageResult:
    items: list[DocumentResult]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class FileDownload:
    storage_key: str
    mime_type: str
    filename: str
    inline: bool
    size_bytes: int | None


def list_documents(session: Session, principal: Principal, filters: DocumentFilters) -> DocumentPageResult:
    criteria = [accessible_documents_query(principal.user, principal.scopes)]
    if filters.folder_id is not None:
        _require_listed_folder(session, principal, filters.folder_id)
        criteria.append(Document.folder_id == filters.folder_id)
    if filters.department_id is not None:
        criteria.append(Document.department_id == filters.department_id)
    if filters.category_id is not None:
        criteria.append(Document.category_id == filters.category_id)
    if filters.owner_id is not None:
        criteria.append(Document.owner_id == filters.owner_id)
    if filters.source_type is not None:
        criteria.append(Document.source_type == filters.source_type)
    if filters.status == "active":
        criteria.append(Document.status == DocumentStatus.active)
    elif filters.status == "archived":
        criteria.append(Document.status == DocumentStatus.archived)
    for tag_id in filters.tag_ids:
        criteria.append(
            exists(
                select(DocumentTag.id).where(
                    DocumentTag.document_id == Document.id,
                    DocumentTag.tag_id == tag_id,
                )
            )
        )
    total = session.scalar(select(func.count()).select_from(Document).where(*criteria)) or 0
    rows = list(
        session.scalars(
            select(Document)
            .where(*criteria)
            .order_by(*_ORDER.get(filters.sort, _ORDER["modified"]))
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
    )
    return DocumentPageResult(
        items=_results(session, principal, rows),
        total=total,
        page=filters.page,
        page_size=filters.page_size,
    )


def create_document(session: Session, principal: Principal, payload: DocumentCreate) -> DocumentResult:
    require_folder(session, principal, payload.folder_id, "edit")
    _require_category(session, payload.category_id)
    _require_department(session, payload.department_id)
    document = Document(
        name=payload.name,
        description=payload.description,
        folder_id=payload.folder_id,
        category_id=payload.category_id,
        department_id=payload.department_id,
        owner_id=principal.user.id,
        source_type=payload.source_type,
        visibility=payload.visibility,
        default_access=payload.default_access,
        status=DocumentStatus.active,
        drive_sync_status=DriveSyncStatus.not_applicable,
        last_modified_at=utcnow(),
    )
    session.add(document)
    session.flush()
    if payload.tag_ids:
        _replace_tags(session, document.id, payload.tag_ids)
    session.flush()
    refresh_search_vector(session, document.id)
    record_document_event(session, principal, document.id, EventType.create, {"source_type": payload.source_type.value})
    _commit_document(session, DOCUMENT_CREATED, document, principal)
    return _one(session, principal, document)


def create_upload(
    session: Session,
    principal: Principal,
    storage: StorageBackend,
    *,
    name: str,
    description: str | None,
    folder_id: UUID,
    category_id: UUID,
    department_id: UUID,
    visibility,
    default_access,
    tag_ids: list[UUID],
    filename: str | None,
    content: bytes,
) -> DocumentResult:
    require_folder(session, principal, folder_id, "edit")
    _require_category(session, category_id)
    _require_department(session, department_id)
    detected = _detect(content)
    safe_name = filename_for(filename, detected)
    key = _save(storage, content)
    try:
        document = Document(
            name=name,
            description=description,
            folder_id=folder_id,
            category_id=category_id,
            department_id=department_id,
            owner_id=principal.user.id,
            source_type=detected.source_type,
            storage_key=key,
            original_filename=safe_name,
            mime_type=detected.mime_type,
            size_bytes=len(content),
            current_version_number=1,
            visibility=visibility,
            default_access=default_access,
            status=DocumentStatus.active,
            drive_sync_status=DriveSyncStatus.not_applicable,
            last_modified_at=utcnow(),
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentVersion(
                document_id=document.id,
                version_number=1,
                storage_key=key,
                original_filename=safe_name,
                mime_type=detected.mime_type,
                size_bytes=len(content),
                uploaded_by=principal.user.id,
                change_note="Initial upload",
            )
        )
        if tag_ids:
            _replace_tags(session, document.id, tag_ids)
        session.flush()
        refresh_search_vector(session, document.id)
        record_document_event(
            session,
            principal,
            document.id,
            EventType.create,
            {"source_type": detected.source_type.value, "version_number": 1},
        )
        session.commit()
    except IntegrityError as exc:
        _discard_upload(session, storage, key)
        raise ApiError(409, "CONFLICT", "The change conflicts with an existing record.") from exc
    except Exception:
        _discard_upload(session, storage, key)
        raise
    payload = {"document_id": str(document.id), "actor_id": str(principal.user.id), "version_number": 1}
    emit_with_session(session, DOCUMENT_CREATED, **payload)
    emit_with_session(session, DOCUMENT_VERSION_ADDED, **payload)
    return _one(session, principal, document)


def get_document(session: Session, principal: Principal, document_id: UUID) -> DocumentResult:
    document = require_document(session, principal, document_id, "view")
    record_document_event(session, principal, document.id, EventType.view, {})
    commit_and_emit(session)
    return _one(session, principal, document)


def update_document(session: Session, principal: Principal, document_id: UUID, payload: DocumentUpdate) -> DocumentResult:
    document = require_document(session, principal, document_id, "edit")
    _reject_archived(document)
    changed: list[str] = []
    search = False
    if "name" in payload.model_fields_set and payload.name is not None:
        document.name = payload.name
        changed.append("name")
        search = True
    if "description" in payload.model_fields_set:
        document.description = payload.description
        changed.append("description")
        search = True
    if "category_id" in payload.model_fields_set and payload.category_id is not None:
        _require_category(session, payload.category_id)
        document.category_id = payload.category_id
        changed.append("category")
        search = True
    if "department_id" in payload.model_fields_set and payload.department_id is not None:
        _require_department(session, payload.department_id)
        document.department_id = payload.department_id
        changed.append("department")
    if "tag_ids" in payload.model_fields_set and payload.tag_ids is not None:
        _replace_tags(session, document.id, payload.tag_ids)
        changed.append("tags")
        search = True
    document.last_modified_at = utcnow()
    if search:
        session.flush()
        refresh_search_vector(session, document.id)
    record_document_event(session, principal, document.id, EventType.update, {"fields": changed})
    _commit_document(session, DOCUMENT_UPDATED, document, principal, fields=changed)
    return _one(session, principal, document)


def move_document(session: Session, principal: Principal, document_id: UUID, folder_id: UUID) -> DocumentResult:
    document = require_document(session, principal, document_id, "edit")
    _reject_archived(document)
    if document.folder_id != folder_id:
        require_folder(session, principal, folder_id, "edit")
        document.folder_id = folder_id
        document.last_modified_at = utcnow()
        record_document_event(session, principal, document.id, EventType.move, {"folder_id": str(folder_id)})
        commit_and_emit(session)
    return _one(session, principal, document)


def archive_document(session: Session, principal: Principal, document_id: UUID) -> DocumentResult:
    document = require_document(session, principal, document_id, "manage")
    if document.status == DocumentStatus.archived:
        raise ApiError(409, "ALREADY_ARCHIVED", "This document is already archived.")
    document.status = DocumentStatus.archived
    document.archived_at = utcnow()
    document.last_modified_at = document.archived_at
    record_document_event(session, principal, document.id, EventType.archive, {})
    _commit_document(session, DOCUMENT_ARCHIVED, document, principal)
    return _one(session, principal, document)


def restore_document(session: Session, principal: Principal, document_id: UUID) -> DocumentResult:
    document = require_document(session, principal, document_id, "manage")
    if document.status != DocumentStatus.archived:
        raise ApiError(409, "NOT_ARCHIVED", "This document is not archived.")
    document.status = DocumentStatus.active
    document.archived_at = None
    document.last_modified_at = utcnow()
    record_document_event(session, principal, document.id, EventType.restore, {})
    _commit_document(session, DOCUMENT_RESTORED, document, principal)
    return _one(session, principal, document)


def delete_document(session: Session, principal: Principal, document_id: UUID) -> None:
    document = require_document(session, principal, document_id, "manage")
    document.deleted_at = utcnow()
    record_document_event(session, principal, document.id, EventType.delete, {})
    _commit_document(session, DOCUMENT_DELETED, document, principal)


def get_permissions(session: Session, principal: Principal, document_id: UUID) -> tuple[Document, list, AccessName]:
    document = require_document(session, principal, document_id, "view")
    grants = load_grants(session, DocumentPermission, document.id)
    return document, grants, access_level(principal.user, document, grants, principal.scopes)


def put_permissions(
    session: Session, principal: Principal, document_id: UUID, payload: PermissionsUpdate
) -> tuple[Document, list, AccessName]:
    document = require_document(session, principal, document_id, "manage")
    validate_grants(session, payload.grants)
    document.visibility = payload.visibility
    document.default_access = payload.default_access
    replace_grants(session, DocumentPermission, document.id, payload.grants, principal.user.id)
    record_document_event(
        session,
        principal,
        document.id,
        EventType.share,
        {
            "visibility": payload.visibility.value,
            "default_access": payload.default_access.value,
            "grant_count": len(payload.grants),
        },
    )
    _commit_document(session, DOCUMENT_PERMISSIONS_CHANGED, document, principal)
    grants = load_grants(session, DocumentPermission, document.id)
    return document, grants, access_level(principal.user, document, grants, principal.scopes)


def list_versions(session: Session, principal: Principal, document_id: UUID) -> list[DocumentVersion]:
    document = require_document(session, principal, document_id, "view")
    return list(
        session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
        )
    )


def add_version(
    session: Session,
    principal: Principal,
    storage: StorageBackend,
    document_id: UUID,
    *,
    filename: str | None,
    content: bytes,
    change_note: str | None,
) -> DocumentResult:
    document = require_document(session, principal, document_id, "edit")
    _reject_archived(document)
    _reject_google(document)
    detected = _detect(content)
    if detected.source_type != document.source_type:
        raise ApiError(415, "TYPE_MISMATCH", "The new version has to be the same type of file.")
    return _store_version(
        session,
        principal,
        storage,
        document,
        detected=detected,
        filename=filename_for(filename, detected),
        content=content,
        change_note=change_note or "New version uploaded",
        restored_from=None,
    )


def restore_version(
    session: Session,
    principal: Principal,
    storage: StorageBackend,
    document_id: UUID,
    version_number: int,
    change_note: str | None,
) -> DocumentResult:
    document = require_document(session, principal, document_id, "edit")
    _reject_archived(document)
    _reject_google(document)
    previous = _version(session, document.id, version_number)
    if not previous.storage_key or not storage.exists(previous.storage_key):
        raise ApiError(404, "NO_FILE", "This version has no uploaded file.")
    content = _read(storage, previous.storage_key)
    detected = _detect(content)
    note = change_note or f"Restored from version {previous.version_number}"
    return _store_version(
        session,
        principal,
        storage,
        document,
        detected=detected,
        filename=previous.original_filename or filename_for(None, detected),
        content=content,
        change_note=note,
        restored_from=previous.version_number,
    )


def download_file(
    session: Session,
    principal: Principal,
    storage: StorageBackend,
    document_id: UUID,
    version_number: int | None = None,
) -> FileDownload:
    document = require_document(session, principal, document_id, "view")
    if version_number is None:
        key = document.storage_key
        mime_type = document.mime_type
        filename = document.original_filename
        size_bytes = document.size_bytes
        number = document.current_version_number
    else:
        version = _version(session, document.id, version_number)
        key = version.storage_key
        mime_type = version.mime_type
        filename = version.original_filename
        size_bytes = version.size_bytes
        number = version.version_number
    if not key or not storage.exists(key):
        raise ApiError(404, "NO_FILE", "This document has no uploaded file.")
    record_document_event(session, principal, document.id, EventType.download, {"version_number": number})
    commit_and_emit(session)
    resolved_mime = mime_type or "application/octet-stream"
    return FileDownload(
        storage_key=key,
        mime_type=resolved_mime,
        filename=filename or "file",
        inline=_inline(resolved_mime),
        size_bytes=size_bytes,
    )


def require_document(session: Session, principal: Principal, document_id: UUID, action: str) -> Document:
    document = session.get(Document, document_id)
    if document is None or document.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", "Document not found.")
    grants = load_grants(session, DocumentPermission, document.id)
    if not can(principal.user, document, "view", grants, principal.scopes):
        raise ApiError(404, "NOT_FOUND", "Document not found.")
    if action != "view" and not can(principal.user, document, action, grants, principal.scopes):
        raise ApiError(403, "FORBIDDEN", "You do not have access to this action.")
    return document


def list_document_events(session: Session, principal: Principal, document_id: UUID, limit: int = 20) -> list[DocumentEvent]:
    """Recent access rows. Viewing the list does not itself record another event."""
    require_document(session, principal, document_id, "view")
    return list(
        session.scalars(
            select(DocumentEvent)
            .where(DocumentEvent.document_id == document_id)
            .order_by(DocumentEvent.created_at.desc(), DocumentEvent.id.desc())
            .limit(limit)
        )
    )


def _store_version(
    session: Session,
    principal: Principal,
    storage: StorageBackend,
    document: Document,
    *,
    detected,
    filename: str,
    content: bytes,
    change_note: str,
    restored_from: int | None,
) -> DocumentResult:
    key = _save(storage, content)
    try:
        number = _next_version_number(session, document.id)
        session.add(
            DocumentVersion(
                document_id=document.id,
                version_number=number,
                storage_key=key,
                original_filename=filename,
                mime_type=detected.mime_type,
                size_bytes=len(content),
                uploaded_by=principal.user.id,
                change_note=change_note,
            )
        )
        document.storage_key = key
        document.original_filename = filename
        document.mime_type = detected.mime_type
        document.size_bytes = len(content)
        document.current_version_number = number
        document.last_modified_at = utcnow()
        metadata: dict[str, object] = {"action": "version", "version_number": number}
        if restored_from is not None:
            metadata["restored_from"] = restored_from
        record_document_event(session, principal, document.id, EventType.update, metadata)
        session.commit()
    except IntegrityError as exc:
        _discard_upload(session, storage, key)
        raise ApiError(409, "CONFLICT", "The change conflicts with an existing record.") from exc
    except Exception:
        _discard_upload(session, storage, key)
        raise
    payload = {"document_id": str(document.id), "actor_id": str(principal.user.id), "version_number": number}
    if restored_from is not None:
        payload["restored_from"] = restored_from
    emit_with_session(session, DOCUMENT_VERSION_ADDED, **payload)
    return _one(session, principal, document)


def _results(session: Session, principal: Principal, documents: list[Document]) -> list[DocumentResult]:
    if not documents:
        return []
    identifiers = [document.id for document in documents]
    tags = _tags_for(session, identifiers)
    grants = load_grants_for(session, DocumentPermission, identifiers)
    return [
        DocumentResult(
            document=document,
            tags=tags.get(document.id, []),
            my_access=access_level(principal.user, document, grants.get(document.id, ()), principal.scopes),
        )
        for document in documents
    ]


def _one(session: Session, principal: Principal, document: Document) -> DocumentResult:
    return _results(session, principal, [document])[0]


def _tags_for(session: Session, document_ids: list[UUID]) -> dict[UUID, list[Tag]]:
    grouped: dict[UUID, list[Tag]] = {document_id: [] for document_id in document_ids}
    rows = session.execute(
        select(DocumentTag.document_id, Tag)
        .join(Tag, Tag.id == DocumentTag.tag_id)
        .where(DocumentTag.document_id.in_(document_ids))
        .order_by(Tag.name, Tag.id)
    ).all()
    for document_id, tag in rows:
        grouped[document_id].append(tag)
    return grouped


def _replace_tags(session: Session, document_id: UUID, tag_ids: list[UUID]) -> None:
    unique = list(dict.fromkeys(tag_ids))
    if unique:
        found = set(session.scalars(select(Tag.id).where(Tag.id.in_(unique))))
        missing = [str(tag_id) for tag_id in unique if tag_id not in found]
        if missing:
            raise ApiError(422, "UNKNOWN_TAG", "One or more tags do not exist.", details={"ids": missing})
    session.execute(delete(DocumentTag).where(DocumentTag.document_id == document_id))
    for tag_id in unique:
        session.add(DocumentTag(document_id=document_id, tag_id=tag_id))


def _require_listed_folder(session: Session, principal: Principal, folder_id: UUID) -> None:
    folder = session.get(Folder, folder_id)
    if folder is None or folder.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", "Folder not found.")
    visible = session.scalar(select(Folder.id).where(Folder.id == folder.id, accessible_folders_query(principal.user, principal.scopes)))
    if visible is None:
        raise ApiError(404, "NOT_FOUND", "Folder not found.")


def _require_category(session: Session, category_id: UUID) -> None:
    if session.get(Category, category_id) is None:
        raise ApiError(422, "UNKNOWN_CATEGORY", "Choose a category that exists.")


def _require_department(session: Session, department_id: UUID) -> None:
    if session.get(Department, department_id) is None:
        raise ApiError(422, "UNKNOWN_DEPARTMENT", "Choose a department that exists.")


def _reject_archived(document: Document) -> None:
    if document.status == DocumentStatus.archived:
        raise ApiError(409, "ARCHIVED", "Restore this document before changing it.")


def _reject_google(document: Document) -> None:
    if document.source_type in _GOOGLE:
        raise ApiError(409, "NOT_A_FILE", "Google documents don't accept uploaded versions.")


def _version(session: Session, document_id: UUID, version_number: int) -> DocumentVersion:
    version = session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number,
        )
    )
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "Version not found.")
    return version


def _next_version_number(session: Session, document_id: UUID) -> int:
    current = session.scalar(
        select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == document_id)
    )
    return 1 if current is None else int(current) + 1


def _inline(mime_type: str) -> bool:
    return mime_type in {"application/pdf", "text/plain", "image/png", "image/jpeg", "image/webp"}


def _detect(content: bytes):
    try:
        return detect_file(content)
    except StorageError as exc:
        raise ApiError(exc.status_code, exc.code, exc.message) from exc


def _discard_upload(session: Session, storage: StorageBackend, key: str) -> None:
    session.rollback()
    storage.delete(key)


def _save(storage: StorageBackend, content: bytes) -> str:
    try:
        return storage.save(content)
    except StorageError as exc:
        raise ApiError(exc.status_code, exc.code, exc.message) from exc


def _read(storage: StorageBackend, key: str) -> bytes:
    try:
        return storage.read(key)
    except StorageError as exc:
        raise ApiError(exc.status_code, exc.code, exc.message) from exc


def _commit_document(session: Session, event: str, document: Document, principal: Principal, **extra: object) -> None:
    payload = {"document_id": str(document.id), "actor_id": str(principal.user.id)}
    for key, value in extra.items():
        if value is not None:
            payload[key] = value
    commit_and_emit(session, event, **payload)
