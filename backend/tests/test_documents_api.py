from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.core.enums import ActorChannel, EventType, UserRole
from app.core.events import (
    DOCUMENT_ARCHIVED,
    DOCUMENT_CREATED,
    DOCUMENT_DELETED,
    DOCUMENT_PERMISSIONS_CHANGED,
    DOCUMENT_RESTORED,
    DOCUMENT_UPDATED,
    DOCUMENT_VERSION_ADDED,
    event_bus,
)
from app.api.deps import get_storage
from app.core.principal import SCOPE_DOCS_READ, SCOPE_DOCS_WRITE, AuthMethod as PrincipalAuth, Principal
from app.integrations.storage import LocalDiskStorage
from app.main import app
from app.models import ApiToken, Document, DocumentEvent, DocumentVersion
from app.models.user import User
from app.services.activity import channel_for
from tests.blobs import office_bytes, pdf_bytes, png_bytes, text_bytes
from tests.helpers import CSRF, acting_as, assert_error, login

pytestmark = pytest.mark.usefixtures("org")


@pytest.fixture
def disk(api, tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://atlas.example")
    monkeypatch.setenv("MAX_UPLOAD_MB", "50")
    store = LocalDiskStorage(tmp_path)
    app.dependency_overrides[get_storage] = lambda: store
    yield store


def test_channel_follows_the_principal():
    user = User(id=uuid4(), email="a@company.com", name="A", role=UserRole.employee, department_id=uuid4(), is_active=True)
    assert channel_for(Principal(user=user, auth_method=PrincipalAuth.session, scopes=frozenset())) is ActorChannel.web
    assert channel_for(Principal(user=user, auth_method=PrincipalAuth.bearer, scopes=frozenset())) is ActorChannel.rest
    assert channel_for(Principal(user=user, auth_method=PrincipalAuth.oauth, scopes=frozenset())) is ActorChannel.mcp


def test_document_routes_require_auth_and_the_right_scope(api, org, disk):
    missing = uuid4()
    body = {"name": "Notes", "folder_id": str(missing), "category_id": str(missing), "department_id": str(missing), "source_type": "txt"}
    assert_error(api.get("/api/v1/documents"), 401, "UNAUTHENTICATED")
    assert_error(api.post("/api/v1/documents", json=body), 401, "UNAUTHENTICATED")
    assert_error(api.get(f"/api/v1/documents/{missing}"), 401, "UNAUTHENTICATED")
    assert_error(api.patch(f"/api/v1/documents/{missing}", json={"name": "X"}), 401, "UNAUTHENTICATED")
    assert_error(api.post(f"/api/v1/documents/{missing}/move", json={"folder_id": str(missing)}), 401, "UNAUTHENTICATED")
    assert_error(api.post(f"/api/v1/documents/{missing}/archive"), 401, "UNAUTHENTICATED")
    assert_error(api.post(f"/api/v1/documents/{missing}/restore"), 401, "UNAUTHENTICATED")
    assert_error(api.delete(f"/api/v1/documents/{missing}"), 401, "UNAUTHENTICATED")
    assert_error(api.get(f"/api/v1/documents/{missing}/permissions"), 401, "UNAUTHENTICATED")
    assert_error(api.put(f"/api/v1/documents/{missing}/permissions", json=_grants()), 401, "UNAUTHENTICATED")
    assert_error(api.get(f"/api/v1/documents/{missing}/file"), 401, "UNAUTHENTICATED")
    assert_error(api.get(f"/api/v1/documents/{missing}/versions"), 401, "UNAUTHENTICATED")
    assert_error(api.get(f"/api/v1/documents/{missing}/versions/1/file"), 401, "UNAUTHENTICATED")
    assert_error(api.post(f"/api/v1/documents/{missing}/versions/1/restore", json={}), 401, "UNAUTHENTICATED")

    with acting_as(org.employee, {SCOPE_DOCS_WRITE}):
        assert_error(api.get("/api/v1/documents"), 403, "MISSING_SCOPE")
        assert_error(api.get(f"/api/v1/documents/{missing}"), 403, "MISSING_SCOPE")
        assert_error(api.get(f"/api/v1/documents/{missing}/file"), 403, "MISSING_SCOPE")
        assert_error(api.get(f"/api/v1/documents/{missing}/versions"), 403, "MISSING_SCOPE")
    with acting_as(org.employee, {SCOPE_DOCS_READ}):
        assert_error(api.post("/api/v1/documents", json=body), 403, "MISSING_SCOPE")
        assert_error(api.patch(f"/api/v1/documents/{missing}", json={"name": "X"}), 403, "MISSING_SCOPE")
        assert_error(api.delete(f"/api/v1/documents/{missing}"), 403, "MISSING_SCOPE")
        assert_error(api.post(f"/api/v1/documents/{missing}/archive"), 403, "MISSING_SCOPE")


def test_permissions_archive_and_metadata(api, org, db_session, disk):
    library = _library(api, org)
    login(api, org.employee.email)
    created = api.post("/api/v1/documents", json=_document_body(library, "Private notes", visibility="private"), headers=CSRF)
    assert created.status_code == 201, created.text
    private = created.json()
    assert private["my_access"] == "manage"
    assert private["web_url"] == f"https://atlas.example/documents/{private['id']}"
    assert private["has_file"] is False

    login(api, org.sales_employee.email)
    assert_error(api.get(f"/api/v1/documents/{private['id']}"), 404, "NOT_FOUND")
    assert_error(api.patch(f"/api/v1/documents/{private['id']}", json={"name": "Stolen"}, headers=CSRF), 404, "NOT_FOUND")
    assert_error(api.get(f"/api/v1/documents/{private['id']}/permissions"), 404, "NOT_FOUND")
    assert_error(api.get(f"/api/v1/documents/{private['id']}/file"), 404, "NOT_FOUND")
    assert_error(api.get(f"/api/v1/documents/{private['id']}/versions"), 404, "NOT_FOUND")
    assert api.get("/api/v1/documents").json()["total"] == 0

    login(api, org.employee.email)
    shared = api.post(
        "/api/v1/documents",
        json=_document_body(library, "Handbook", visibility="organization", default_access="view"),
        headers=CSRF,
    ).json()
    login(api, org.sales_employee.email)
    viewed = api.get(f"/api/v1/documents/{shared['id']}")
    assert viewed.status_code == 200, viewed.text
    assert viewed.json()["my_access"] == "view"
    assert_error(api.patch(f"/api/v1/documents/{shared['id']}", json={"name": "Edited"}, headers=CSRF), 403, "FORBIDDEN")
    assert_error(api.post(f"/api/v1/documents/{shared['id']}/archive", headers=CSRF), 403, "FORBIDDEN")
    assert_error(api.post(f"/api/v1/documents/{shared['id']}/move", json={"folder_id": library["folder_id"]}, headers=CSRF), 403, "FORBIDDEN")
    assert_error(
        api.put(f"/api/v1/documents/{shared['id']}/permissions", json=_grants(), headers=CSRF),
        403,
        "FORBIDDEN",
    )

    login(api, org.manager.email)
    archived = api.post(f"/api/v1/documents/{shared['id']}/archive", headers=CSRF)
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    login(api, org.sales_employee.email)
    assert_error(api.get(f"/api/v1/documents/{shared['id']}"), 404, "NOT_FOUND")
    login(api, org.sales_manager.email)
    assert_error(api.get(f"/api/v1/documents/{shared['id']}"), 404, "NOT_FOUND")
    login(api, org.manager.email)
    assert api.get(f"/api/v1/documents/{shared['id']}").status_code == 200
    assert_error(api.patch(f"/api/v1/documents/{shared['id']}", json={"description": "Later"}, headers=CSRF), 409, "ARCHIVED")
    restored = api.post(f"/api/v1/documents/{shared['id']}/restore", headers=CSRF)
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "active"

    login(api, org.employee.email)
    removed = api.delete(f"/api/v1/documents/{private['id']}", headers=CSRF)
    assert removed.status_code == 204, removed.text
    assert_error(api.get(f"/api/v1/documents/{private['id']}"), 404, "NOT_FOUND")
    db_session.expire_all()
    assert db_session.get(Document, private["id"]).deleted_at is not None


def test_events_search_permissions_and_list(api, org, db_session, disk):
    library = _library(api, org)
    seen = []

    def remember(event):
        def handler(payload):
            seen.append((event, payload))

        return handler

    for event_name in (
        DOCUMENT_CREATED,
        DOCUMENT_UPDATED,
        DOCUMENT_PERMISSIONS_CHANGED,
        DOCUMENT_ARCHIVED,
        DOCUMENT_RESTORED,
        DOCUMENT_DELETED,
    ):
        event_bus.subscribe(event_name, remember(event_name))
    login(api, org.employee.email)
    failed = api.post("/api/v1/documents", json=_document_body(library, "Missing", folder_id=str(uuid4())), headers=CSRF)
    assert_error(failed, 404, "NOT_FOUND")
    assert seen == []

    created = api.post(
        "/api/v1/documents",
        json=_document_body(library, "Inventory handbook", tag_ids=[library["tag_id"]]),
        headers=CSRF,
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["id"]
    assert seen[-1] == (DOCUMENT_CREATED, {"document_id": document_id, "actor_id": str(org.employee.id)})
    event = _events(db_session, document_id, EventType.create)[-1]
    assert event.actor_channel is ActorChannel.web
    assert event.token_id is None
    assert event.client_name is None

    renamed = api.patch(f"/api/v1/documents/{document_id}", json={"name": "qxylophonezz handbook"}, headers=CSRF)
    assert renamed.status_code == 200, renamed.text
    assert (DOCUMENT_UPDATED, {"document_id": document_id, "actor_id": str(org.employee.id)}) in [
        (name, {"document_id": payload["document_id"], "actor_id": payload["actor_id"]}) for name, payload in seen
    ]
    db_session.expire_all()
    matched = db_session.scalar(
        text("SELECT search_vector @@ plainto_tsquery('english', 'qxylophonezz') FROM documents WHERE id = :id"),
        {"id": document_id},
    )
    assert matched is True

    calls = []

    def spy(session, watched_id):
        calls.append(watched_id)

    from app.services import search as search_module

    real = search_module.refresh_search_vector

    def wrapped(session, watched_id):
        calls.append(watched_id)
        return real(session, watched_id)

    # Department-only edits must not rebuild the vector. Null it, then prove it stays null.
    db_session.execute(text("UPDATE documents SET search_vector = NULL WHERE id = :id"), {"id": document_id})
    db_session.flush()
    from app.services import documents as document_service

    original = document_service.refresh_search_vector
    document_service.refresh_search_vector = spy
    try:
        department = api.patch(
            f"/api/v1/documents/{document_id}",
            json={"department_id": str(org.product.id)},
            headers=CSRF,
        )
        assert department.status_code == 200, department.text
        assert calls == []
    finally:
        document_service.refresh_search_vector = original
    db_session.expire_all()
    assert db_session.get(Document, document_id).search_vector is None

    tagged = api.patch(f"/api/v1/documents/{document_id}", json={"name": "qxylophonezz handbook", "tag_ids": []}, headers=CSRF)
    assert tagged.status_code == 200, tagged.text
    login(api, org.admin.email)
    category = api.post("/api/v1/categories", json={"name": "Zephyrical"}, headers=CSRF)
    assert category.status_code == 201, category.text
    login(api, org.employee.email)
    recategorized = api.patch(
        f"/api/v1/documents/{document_id}",
        json={"category_id": category.json()["id"]},
        headers=CSRF,
    )
    assert recategorized.status_code == 200, recategorized.text
    db_session.expire_all()
    assert db_session.scalar(
        text("SELECT search_vector @@ plainto_tsquery('english', 'zephyrical') FROM documents WHERE id = :id"),
        {"id": document_id},
    )

    rejected = api.put(
        f"/api/v1/documents/{document_id}/permissions",
        json={"visibility": "private", "default_access": "view", "grants": [
            {"principal_type": "user", "principal_id": str(uuid4()), "access": "edit"}
        ]},
        headers=CSRF,
    )
    assert_error(rejected, 422, "UNKNOWN_PRINCIPAL")
    replaced = api.put(
        f"/api/v1/documents/{document_id}/permissions",
        json={
            "visibility": "custom",
            "default_access": "view",
            "grants": [
                {"principal_type": "user", "principal_id": str(org.guest.id), "access": "edit"},
                {"principal_type": "department", "principal_id": str(org.sales.id), "access": "view"},
            ],
        },
        headers=CSRF,
    )
    assert replaced.status_code == 200, replaced.text
    assert len(replaced.json()["grants"]) == 2
    assert any(name == DOCUMENT_PERMISSIONS_CHANGED and payload["document_id"] == document_id for name, payload in seen)
    share = _events(db_session, document_id, EventType.share)[-1]
    assert share.event_metadata["grant_count"] == 2

    with acting_as(org.guest, {SCOPE_DOCS_WRITE}, method=PrincipalAuth.bearer, client_name="Cursor"):
        edited = api.patch(f"/api/v1/documents/{document_id}", json={"description": "Guest edit"}, headers=CSRF)
        assert edited.status_code == 200, edited.text
        assert edited.json()["my_access"] == "edit"
    guest_event = _events(db_session, document_id, EventType.update)[-1]
    assert guest_event.actor_channel is ActorChannel.rest
    assert guest_event.client_name == "Cursor"

    login(api, org.guest.email)
    assert_error(api.patch(f"/api/v1/documents/{document_id}", json={"description": "No"}, headers=CSRF), 403, "MISSING_SCOPE")
    assert api.get(f"/api/v1/documents/{document_id}").status_code == 200

    login(api, org.employee.email)
    listed = api.get("/api/v1/documents", params={"type": "txt", "owner_id": str(org.employee.id), "tag_id": library["tag_id"]})
    # tags were cleared, so the tag filter excludes it
    assert listed.json()["total"] == 0
    page = api.get(
        "/api/v1/documents",
        params={"folder_id": library["folder_id"], "department_id": str(org.product.id), "category_id": category.json()["id"], "sort": "name"},
    )
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 1
    assert page.json()["items"][0]["id"] == document_id

    archived = api.post(f"/api/v1/documents/{document_id}/archive", headers=CSRF)
    assert archived.status_code == 200
    active = api.get("/api/v1/documents", params={"folder_id": library["folder_id"]})
    assert active.json()["total"] == 0
    filed = api.get("/api/v1/documents", params={"status": "archived", "owner_id": str(org.employee.id)})
    assert filed.json()["total"] == 1
    api.post(f"/api/v1/documents/{document_id}/restore", headers=CSRF)
    api.delete(f"/api/v1/documents/{document_id}", headers=CSRF)
    emitted = {name for name, payload in seen if payload["document_id"] == document_id}
    assert emitted == {
        DOCUMENT_CREATED,
        DOCUMENT_UPDATED,
        DOCUMENT_PERMISSIONS_CHANGED,
        DOCUMENT_ARCHIVED,
        DOCUMENT_RESTORED,
        DOCUMENT_DELETED,
    }


def test_uploads_versions_and_streams(api, org, db_session, disk, monkeypatch):
    library = _library(api, org)
    seen = []
    event_bus.subscribe(DOCUMENT_CREATED, seen.append)
    event_bus.subscribe(DOCUMENT_VERSION_ADDED, seen.append)
    login(api, org.employee.email)
    uploaded = api.post(
        "/api/v1/documents/upload",
        data=_form(library, "Notes", visibility="private"),
        files={"file": ("../../secret notes.txt", text_bytes("alpha line"), "application/pdf")},
        headers=CSRF,
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["source_type"] == "txt"
    assert body["mime_type"] == "text/plain"
    assert body["original_filename"] == "secret notes.txt"
    assert "secret" not in _storage_key(db_session, body["id"])
    assert len(seen) == 2

    streamed = api.get(f"/api/v1/documents/{body['id']}/file")
    assert streamed.status_code == 200, streamed.text
    assert streamed.content == text_bytes("alpha line")
    assert streamed.headers["content-type"].startswith("text/plain")
    disposition = streamed.headers["content-disposition"]
    assert disposition.startswith("inline;")
    assert "secret notes.txt" in disposition
    download = _events(db_session, body["id"], EventType.download)[-1]
    assert download.actor_channel is ActorChannel.web
    assert download.event_metadata["version_number"] == 1

    picture = api.post(
        "/api/v1/documents/upload",
        data=_form(library, "Diagram", visibility="organization", default_access="view"),
        files={"file": ("diagram.png", png_bytes(), "text/plain")},
        headers=CSRF,
    )
    assert picture.status_code == 201, picture.text
    image = api.get(f"/api/v1/documents/{picture.json()['id']}/file")
    assert image.headers["content-disposition"].startswith("inline;")
    assert image.headers["content-type"].startswith("image/png")

    slides = api.post(
        "/api/v1/documents/upload",
        data=_form(library, "Deck", visibility="department"),
        files={"file": ("deck.pptx", office_bytes("pptx"), "application/octet-stream")},
        headers=CSRF,
    )
    assert slides.status_code == 201, slides.text
    assert slides.json()["source_type"] == "ppt"
    attachment = api.get(f"/api/v1/documents/{slides.json()['id']}/file")
    assert attachment.headers["content-disposition"].startswith("attachment;")

    login(api, org.sales_employee.email)
    assert_error(api.get(f"/api/v1/documents/{body['id']}/file"), 404, "NOT_FOUND")
    assert_error(
        api.post(
            f"/api/v1/documents/{picture.json()['id']}/versions",
            files={"file": ("diagram.png", png_bytes(), "image/png")},
            headers=CSRF,
        ),
        403,
        "FORBIDDEN",
    )

    login(api, org.employee.email)
    mismatch = api.post(
        f"/api/v1/documents/{body['id']}/versions",
        files={"file": ("notes.pdf", pdf_bytes(), "application/pdf")},
        data={"change_note": "wrong type"},
        headers=CSRF,
    )
    assert_error(mismatch, 415, "TYPE_MISMATCH")
    second = api.post(
        f"/api/v1/documents/{body['id']}/versions",
        files={"file": ("notes.txt", text_bytes("beta line"), "text/plain")},
        data={"change_note": "Second draft"},
        headers=CSRF,
    )
    assert second.status_code == 201, second.text
    assert second.json()["current_version_number"] == 2
    versions = api.get(f"/api/v1/documents/{body['id']}/versions")
    assert [item["version_number"] for item in versions.json()] == [2, 1]
    restored = api.post(f"/api/v1/documents/{body['id']}/versions/1/restore", json={"change_note": "Back to alpha"}, headers=CSRF)
    assert restored.status_code == 201, restored.text
    assert restored.json()["current_version_number"] == 3
    current = api.get(f"/api/v1/documents/{body['id']}/file")
    assert current.content == text_bytes("alpha line")
    first = api.get(f"/api/v1/documents/{body['id']}/versions/1/file")
    older = api.get(f"/api/v1/documents/{body['id']}/versions/2/file")
    assert first.content == text_bytes("alpha line")
    assert older.content == text_bytes("beta line")
    db_session.expire_all()
    keys = set(db_session.scalars(select(DocumentVersion.storage_key).where(DocumentVersion.document_id == body["id"])))
    assert len(keys) == 3
    assert None not in keys

    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    oversized = api.post(
        "/api/v1/documents/upload",
        data=_form(library, "Huge"),
        files={"file": ("huge.txt", b"a" * (1024 * 1024 + 1), "text/plain")},
        headers=CSRF,
    )
    assert_error(oversized, 413, "FILE_TOO_LARGE")
    empty = api.post(
        "/api/v1/documents/upload",
        data=_form(library, "Empty"),
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=CSRF,
    )
    assert_error(empty, 422, "EMPTY_FILE")
    binary = api.post(
        "/api/v1/documents/upload",
        data=_form(library, "Binary"),
        files={"file": ("data.bin", b"\x00\x01\x02", "application/octet-stream")},
        headers=CSRF,
    )
    assert_error(binary, 415, "UNSUPPORTED_FILE_TYPE")


def test_openapi_tags_and_examples(api):
    spec = api.get("/openapi.json").json()
    tags = {tag["name"]: tag.get("description", "") for tag in spec["tags"]}
    assert "folder" in tags["folders"].lower()
    assert "my_access" in tags["documents"]
    schemas = spec["components"]["schemas"]
    assert schemas["FolderCreate"]["examples"]
    assert schemas["DocumentCreate"]["examples"]
    assert schemas["DocumentRead"]["examples"][0]["my_access"]
    assert "web_url" in schemas["DocumentRead"]["examples"][0]
    assert schemas["PermissionsUpdate"]["examples"]
    assert "/api/v1/documents/{document_id}/file" in spec["paths"]
    assert "/api/v1/folders/tree" in spec["paths"]


def test_list_uses_the_access_filter(api, org, disk, monkeypatch):
    from sqlalchemy import false as sql_false

    library = _library(api, org)
    login(api, org.admin.email)
    created = api.post("/api/v1/documents", json=_document_body(library, "Visible"), headers=CSRF)
    assert created.status_code == 201, created.text
    monkeypatch.setattr("app.services.documents.accessible_documents_query", lambda *args, **kwargs: sql_false())
    assert api.get("/api/v1/documents").json()["items"] == []


def _library(api, org):
    login(api, org.admin.email)
    category = api.post("/api/v1/categories", json={"name": f"Guides {uuid4().hex[:8]}"}, headers=CSRF)
    tag = api.post("/api/v1/tags", json={"name": f"Inventory {uuid4().hex[:8]}"}, headers=CSRF)
    folder = api.post(
        "/api/v1/folders",
        json={
            "name": "Library",
            "parent_id": None,
            "department_id": str(org.product.id),
            "visibility": "organization",
            "default_access": "edit",
        },
        headers=CSRF,
    )
    assert category.status_code == 201, category.text
    assert tag.status_code == 201, tag.text
    assert folder.status_code == 201, folder.text
    return {
        "category_id": category.json()["id"],
        "tag_id": tag.json()["id"],
        "folder_id": folder.json()["id"],
        "department_id": str(org.product.id),
    }


def _document_body(library, name, **overrides):
    body = {
        "name": name,
        "description": name,
        "folder_id": library["folder_id"],
        "category_id": library["category_id"],
        "department_id": library["department_id"],
        "source_type": "txt",
        "visibility": "department",
        "default_access": "view",
        "tag_ids": [],
    }
    body.update(overrides)
    return body


def _form(library, name, **overrides):
    body = _document_body(library, name, **overrides)
    return {
        "name": body["name"],
        "description": body["description"],
        "folder_id": body["folder_id"],
        "category_id": body["category_id"],
        "department_id": body["department_id"],
        "visibility": body["visibility"],
        "default_access": body["default_access"],
    }


def _grants():
    return {"visibility": "private", "default_access": "view", "grants": []}


def _events(session, document_id, event_type):
    return list(
        session.scalars(
            select(DocumentEvent).where(DocumentEvent.document_id == document_id, DocumentEvent.event_type == event_type)
        )
    )


def _storage_key(session, document_id):
    return session.get(Document, document_id).storage_key
