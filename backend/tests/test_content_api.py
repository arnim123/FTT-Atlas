"""Content, related documents, and the admin reindex route."""

from uuid import uuid4

from sqlalchemy import select

from app.api.deps import get_storage
from app.core.enums import ExtractionStatus, EventType, JobStatus, Visibility
from app.core.principal import SCOPE_DOCS_READ, AuthMethod
from app.ingestion.pipeline import ExtractionPipeline
from app.ingestion.queue import PostgresIngestionQueue, drain
from app.integrations.storage import LocalDiskStorage
from app.main import app
from app.models import Document, DocumentChunk, DocumentEvent, DocumentTag, IngestionJob
from tests.blobs import text_bytes
from tests.helpers import CSRF, acting_as, assert_error, login
from tests.library import add_category, add_document, add_folder, add_tag
from tests.test_documents_api import _form, _library


def test_content_pages_and_reports_status_instead_of_empty_text(api, org, db_session):
    ready = _document(org, db_session, name="Visible handbook", visibility=Visibility.department, owner=org.employee)
    ready.content_text = "abcdefghij" * 3
    ready.extraction_status = ExtractionStatus.done
    ready.extracted_at = ready.created_at
    db_session.add_all(
        [
            DocumentChunk(
                document_id=ready.id,
                version_number=1,
                chunk_index=0,
                text="abcdefghij",
                token_count=1,
                heading_path="Counting",
                content_hash="a",
            ),
            DocumentChunk(
                document_id=ready.id,
                version_number=1,
                chunk_index=1,
                text="more",
                token_count=1,
                heading_path="Counting / Detail",
                content_hash="b",
            ),
            DocumentChunk(
                document_id=ready.id,
                version_number=1,
                chunk_index=2,
                text="again",
                token_count=1,
                heading_path="Counting",
                content_hash="c",
            ),
        ]
    )
    waiting = _document(org, db_session, name="Still indexing", visibility=Visibility.department, owner=org.employee)
    waiting.content_text = "hidden until extraction finishes"
    waiting.extraction_status = ExtractionStatus.pending
    skipped = _document(org, db_session, name="Photo", visibility=Visibility.department, owner=org.employee)
    skipped.extraction_status = ExtractionStatus.skipped
    skipped.extraction_error = "Image files need OCR, which is not configured."
    db_session.flush()

    login(api, org.employee.email)
    first = api.get(f"/api/v1/documents/{ready.id}/content", params={"offset": 0, "limit": 10})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["kind"] == "document_content"
    assert body["text"] == "abcdefghij"
    assert body["offset"] == 0
    assert body["next_offset"] == 10
    assert body["total_chars"] == 30
    assert body["truncated"] is True
    assert body["extraction_status"] == "done"
    assert body["heading_outline"] == ["Counting", "Counting / Detail"]
    assert body["detail"] is None

    second = api.get(f"/api/v1/documents/{ready.id}/content", params={"offset": 10, "limit": 10})
    assert second.json()["text"] == "abcdefghij"
    assert second.json()["next_offset"] == 20
    last = api.get(f"/api/v1/documents/{ready.id}/content", params={"offset": 20, "limit": 10})
    assert last.json()["text"] == "abcdefghij"
    assert last.json()["next_offset"] is None
    assert last.json()["truncated"] is False
    past = api.get(f"/api/v1/documents/{ready.id}/content", params={"offset": 40, "limit": 10})
    assert past.json()["text"] == ""
    assert past.json()["total_chars"] == 30

    too_big = api.get(f"/api/v1/documents/{ready.id}/content", params={"limit": 50001})
    assert too_big.status_code == 422

    pending = api.get(f"/api/v1/documents/{waiting.id}/content")
    assert pending.status_code == 200, pending.text
    pending_body = pending.json()
    assert pending_body["text"] is None
    assert pending_body["extraction_status"] == "pending"
    assert pending_body["detail"] == "Text extraction has not finished."
    assert "hidden until extraction" not in pending.text

    skipped_body = api.get(f"/api/v1/documents/{skipped.id}/content").json()
    assert skipped_body["text"] is None
    assert skipped_body["extraction_status"] == "skipped"
    assert "OCR" in skipped_body["detail"]

    events = list(
        db_session.scalars(
            select(DocumentEvent).where(DocumentEvent.document_id == ready.id, DocumentEvent.event_type == EventType.read_content)
        )
    )
    assert events
    assert all("abcdefghij" not in str(event.event_metadata) for event in events)
    assert any(event.event_metadata.get("limit") == 10 for event in events)


def test_content_and_related_do_not_leak(api, org, db_session):
    tag = add_tag(db_session, name=f"zephyr-{uuid4().hex[:8]}")
    folder = add_folder(db_session, name="Shared", owner=org.employee, department=org.product, visibility=Visibility.organization)
    other = add_folder(db_session, name="Elsewhere", owner=org.sales_employee, department=org.sales, visibility=Visibility.department)
    category = add_category(db_session, name=f"Related {uuid4().hex[:8]}")
    source = add_document(
        db_session,
        name="Zephyr Habitat Manual",
        folder=folder,
        owner=org.employee,
        department=org.product,
        category=category,
        visibility=Visibility.department,
    )
    tagged = add_document(
        db_session,
        name="Warehouse ledger",
        folder=other,
        owner=org.sales_employee,
        department=org.sales,
        category=category,
        visibility=Visibility.organization,
    )
    private = add_document(
        db_session,
        name="Zephyr Habitat Manual private",
        folder=folder,
        owner=org.admin,
        department=org.product,
        category=category,
        visibility=Visibility.private,
    )
    for document in (source, tagged, private):
        db_session.add(DocumentTag(document_id=document.id, tag_id=tag.id))
    source.content_text = "qxsecret balance"
    source.extraction_status = ExtractionStatus.done
    private.content_text = "qxsecret private balance"
    private.extraction_status = ExtractionStatus.done
    db_session.flush()

    login(api, org.sales_employee.email)
    hidden = api.get(f"/api/v1/documents/{source.id}/content")
    assert_error(hidden, 404, "NOT_FOUND")
    assert_error(api.get(f"/api/v1/documents/{source.id}/related"), 404, "NOT_FOUND")
    assert_error(api.get(f"/api/v1/documents/{source.id}/ai-status"), 404, "NOT_FOUND")
    assert_error(api.get(f"/api/v1/documents/{private.id}/content"), 404, "NOT_FOUND")
    leaked = list(
        db_session.scalars(
            select(DocumentEvent).where(
                DocumentEvent.document_id == source.id,
                DocumentEvent.event_type == EventType.read_content,
                DocumentEvent.user_id == org.sales_employee.id,
            )
        )
    )
    assert leaked == []
    assert "qxsecret" not in hidden.text

    login(api, org.employee.email)
    related = api.get(f"/api/v1/documents/{source.id}/related", params={"limit": 5})
    assert related.status_code == 200, related.text
    identifiers = {item["id"] for item in related.json()["items"]}
    assert str(tagged.id) in identifiers
    assert str(private.id) not in identifiers
    assert str(source.id) not in identifiers
    assert_error(api.get(f"/api/v1/documents/{private.id}/content"), 404, "NOT_FOUND")
    match = next(item for item in related.json()["items"] if item["id"] == str(tagged.id))
    assert "tag" in match["reasons"]
    assert "qxsecret" not in related.text

    limited = api.get(f"/api/v1/documents/{source.id}/related", params={"limit": 1})
    assert len(limited.json()["items"]) == 1

    with acting_as(org.employee, set()):
        assert_error(api.get(f"/api/v1/documents/{source.id}/content"), 403, "MISSING_SCOPE")
    with acting_as(org.employee, {SCOPE_DOCS_READ}, method=AuthMethod.bearer, client_name="reader"):
        allowed = api.get(f"/api/v1/documents/{source.id}/content")
        assert allowed.status_code == 200
        assert allowed.json()["text"] == "qxsecret balance"


def test_ai_status_reindex_and_no_ai_routes(api, org, db_session, tmp_path):
    storage = LocalDiskStorage(tmp_path)
    app.dependency_overrides[get_storage] = lambda: storage
    library = _library(api, org)
    login(api, org.employee.email)
    uploaded = api.post(
        "/api/v1/documents/upload",
        data=_form(library, "Status notes", visibility="organization"),
        files={"file": ("notes.txt", text_bytes("# Counting\n\nTwelve items.\n"), "text/plain")},
        headers=CSRF,
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    login(api, org.admin.email)
    queued = api.post("/api/v1/admin/reindex", params={"document_id": document_id}, headers=CSRF)
    assert queued.status_code == 200, queued.text
    assert queued.json()["document_id"] == document_id
    assert queued.json()["status"] == "pending"
    missing = api.post("/api/v1/admin/reindex", params={"document_id": str(uuid4())}, headers=CSRF)
    assert_error(missing, 404, "NOT_FOUND")

    login(api, org.employee.email)
    assert_error(api.post("/api/v1/admin/reindex", params={"document_id": document_id}, headers=CSRF), 403, "FORBIDDEN")

    with acting_as(org.admin, {SCOPE_DOCS_READ}):
        assert_error(
            api.post("/api/v1/admin/reindex", params={"document_id": document_id}, headers=CSRF),
            403,
            "MISSING_SCOPE",
        )

    queue = PostgresIngestionQueue(pipeline=ExtractionPipeline(storage=storage))
    assert drain(queue, db_session, limit=5) >= 1
    db_session.expire_all()
    stored = db_session.get(Document, document_id)
    assert stored.extraction_status is ExtractionStatus.done
    login(api, org.employee.email)
    status = api.get(f"/api/v1/documents/{document_id}/ai-status")
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["ai_enabled"] is False
    assert body["extraction_status"] == "done"
    assert body["chunk_count"] >= 1
    assert body["extracted_at"] is not None
    content = api.get(f"/api/v1/documents/{document_id}/content")
    assert content.json()["text"]
    assert "Twelve items." in content.json()["text"]
    assert "Counting" in content.json()["heading_outline"]

    spec = api.get("/openapi.json").json()["paths"]
    assert "/api/v1/documents/{document_id}/content" in spec
    assert "/api/v1/documents/{document_id}/related" in spec
    assert "/api/v1/documents/{document_id}/ai-status" in spec
    assert "/api/v1/admin/reindex" in spec
    assert not any(path == "/api/v1/ai" or path.startswith("/api/v1/ai/") for path in spec)
    assert db_session.scalar(
        select(IngestionJob).where(IngestionJob.document_id == document_id, IngestionJob.status == JobStatus.succeeded)
    )


def _document(org, db_session, *, name, visibility, owner):
    category = add_category(db_session, name=f"{name} {uuid4().hex[:8]}")
    folder = add_folder(
        db_session,
        name=f"Folder {uuid4().hex[:6]}",
        owner=owner,
        department=org.product,
        visibility=visibility,
    )
    return add_document(
        db_session,
        name=name,
        folder=folder,
        owner=owner,
        department=org.product,
        category=category,
        visibility=visibility,
    )
