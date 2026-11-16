"""Read extracted text and find related documents.

Content is returned as data, labeled `document_content`, and paginated.
A document the caller cannot view is a 404. Related rows are produced by
`accessible_documents_query`; nothing is loaded and then dropped.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import DocumentStatus, EventType, ExtractionStatus, JobStatus, SourceType
from app.core.principal import Principal
from app.ingestion.queue import get_queue
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.ingestion import IngestionJob
from app.models.taxonomy import DocumentTag
from app.permissions.engine import accessible_documents_query
from app.services.activity import commit_and_emit, record_document_event
from app.services.documents import require_document

CONTENT_DEFAULT_LIMIT = 20_000
CONTENT_MAX_LIMIT = 50_000
RELATED_DEFAULT_LIMIT = 5
RELATED_MAX_LIMIT = 20
TITLE_SIMILARITY = 0.4
_TAG_WEIGHT = 4
_FOLDER_WEIGHT = 3
_DEPARTMENT_WEIGHT = 2
_TITLE_WEIGHT = 5.0

_WAITING = {
    ExtractionStatus.pending: "Text extraction has not finished.",
    ExtractionStatus.processing: "Text extraction is in progress.",
    ExtractionStatus.failed: "Text extraction failed.",
    ExtractionStatus.skipped: "Text extraction was skipped.",
}


@dataclass(frozen=True)
class ContentPage:
    text: str | None
    offset: int
    next_offset: int | None
    total_chars: int
    truncated: bool
    extraction_status: ExtractionStatus
    extracted_at: datetime | None
    heading_outline: list[str]
    detail: str | None


@dataclass(frozen=True)
class RelatedDocument:
    id: UUID
    name: str
    folder_id: UUID
    department_id: UUID
    source_type: SourceType
    score: float
    reasons: list[str]


@dataclass(frozen=True)
class AiStatus:
    ai_enabled: bool
    extraction_status: ExtractionStatus
    chunk_count: int
    extracted_at: datetime | None


@dataclass(frozen=True)
class ReindexResult:
    document_id: UUID
    job_id: UUID
    status: JobStatus


def read_content(session: Session, principal: Principal, document_id: UUID, *, offset: int, limit: int) -> ContentPage:
    """Return one page of extracted text, or a status when extraction is not done."""
    document = require_document(session, principal, document_id, "view")
    offset = max(0, offset)
    limit = min(max(1, limit), CONTENT_MAX_LIMIT)
    record_document_event(
        session,
        principal,
        document.id,
        EventType.read_content,
        {"offset": offset, "limit": limit, "extraction_status": document.extraction_status.value},
    )
    page = _page(session, document, offset, limit)
    commit_and_emit(session)
    return page


def related_documents(session: Session, principal: Principal, document_id: UUID, *, limit: int) -> list[RelatedDocument]:
    """Rank accessible documents that share tags, folder, department, or a similar title."""
    source = require_document(session, principal, document_id, "view")
    limit = min(max(1, limit), RELATED_MAX_LIMIT)
    tag_ids = list(session.scalars(select(DocumentTag.tag_id).where(DocumentTag.document_id == source.id)))
    if tag_ids:
        shared_tags = (
            select(func.count())
            .select_from(DocumentTag)
            .where(DocumentTag.document_id == Document.id, DocumentTag.tag_id.in_(tag_ids))
            .correlate(Document)
            .scalar_subquery()
        )
    else:
        shared_tags = literal(0)
    title_similarity = func.similarity(Document.name, literal(source.name))
    same_folder = Document.folder_id == source.folder_id
    same_department = Document.department_id == source.department_id
    score = (
        shared_tags * _TAG_WEIGHT
        + case((same_folder, _FOLDER_WEIGHT), else_=0)
        + case((same_department, _DEPARTMENT_WEIGHT), else_=0)
        + case((title_similarity >= TITLE_SIMILARITY, title_similarity * _TITLE_WEIGHT), else_=0.0)
    )
    rows = session.execute(
        select(
            Document.id,
            Document.name,
            Document.folder_id,
            Document.department_id,
            Document.source_type,
            shared_tags.label("shared_tags"),
            same_folder.label("same_folder"),
            same_department.label("same_department"),
            title_similarity.label("title_similarity"),
            score.label("score"),
        )
        .where(
            accessible_documents_query(principal.user, principal.scopes),
            Document.id != source.id,
            Document.status == DocumentStatus.active,
            score > 0,
        )
        .order_by(score.desc(), Document.name.asc(), Document.id.asc())
        .limit(limit)
    ).all()
    return [_related(row) for row in rows]


def document_ai_status(session: Session, principal: Principal, document_id: UUID) -> AiStatus:
    document = require_document(session, principal, document_id, "view")
    count = session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(
            DocumentChunk.document_id == document.id,
            DocumentChunk.version_number == document.current_version_number,
        )
    )
    return AiStatus(
        ai_enabled=get_settings().ai_enabled,
        extraction_status=document.extraction_status,
        chunk_count=int(count or 0),
        extracted_at=document.extracted_at,
    )


def reindex_document(session: Session, principal: Principal, document_id: UUID) -> ReindexResult:
    """Queue extraction again. Admins call this; the route checks the role."""
    document = require_document(session, principal, document_id, "view")
    document.extraction_status = ExtractionStatus.pending
    document.extraction_error = None
    job_id = get_queue().enqueue(session, document.id, force=True)
    session.commit()
    job = session.get(IngestionJob, job_id)
    status = job.status if job is not None else JobStatus.pending
    return ReindexResult(document_id=document.id, job_id=job_id, status=status)


def _page(session: Session, document: Document, offset: int, limit: int) -> ContentPage:
    if document.extraction_status is not ExtractionStatus.done:
        if document.extraction_status in {ExtractionStatus.skipped, ExtractionStatus.failed} and document.extraction_error:
            detail = document.extraction_error
        else:
            detail = _WAITING[document.extraction_status]
        return ContentPage(
            text=None,
            offset=offset,
            next_offset=None,
            total_chars=0,
            truncated=False,
            extraction_status=document.extraction_status,
            extracted_at=document.extracted_at,
            heading_outline=[],
            detail=detail,
        )
    outline = _heading_outline(session, document)
    body = document.content_text or ""
    total = len(body)
    if offset >= total:
        snippet = ""
        next_offset = None
    else:
        end = min(total, offset + limit)
        snippet = body[offset:end]
        next_offset = end if end < total else None
    return ContentPage(
        text=snippet,
        offset=offset,
        next_offset=next_offset,
        total_chars=total,
        truncated=next_offset is not None,
        extraction_status=document.extraction_status,
        extracted_at=document.extracted_at,
        heading_outline=outline,
        detail=None,
    )


def _heading_outline(session: Session, document: Document) -> list[str]:
    rows = session.scalars(
        select(DocumentChunk.heading_path)
        .where(
            DocumentChunk.document_id == document.id,
            DocumentChunk.version_number == document.current_version_number,
            DocumentChunk.heading_path.is_not(None),
        )
        .order_by(DocumentChunk.chunk_index.asc())
    )
    outline: list[str] = []
    for path in rows:
        if path and path not in outline:
            outline.append(path)
    return outline


def _related(row) -> RelatedDocument:
    reasons: list[str] = []
    if int(row.shared_tags or 0) > 0:
        reasons.append("tag")
    if bool(row.same_folder):
        reasons.append("folder")
    if bool(row.same_department):
        reasons.append("department")
    if float(row.title_similarity or 0) >= TITLE_SIMILARITY:
        reasons.append("title")
    return RelatedDocument(
        id=row.id,
        name=row.name,
        folder_id=row.folder_id,
        department_id=row.department_id,
        source_type=row.source_type,
        score=round(float(row.score or 0), 4),
        reasons=reasons,
    )
