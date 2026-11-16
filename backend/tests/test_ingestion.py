"""Extraction, chunking, and the Postgres job queue. No AI provider is called."""

import io
import socket
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app.ai.errors import NotConfigured
from app.api.deps import get_storage
from app.core.config import get_settings
from app.core.enums import ExtractionStatus, JobStatus, SourceType, Visibility
from app.ingestion.chunker import OVERLAP_TOKENS, TARGET_TOKENS, chunk_text, count_tokens, text_hash, tokenize
from app.ingestion.extractors import (
    DocxExtractor,
    ExtractInput,
    GoogleExportExtractor,
    OCRExtractor,
    PdfExtractor,
    PlainTextExtractor,
    PermanentExtractionError,
    TransientExtractionError,
)
from app.ingestion.pipeline import ExtractionPipeline, process_document
from app.ingestion.queue import EXTRACT_JOB, IngestionQueue, PostgresIngestionQueue, claim_statement, drain
from app.integrations.drive import MIME_DOCUMENT, MIME_PRESENTATION, MIME_SPREADSHEET, FakeDriveClient
from app.integrations.storage import LocalDiskStorage
from app.main import app
from app.models import Document, DocumentChunk, IngestionJob
from app.models.base import utcnow
from tests.blobs import office_bytes, png_bytes, text_bytes
from tests.helpers import CSRF, login
from tests.library import add_category, add_document, add_folder
from tests.test_documents_api import _form, _library

_AI_MARKERS = (
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.cohere.com",
    "api.groq.com",
    "import openai",
    "from openai",
    "import anthropic",
    "from anthropic",
)


def test_chunker_is_deterministic_and_overlaps_by_eighty_tokens():
    source = " ".join(f"w{index:04d}" for index in range(1000))
    first = chunk_text(source)
    assert first == chunk_text(source)
    assert [chunk.chunk_index for chunk in first] == list(range(len(first)))
    assert first[0].token_count == TARGET_TOKENS
    assert first[0].heading_path is None
    assert tokenize(first[1].text)[:OVERLAP_TOKENS] == tokenize(first[0].text)[-OVERLAP_TOKENS:]
    assert first[0].content_hash == text_hash(first[0].text)
    assert count_tokens(first[0].text) == first[0].token_count


def test_chunker_overlap_stays_inside_one_heading():
    alpha = " ".join(f"a{index:04d}" for index in range(700))
    beta = " ".join(f"b{index:04d}" for index in range(700))
    source = f"# Alpha\n\n{alpha}\n\n# Beta\n\n{beta}\n"
    chunks = chunk_text(source)
    alpha_chunks = [chunk for chunk in chunks if chunk.heading_path == "Alpha"]
    beta_chunks = [chunk for chunk in chunks if chunk.heading_path == "Beta"]
    assert len(alpha_chunks) >= 2
    assert len(beta_chunks) >= 2
    body = [chunk for chunk in alpha_chunks if chunk.token_count >= TARGET_TOKENS]
    assert body
    following = alpha_chunks[alpha_chunks.index(body[0]) + 1]
    assert tokenize(following.text)[:OVERLAP_TOKENS] == tokenize(body[0].text)[-OVERLAP_TOKENS:]
    assert not any(token.startswith("b") for token in tokenize(alpha_chunks[-1].text))
    assert not any(token.startswith("a") for token in tokenize(beta_chunks[0].text))


def test_chunker_keeps_nested_heading_paths():
    source = "# Animals\n\nCats are small.\n\n## Habitat\n\nCats live indoors.\n"
    chunks = chunk_text(source)
    assert [chunk.heading_path for chunk in chunks] == ["Animals", "Animals / Habitat"]
    assert "Cats are small." in chunks[0].text
    assert "Cats live indoors." in chunks[1].text
    assert "small" not in chunks[1].text


def test_extractors_read_each_supported_type():
    plain = PlainTextExtractor().extract(ExtractInput(data="Hello plain text\n".encode()))
    assert plain == "Hello plain text"
    pdf = PdfExtractor().extract(ExtractInput(data=_pdf("Hello PDF extraction")))
    assert "Hello PDF extraction" in pdf
    docx = DocxExtractor().extract(ExtractInput(data=_docx()))
    assert "# Animals" in docx
    assert "Cats live indoors." in docx
    drive = FakeDriveClient()
    samples = {
        SourceType.google_doc: (MIME_DOCUMENT, "doc-file-1234567890"),
        SourceType.google_sheet: (MIME_SPREADSHEET, "sheet-file-12345678"),
        SourceType.google_slide: (MIME_PRESENTATION, "slide-file-12345678"),
    }
    for _source, (mime, file_id) in samples.items():
        drive.seed_file(file_id, mime_type=mime, text=f"exported {mime}")
        extracted = GoogleExportExtractor(drive).extract(ExtractInput(google_file_id=file_id))
        assert extracted == f"exported {mime}"
    with pytest.raises(NotConfigured, match="OCR"):
        OCRExtractor().extract(ExtractInput(data=png_bytes()))
    try:
        garbage = PdfExtractor().extract(ExtractInput(data=b"not a pdf"))
    except PermanentExtractionError:
        garbage = None
    assert garbage in {None, ""}


def test_pipeline_extracts_hashes_chunks_and_skips_unreadable_types(org, db_session, tmp_path):
    storage = LocalDiskStorage(tmp_path)
    category = add_category(db_session, name=f"Extract {uuid4().hex[:8]}")
    folder = add_folder(db_session, name="Files", owner=org.employee, department=org.product, visibility=Visibility.organization)
    notes = _stored(
        db_session,
        storage,
        name="Field notes",
        folder=folder,
        owner=org.employee,
        department=org.product,
        category=category,
        source_type=SourceType.txt,
        payload=text_bytes("# Animals\n\nqxpipelinealpha cats live indoors.\n\n## Habitat\n\nTrees.\n"),
    )
    process_document(db_session, notes.id, storage=storage)
    db_session.flush()
    assert notes.extraction_status is ExtractionStatus.done
    assert notes.content_hash
    assert "qxpipelinealpha" in notes.content_text
    assert notes.extracted_at is not None
    chunks = list(
        db_session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == notes.id).order_by(DocumentChunk.chunk_index)
        )
    )
    assert [chunk.heading_path for chunk in chunks] == ["Animals", "Animals / Habitat"]
    assert chunks[0].token_count == count_tokens(chunks[0].text)
    matched = db_session.scalar(
        text("SELECT search_vector @@ plainto_tsquery('english', :term) FROM documents WHERE id = :id"),
        {"term": "qxpipelinealpha", "id": notes.id},
    )
    assert matched is True

    kept = [chunk.id for chunk in chunks]
    process_document(db_session, notes.id, storage=storage)
    db_session.expire_all()
    again = list(db_session.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == notes.id)))
    assert set(again) == set(kept)

    notes = db_session.get(Document, notes.id)
    notes.storage_key = storage.save(text_bytes("A completely different body about qxotherterm."))
    notes.current_version_number = 2
    db_session.flush()
    process_document(db_session, notes.id, storage=storage)
    db_session.expire_all()
    current = list(
        db_session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == notes.id, DocumentChunk.version_number == 2)
        )
    )
    previous = list(
        db_session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == notes.id, DocumentChunk.version_number == 1)
        )
    )
    assert previous
    assert current
    assert "qxotherterm" in db_session.get(Document, notes.id).content_text
    assert all(chunk.id not in {item.id for item in current} for chunk in previous)

    for source, payload, phrase in (
        (SourceType.pdf, _pdf("Hello PDF extraction"), "Hello PDF extraction"),
        (SourceType.docx, _docx(), "Cats live indoors."),
    ):
        document = _stored(
            db_session,
            storage,
            name=source.value,
            folder=folder,
            owner=org.employee,
            department=org.product,
            category=category,
            source_type=source,
            payload=payload,
        )
        process_document(db_session, document.id, storage=storage)
        assert document.extraction_status is ExtractionStatus.done
        assert phrase in document.content_text

    drive = FakeDriveClient()
    for source, mime in (
        (SourceType.google_doc, MIME_DOCUMENT),
        (SourceType.google_sheet, MIME_SPREADSHEET),
        (SourceType.google_slide, MIME_PRESENTATION),
    ):
        file_id = f"file{uuid4().hex[:16]}"
        drive.seed_file(file_id, mime_type=mime, text=f"cells for {source.value}")
        document = add_document(
            db_session,
            name=source.value,
            folder=folder,
            owner=org.employee,
            department=org.product,
            category=category,
            visibility=Visibility.organization,
            source_type=source,
        )
        document.google_file_id = file_id
        db_session.flush()
        process_document(db_session, document.id, storage=storage, drive=drive)
        assert document.extraction_status is ExtractionStatus.done
        assert source.value in document.content_text

    for source, payload in (
        (SourceType.image, png_bytes()),
        (SourceType.ppt, office_bytes("pptx")),
        (SourceType.xlsx, office_bytes("xlsx")),
    ):
        document = _stored(
            db_session,
            storage,
            name=source.value,
            folder=folder,
            owner=org.employee,
            department=org.product,
            category=category,
            source_type=source,
            payload=payload,
        )
        process_document(db_session, document.id, storage=storage)
        assert document.extraction_status is ExtractionStatus.skipped
        assert document.content_text is None
        assert document.extraction_error
    reasons = {
        SourceType.image: "OCR",
        SourceType.ppt: "PowerPoint",
        SourceType.xlsx: "Excel",
    }
    for source, phrase in reasons.items():
        skipped = db_session.scalar(select(Document).where(Document.name == source.value, Document.owner_id == org.employee.id))
        assert phrase in skipped.extraction_error


def test_failed_jobs_retry_with_backoff_then_stop(org, db_session):
    document = _bare_document(org, db_session)
    queue = PostgresIngestionQueue(pipeline=_Boom(), max_attempts=3, backoff_seconds=60)
    queue.enqueue(db_session, document.id)
    assert queue.run_next(db_session) is True
    db_session.expire_all()
    job = db_session.scalar(select(IngestionJob).where(IngestionJob.document_id == document.id))
    assert job.status is JobStatus.pending
    assert job.attempts == 1
    assert job.run_after is not None
    assert job.run_after > utcnow()
    assert "timed out" in job.last_error
    assert queue.run_next(db_session) is False

    job.run_after = utcnow() - timedelta(hours=1)
    db_session.flush()
    assert queue.run_next(db_session) is True
    db_session.expire_all()
    job = db_session.scalar(select(IngestionJob).where(IngestionJob.document_id == document.id, IngestionJob.status == JobStatus.pending))
    assert job.attempts == 2

    job.run_after = None
    db_session.flush()
    assert queue.run_next(db_session) is True
    db_session.expire_all()
    job = db_session.scalar(select(IngestionJob).where(IngestionJob.document_id == document.id))
    assert job.status is JobStatus.failed
    assert job.attempts == 3
    assert db_session.get(Document, document.id).extraction_status is ExtractionStatus.failed


def test_permanent_errors_do_not_retry(org, db_session):
    document = _bare_document(org, db_session)
    queue = PostgresIngestionQueue(pipeline=_Broken(), max_attempts=5, backoff_seconds=30)
    queue.enqueue(db_session, document.id)
    assert queue.run_next(db_session) is True
    db_session.expire_all()
    job = db_session.scalar(select(IngestionJob).where(IngestionJob.document_id == document.id))
    assert job.status is JobStatus.failed
    assert job.attempts == 1
    assert db_session.get(Document, document.id).extraction_status is ExtractionStatus.failed


def test_claim_uses_skip_locked(engine):
    compiled = str(claim_statement().compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in compiled.upper()
    assert "SKIP LOCKED" in compiled.upper()
    _publish(engine)
    left = SessionProbe(engine)
    right = SessionProbe(engine)
    third = SessionProbe(engine)
    try:
        claimed_left = left.session.scalar(claim_statement())
        claimed_right = right.session.scalar(claim_statement())
        third.session.execute(text("SET LOCAL lock_timeout = '2s'"))
        claimed_third = third.session.scalar(claim_statement())
        assert claimed_left is not None
        assert claimed_right is not None
        assert claimed_left.id != claimed_right.id
        assert claimed_third is None
    finally:
        left.close()
        right.close()
        third.close()
        _unpublish(engine)


def test_events_enqueue_extract_jobs(api, org, db_session, tmp_path):
    storage = LocalDiskStorage(tmp_path)
    app.dependency_overrides[get_storage] = lambda: storage
    library = _library(api, org)
    login(api, org.employee.email)
    uploaded = api.post(
        "/api/v1/documents/upload",
        data=_form(library, "Pipeline notes", visibility="organization"),
        files={"file": ("notes.txt", text_bytes("qxpipelinealpha in the upload"), "text/plain")},
        headers=CSRF,
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    db_session.expire_all()
    job = db_session.scalar(select(IngestionJob).where(IngestionJob.document_id == document_id, IngestionJob.job_type == "extract"))
    assert job is not None
    assert job.status is JobStatus.pending

    db_session.execute(delete(IngestionJob).where(IngestionJob.document_id == document_id))
    db_session.flush()
    renamed = api.patch(f"/api/v1/documents/{document_id}", json={"name": "Pipeline notes revised"}, headers=CSRF)
    assert renamed.status_code == 200, renamed.text
    db_session.expire_all()
    assert db_session.scalar(select(IngestionJob.id).where(IngestionJob.document_id == document_id, IngestionJob.status == JobStatus.pending))

    db_session.execute(delete(IngestionJob).where(IngestionJob.document_id == document_id))
    db_session.flush()
    version = api.post(
        f"/api/v1/documents/{document_id}/versions",
        files={"file": ("notes.txt", text_bytes("second body"), "text/plain")},
        data={"change_note": "Next"},
        headers=CSRF,
    )
    assert version.status_code == 201, version.text
    db_session.expire_all()
    assert db_session.scalar(select(IngestionJob.id).where(IngestionJob.document_id == document_id, IngestionJob.status == JobStatus.pending))

    queue = PostgresIngestionQueue(pipeline=ExtractionPipeline(storage=storage))
    assert drain(queue, db_session, limit=5) >= 1
    db_session.expire_all()
    stored = db_session.get(Document, document_id)
    assert stored.extraction_status is ExtractionStatus.done
    assert "second body" in stored.content_text


def test_queue_can_be_replaced_without_changing_drain():
    class OtherQueue:
        def __init__(self):
            self.runs = 0

        def enqueue(self, session, document_id, job_type=EXTRACT_JOB, *, force=False):
            return document_id

        def run_next(self, session) -> bool:
            self.runs += 1
            return self.runs < 3

    queue = OtherQueue()
    assert isinstance(PostgresIngestionQueue(), IngestionQueue)
    assert drain(queue, session=None, limit=10) == 2
    assert queue.runs == 3


def test_ingestion_does_not_call_an_ai_provider(monkeypatch):
    root = Path(__file__).resolve().parents[1] / "app"
    for package in ("ingestion", "ai"):
        for path in (root / package).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for marker in _AI_MARKERS:
                assert marker not in source, f"{path} mentions {marker}"
    calls = []

    def blocked(*args, **kwargs):
        calls.append(args)
        raise AssertionError(f"unexpected network call: {args}")

    monkeypatch.setattr(socket, "create_connection", blocked)
    PlainTextExtractor().extract(ExtractInput(data=b"local only"))
    PdfExtractor().extract(ExtractInput(data=_pdf("Hello PDF extraction")))
    DocxExtractor().extract(ExtractInput(data=_docx()))
    drive = FakeDriveClient()
    drive.seed_file("local-google-file-1", text="local export")
    GoogleExportExtractor(drive).extract(ExtractInput(google_file_id="local-google-file-1"))
    assert calls == []
    assert get_settings().ai_enabled is False
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any(path == "/api/v1/ai" or path.startswith("/api/v1/ai/") for path in paths)


class _Boom:
    def run(self, session, document_id):
        raise TransientExtractionError("drive timed out")


class _Broken:
    def run(self, session, document_id):
        raise PermanentExtractionError("This PDF could not be read.")


class SessionProbe:
    def __init__(self, engine):
        self.session = sessionmaker(bind=engine, expire_on_commit=False)()

    def close(self):
        self.session.rollback()
        self.session.close()


_published_document_id = None
_published_folder_id = None
_published_category_id = None
_published_user_id = None
_published_department_id = None


def _publish(engine):
    """Commit two pending jobs so two connections can lock different rows."""
    global _published_document_id, _published_folder_id, _published_category_id, _published_user_id, _published_department_id
    from app.core.enums import AccessGrant, UserRole
    from app.models import Category, Department, Folder, User

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        department = Department(code=f"lock{uuid4().hex[:8]}", name=f"Lock {uuid4().hex[:8]}")
        session.add(department)
        session.flush()
        user = User(email=f"lock-{uuid4().hex[:8]}@company.com", name="Lock", role=UserRole.employee, department_id=department.id)
        session.add(user)
        session.flush()
        folder_id = uuid4()
        folder = Folder(
            id=folder_id,
            name="Lock",
            path=f"/{folder_id}",
            depth=0,
            department_id=department.id,
            owner_id=user.id,
            visibility=Visibility.private,
            default_access=AccessGrant.view,
        )
        category = Category(name=f"Lock {uuid4().hex[:8]}")
        session.add_all([folder, category])
        session.flush()
        document = Document(
            name="Locked",
            folder_id=folder.id,
            category_id=category.id,
            department_id=department.id,
            owner_id=user.id,
            source_type=SourceType.txt,
            visibility=Visibility.private,
            default_access=AccessGrant.view,
        )
        session.add(document)
        session.flush()
        session.add_all(
            [
                IngestionJob(document_id=document.id, job_type=EXTRACT_JOB, status=JobStatus.pending),
                IngestionJob(document_id=document.id, job_type=EXTRACT_JOB, status=JobStatus.pending),
            ]
        )
        session.commit()
        _published_document_id = document.id
        _published_folder_id = folder.id
        _published_category_id = category.id
        _published_user_id = user.id
        _published_department_id = department.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _unpublish(engine):
    if _published_document_id is None:
        return
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM ingestion_jobs WHERE document_id = :id"), {"id": _published_document_id})
        connection.execute(text("DELETE FROM documents WHERE id = :id"), {"id": _published_document_id})
        connection.execute(text("DELETE FROM folders WHERE id = :id"), {"id": _published_folder_id})
        connection.execute(text("DELETE FROM categories WHERE id = :id"), {"id": _published_category_id})
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": _published_user_id})
        connection.execute(text("DELETE FROM departments WHERE id = :id"), {"id": _published_department_id})


def _bare_document(org, db_session):
    category = add_category(db_session, name=f"Jobs {uuid4().hex[:8]}")
    folder = add_folder(db_session, name="Jobs", owner=org.employee, department=org.product, visibility=Visibility.private)
    return add_document(
        db_session,
        name="Queued",
        folder=folder,
        owner=org.employee,
        department=org.product,
        category=category,
        visibility=Visibility.private,
        source_type=SourceType.txt,
    )


def _stored(db_session, storage, *, name, folder, owner, department, category, source_type, payload):
    document = add_document(
        db_session,
        name=name,
        folder=folder,
        owner=owner,
        department=department,
        category=category,
        visibility=Visibility.organization,
        source_type=source_type,
    )
    document.storage_key = storage.save(payload)
    document.mime_type = "application/octet-stream"
    db_session.flush()
    return document


def _pdf(message: str) -> bytes:
    escaped = message.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 700 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    header = b"%PDF-1.4\n"
    chunks = [header]
    offsets = [0]
    cursor = len(header)
    for number, body in enumerate(objects, start=1):
        offsets.append(cursor)
        piece = f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
        chunks.append(piece)
        cursor += len(piece)
    xref = ["xref\n0 6\n", "0000000000 65535 f \n"]
    xref.extend(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{cursor}\n%%EOF\n"
    return b"".join(chunks) + "".join(xref).encode() + trailer.encode()


def _docx() -> bytes:
    from docx import Document

    document = Document()
    document.add_heading("Animals", level=1)
    document.add_paragraph("Cats are small.")
    document.add_heading("Habitat", level=2)
    document.add_paragraph("Cats live indoors.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
