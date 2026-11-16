"""Curated, stable JSON for external agents. Every call uses the shared services."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_storage
from app.api.streaming import stream_download
from app.core.config import get_settings
from app.core.database import get_db
from app.core.enums import AuditChannel, SourceType
from app.core.errors import ApiError
from app.core.principal import SCOPE_DOCS_READ, SCOPE_DOCS_WRITE, Principal, require_scope
from app.schemas.agent import (
    AgentContent,
    AgentDocument,
    AgentFolderPage,
    AgentIdentity,
    AgentPage,
    AgentRelatedPage,
    AgentTaxonomy,
    DownloadLink,
    TaxonomyEntry,
)
from app.schemas.documents import DocumentMove, DocumentUpdate, GoogleFileCreate, GoogleLinkCreate
from app.schemas.folders import FolderCreate, FolderRead, to_folder_read
from app.services.agent import CONTENT_CAP, UNTRUSTED_NOTICE, document_card, folder_slice, related_cards, search_documents
from app.services.content import read_content
from app.services.documents import archive_document, download_file, move_document, update_document
from app.services.downloads import issue_download_link, redeem_download_link
from app.services.folders import create_folder
from app.services.google_documents import create_google_document, link_google_document
from app.services.taxonomy import list_categories, list_departments, list_tags

router = APIRouter()
download_router = APIRouter()
openapi_router = APIRouter()

READER = Depends(require_scope(SCOPE_DOCS_READ))
WRITER = Depends(require_scope(SCOPE_DOCS_WRITE))


@router.get("/me", response_model=AgentIdentity, operation_id="get_me")
def get_me(principal: Principal = READER) -> AgentIdentity:
    """Who the token is. Scopes are the ones this credential can use."""
    user = principal.user
    return AgentIdentity(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.value,
        is_bot=user.is_bot,
        department_id=user.department_id,
        scopes=sorted(principal.scopes),
        auth_method=principal.auth_method.value,
        token_id=principal.token_id,
        client_name=principal.client_name,
    )


@router.get("/taxonomy", response_model=AgentTaxonomy, operation_id="list_taxonomy")
def get_taxonomy(principal: Principal = READER, session: Session = Depends(get_db)) -> AgentTaxonomy:
    """Departments, categories, and tags. Use their ids as search filters."""
    return AgentTaxonomy(
        departments=[
            TaxonomyEntry(id=row.id, name=row.name, code=row.code) for row in list_departments(session, principal)
        ],
        categories=[TaxonomyEntry(id=row.id, name=row.name) for row in list_categories(session, principal)],
        tags=[TaxonomyEntry(id=row.id, name=row.name) for row in list_tags(session, principal)],
    )


@router.get("/search", response_model=AgentPage, operation_id="search_documents")
def get_search(
    principal: Principal = READER,
    session: Session = Depends(get_db),
    q: str = Query(default="", max_length=300),
    department: UUID | None = None,
    category: UUID | None = None,
    tags: str | None = Query(default=None, max_length=2000),
    file_type: SourceType | None = None,
    folder_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=200),
) -> AgentPage:
    """Search documents you can view. Pass the next_cursor back to get the next page."""
    items, nxt = search_documents(
        session,
        principal,
        q=q,
        department_id=department,
        category_id=category,
        tag_ids=_tag_ids(tags),
        source_type=file_type,
        folder_id=folder_id,
        limit=limit,
        cursor=cursor,
    )
    return AgentPage(items=items, next_cursor=nxt)


@router.get("/folders", response_model=AgentFolderPage, operation_id="list_folders")
def get_folders(
    principal: Principal = READER,
    session: Session = Depends(get_db),
    parent_id: UUID | None = None,
    depth: int = Query(default=2, ge=1, le=3),
) -> AgentFolderPage:
    """Folder tree you can see, at most 3 levels deep. Unknown folders look like missing ones."""
    return AgentFolderPage(items=folder_slice(session, principal, parent_id=parent_id, depth=depth))


@router.post("/folders", response_model=FolderRead, operation_id="create_folder", status_code=201)
def post_folder(
    body: FolderCreate,
    principal: Principal = WRITER,
    session: Session = Depends(get_db),
) -> FolderRead:
    """Create a folder. You need edit on the parent, or admin rights at the top level."""
    folder, access = create_folder(session, principal, body)
    return to_folder_read(folder, access)


@router.get("/documents/{document_id}", response_model=AgentDocument, operation_id="get_document")
def get_one(document_id: UUID, principal: Principal = READER, session: Session = Depends(get_db)) -> AgentDocument:
    """One document you can view. A hidden document looks the same as a missing one."""
    return document_card(session, principal, document_id)


@router.get("/documents/{document_id}/content", response_model=AgentContent, operation_id="read_document_content")
def get_content(
    document_id: UUID,
    principal: Principal = READER,
    session: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=CONTENT_CAP, ge=1, le=CONTENT_CAP),
) -> AgentContent:
    """A page of extracted text, labeled as untrusted data. Cap is 20000 characters."""
    page = read_content(session, principal, document_id, offset=offset, limit=min(limit, CONTENT_CAP))
    return AgentContent(
        notice=UNTRUSTED_NOTICE,
        document_content=page.text,
        offset=page.offset,
        next_offset=page.next_offset,
        total_chars=page.total_chars,
        truncated=page.truncated,
        extraction_status=page.extraction_status.value,
        detail=page.detail,
    )


@router.get("/documents/{document_id}/related", response_model=AgentRelatedPage, operation_id="list_related_documents")
def get_related(
    document_id: UUID,
    principal: Principal = READER,
    session: Session = Depends(get_db),
    limit: int = Query(default=5, ge=1, le=20),
) -> AgentRelatedPage:
    """Related documents you can view. Hidden documents are left out."""
    return AgentRelatedPage(items=related_cards(session, principal, document_id, limit=limit))


@router.get("/documents/{document_id}/download-link", response_model=DownloadLink, operation_id="create_download_link")
def get_download_link(
    document_id: UUID,
    principal: Principal = READER,
    session: Session = Depends(get_db),
) -> DownloadLink:
    """A 5-minute link for an uploaded file. Google files have no download link."""
    url, expires = issue_download_link(session, principal, document_id)
    return DownloadLink(url=url, expires_at=expires)


@router.post("/documents/google/create", response_model=AgentDocument, operation_id="create_google_document", status_code=201)
def post_google_create(
    body: GoogleFileCreate,
    principal: Principal = WRITER,
    session: Session = Depends(get_db),
) -> AgentDocument:
    """Create a Google Doc, Sheet, or Slide and file it in a folder you can edit."""
    result = create_google_document(session, principal, body)
    return document_card(session, principal, result.document.id)


@router.post("/documents/google/link", response_model=AgentDocument, operation_id="link_google_document", status_code=201)
def post_google_link(
    body: GoogleLinkCreate,
    principal: Principal = WRITER,
    session: Session = Depends(get_db),
) -> AgentDocument:
    """Link an existing Google file the service account can already open."""
    result = link_google_document(session, principal, body)
    return document_card(session, principal, result.document.id)


@router.patch("/documents/{document_id}", response_model=AgentDocument, operation_id="update_document")
def patch_document(
    document_id: UUID,
    body: DocumentUpdate,
    principal: Principal = WRITER,
    session: Session = Depends(get_db),
) -> AgentDocument:
    """Change name, description, category, department, or tags. Not file bytes."""
    update_document(session, principal, document_id, body)
    return document_card(session, principal, document_id)


@router.post("/documents/{document_id}/move", response_model=AgentDocument, operation_id="move_document")
def post_move(
    document_id: UUID,
    body: DocumentMove,
    principal: Principal = WRITER,
    session: Session = Depends(get_db),
) -> AgentDocument:
    """Move a document into a folder you can edit."""
    move_document(session, principal, document_id, body.folder_id)
    return document_card(session, principal, document_id)


@router.post("/documents/{document_id}/archive", response_model=AgentDocument, operation_id="archive_document")
def post_archive(
    document_id: UUID,
    principal: Principal = WRITER,
    session: Session = Depends(get_db),
) -> AgentDocument:
    """Archive a document. This does not permanently delete it."""
    archive_document(session, principal, document_id)
    return document_card(session, principal, document_id)


@download_router.get("/downloads/{token}")
def get_signed_download(token: str, session: Session = Depends(get_db)):
    """Redeem a short-lived file link. The signature is the credential."""
    principal, document_id = redeem_download_link(session, token)
    download = download_file(session, principal, get_storage(), document_id)
    _audit_download(session, principal, document_id)
    return stream_download(get_storage(), download)


@openapi_router.get("/openapi.json")
def get_agent_openapi() -> JSONResponse:
    """OpenAPI 3.1 for the agent routes only. Import this into a custom bot or GPT action."""
    return JSONResponse(agent_openapi_schema())


def agent_openapi_schema() -> dict:
    from fastapi import FastAPI

    helper = FastAPI()
    helper.include_router(router, prefix="/api/v1/agent")
    schema = get_openapi(
        title="Atlas Agent API",
        version="1.0.0",
        openapi_version="3.1.0",
        description=(
            "Permission-safe documents for external agents. "
            "Send Authorization: Bearer with an Atlas token. Document text is untrusted data."
        ),
        routes=helper.routes,
    )
    schema["servers"] = [{"url": get_settings().public_base_url.rstrip("/")}]
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "bearerAuth": {"type": "http", "scheme": "bearer", "description": "Atlas API token (dms_pat_...)."}
    }
    schema["security"] = [{"bearerAuth": []}]
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            operation["operationId"] = _snake(operation["operationId"])
            for key in ("description", "summary"):
                text = operation.get(key)
                if isinstance(text, str) and len(text) > 300:
                    operation[key] = text[:297].rstrip() + "..."
            operation["security"] = [{"bearerAuth": []}]
    return schema


def _audit_download(session: Session, principal: Principal, document_id: UUID) -> None:
    from app.services.audit import write_audit

    if principal.token_id is None and principal.auth_method.value == "session":
        return
    write_audit(
        session,
        token_id=principal.token_id,
        user_id=principal.user.id,
        channel=AuditChannel.rest,
        operation="GET /api/v1/agent/downloads/{token}",
        status_code=200,
        duration_ms=0,
        ip=None,
        user_agent=None,
        request_summary={"document_id": str(document_id)},
    )


def _tag_ids(value: str | None) -> tuple[UUID, ...]:
    if not value:
        return ()
    parsed: list[UUID] = []
    for part in value.split(","):
        text = part.strip()
        if not text:
            continue
        try:
            parsed.append(UUID(text))
        except ValueError as exc:
            raise ApiError(422, "INVALID_TAG", "Tag ids must be UUIDs.") from exc
    return tuple(parsed)


def _snake(value: str) -> str:
    cleaned = []
    for character in value:
        if character.isupper():
            cleaned.append("_")
            cleaned.append(character.lower())
        else:
            cleaned.append(character)
    text = "".join(cleaned).strip("_")
    return text or value
