"""Google Drive linking, embedding, and permission sync. The fake client stands in for Google."""

import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.enums import (
    AccessGrant,
    DocumentStatus,
    DriveSyncStatus,
    EventType,
    JobStatus,
    PrincipalType,
    SourceType,
    Visibility,
)
from app.core.principal import SCOPE_DOCS_READ, SCOPE_DOCS_WRITE, AuthMethod
from app.integrations.drive import (
    DEFAULT_SERVICE_ACCOUNT_EMAIL,
    MIME_DOCUMENT,
    DriveForbidden,
    DrivePermission,
    InvalidGoogleUrl,
    ServiceAccountDriveClient,
    build_drive_client,
    google_urls,
    parse_google_file_reference,
    parse_google_url,
    reset_fake_drive_client,
    service_account_info,
)
from app.integrations.drive_sync import (
    compute_desired_permissions,
    plan_drive_changes,
    reconcile_drive_sync,
    sync_document_sharing,
)
from app.models import Document, DocumentEvent, IngestionJob
from tests.helpers import CSRF, acting_as, assert_error, login
from tests.library import add_category, add_document, add_folder

FILE_ID = "1AbCdEfGhIjKlMnOpQrSt"
SHARED_FOLDER = "shared-drive-folder"
SERVICE_EMAIL = DEFAULT_SERVICE_ACCOUNT_EMAIL


@pytest.fixture
def drive(monkeypatch):
    monkeypatch.setenv("GOOGLE_MODE", "fake")
    monkeypatch.setenv("COMPANY_DOMAIN", "company.com")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "company.com")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", SERVICE_EMAIL)
    monkeypatch.setenv("GOOGLE_SHARED_DRIVE_FOLDER_ID", SHARED_FOLDER)
    reset_fake_drive_client()
    return build_drive_client()


@pytest.mark.parametrize(
    ("url", "source", "file_id"),
    [
        ("https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrSt/edit", SourceType.google_doc, FILE_ID),
        ("https://docs.google.com/document/u/0/d/1AbCdEfGhIjKlMnOpQrSt/edit", SourceType.google_doc, FILE_ID),
        ("https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrSt/view?usp=sharing", SourceType.google_doc, FILE_ID),
        ("https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrSt/preview", SourceType.google_doc, FILE_ID),
        ("https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrSt/", SourceType.google_doc, FILE_ID),
        ("HTTPS://DOCS.GOOGLE.COM/DOCUMENT/d/1AbCdEfGhIjKlMnOpQrSt/EDIT?usp=sharing", SourceType.google_doc, FILE_ID),
        ("https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrSt/edit#gid=0", SourceType.google_sheet, FILE_ID),
        (
            "https://docs.google.com/presentation/u/1/d/1AbCdEfGhIjKlMnOpQrSt/preview?usp=sharing",
            SourceType.google_slide,
            FILE_ID,
        ),
        ("  https://docs.google.com/document/d/AbC-_1234567890/edit  ", SourceType.google_doc, "AbC-_1234567890"),
    ],
)
def test_parse_google_urls(url, source, file_id):
    parsed = parse_google_url(url)
    assert parsed.source_type is source
    assert parsed.file_id == file_id
    assert parse_google_file_reference(url) == file_id


def test_reject_invalid_google_urls():
    for value in (
        "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrSt/view",
        "http://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrSt/edit",
        "https://docs.google.com/document/d/short/edit",
        "https://example.com/document/d/1AbCdEfGhIjKlMnOpQrSt/edit",
        "not a url",
        "",
    ):
        with pytest.raises(InvalidGoogleUrl):
            parse_google_url(value)
    assert parse_google_file_reference(FILE_ID) == FILE_ID


def test_preview_paths_follow_the_file_type():
    assert google_urls(SourceType.google_doc, FILE_ID).preview_url == f"https://docs.google.com/document/d/{FILE_ID}/preview"
    assert google_urls(SourceType.google_sheet, FILE_ID).preview_url == f"https://docs.google.com/spreadsheets/d/{FILE_ID}/preview"
    assert google_urls(SourceType.google_slide, FILE_ID).preview_url == f"https://docs.google.com/presentation/d/{FILE_ID}/preview"
    assert google_urls(SourceType.google_doc, FILE_ID).edit_url.endswith("/edit")


def test_link_requires_the_file_to_be_shared(api, org, drive):
    library = _library(api, org)
    login(api, org.employee.email)
    response = api.post("/api/v1/documents/google/link", json=_link_body(library, FILE_ID), headers=CSRF)
    detail = assert_error(response, 422, "GOOGLE_NOT_SHARED")
    assert detail["details"]["service_account_email"] == SERVICE_EMAIL
    assert SERVICE_EMAIL in detail["message"]
    assert detail["details"]["google_file_id"] == FILE_ID
    assert api.get("/api/v1/documents").json()["total"] == 0


def test_duplicate_link_returns_the_existing_document(api, org, db_session, drive):
    library = _library(api, org)
    drive.seed_file(FILE_ID, name="Inventory handbook", mime_type=MIME_DOCUMENT)
    login(api, org.employee.email)
    url = f"https://docs.google.com/document/u/0/d/{FILE_ID}/edit?usp=sharing"
    created = api.post("/api/v1/documents/google/link", json=_link_body(library, FILE_ID, url=url), headers=CSRF)
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Inventory handbook"
    assert created.json()["source_type"] == "google_doc"
    again = api.post("/api/v1/documents/google/link", json=_link_body(library, FILE_ID, url=url), headers=CSRF)
    detail = assert_error(again, 409, "DUPLICATE_GOOGLE_FILE")
    assert detail["details"]["document_id"] == created.json()["id"]
    db_session.expire_all()
    stored = db_session.get(Document, created.json()["id"])
    assert stored.drive_sync_status is DriveSyncStatus.synced
    assert stored.google_web_url == f"https://docs.google.com/document/d/{FILE_ID}/edit"


def test_invalid_link_is_rejected(api, org, drive):
    library = _library(api, org)
    login(api, org.employee.email)
    response = api.post(
        "/api/v1/documents/google/link",
        json=_link_body(library, FILE_ID, url="https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrSt/view"),
        headers=CSRF,
    )
    assert_error(response, 422, "INVALID_GOOGLE_URL")


def test_create_google_file_in_the_shared_drive(api, org, db_session, drive):
    library = _library(api, org)
    template_id = "templateFile12345"
    drive.seed_file(template_id, name="Template", mime_type=MIME_DOCUMENT, text="boilerplate")
    login(api, org.employee.email)
    created = api.post(
        "/api/v1/documents/google/create",
        json=_create_body(library, "Roadmap", kind="doc", template=template_id),
        headers=CSRF,
    )
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Roadmap"
    assert created.json()["source_type"] == "google_doc"
    db_session.expire_all()
    stored = db_session.get(Document, created.json()["id"])
    assert stored.google_file_id != template_id
    assert stored.drive_sync_status is DriveSyncStatus.synced
    copied = drive.files[stored.google_file_id]
    assert copied.parents == (SHARED_FOLDER,)
    assert copied.mime_type == MIME_DOCUMENT
    assert drive.export_text(stored.google_file_id) == "boilerplate"
    assert _shares(drive, stored.google_file_id)[org.employee.email] == "writer"
    assert org.bot.email not in _shares(drive, stored.google_file_id)

    mismatch = api.post(
        "/api/v1/documents/google/create",
        json=_create_body(library, "Wrong", kind="sheet", template=template_id),
        headers=CSRF,
    )
    assert_error(mismatch, 422, "GOOGLE_TYPE_MISMATCH")


def test_embed_urls_view_event_and_reextraction(api, org, db_session, drive):
    library = _library(api, org)
    login(api, org.employee.email)
    created = api.post("/api/v1/documents/google/create", json=_create_body(library, "Notes", kind="doc"), headers=CSRF)
    assert created.status_code == 201, created.text
    document_id = created.json()["id"]
    db_session.expire_all()
    stored = db_session.get(Document, document_id)
    db_session.execute(delete(IngestionJob).where(IngestionJob.document_id == stored.id))
    db_session.flush()
    drive.files[stored.google_file_id].modified_time = datetime(2030, 1, 1, tzinfo=UTC)

    embedded = api.get(f"/api/v1/documents/{document_id}/embed")
    assert embedded.status_code == 200, embedded.text
    body = embedded.json()
    file_id = stored.google_file_id
    assert body["preview_url"] == f"https://docs.google.com/document/d/{file_id}/preview"
    assert body["edit_url"] == f"https://docs.google.com/document/d/{file_id}/edit"
    assert body["open_url"] == body["edit_url"]
    db_session.expire_all()
    stored = db_session.get(Document, document_id)
    assert stored.last_modified_at == datetime(2030, 1, 1, tzinfo=UTC)
    job = db_session.scalar(select(IngestionJob).where(IngestionJob.document_id == stored.id, IngestionJob.job_type == "extract"))
    assert job is not None
    assert job.status is JobStatus.pending
    views = list(
        db_session.scalars(select(DocumentEvent).where(DocumentEvent.document_id == stored.id, DocumentEvent.event_type == EventType.view))
    )
    assert len(views) == 1
    assert views[0].event_metadata["surface"] == "embed"

    sheet = api.post("/api/v1/documents/google/create", json=_create_body(library, "Grid", kind="sheet"), headers=CSRF)
    assert sheet.status_code == 201, sheet.text
    sheet_embed = api.get(f"/api/v1/documents/{sheet.json()['id']}/embed")
    assert "/spreadsheets/" in sheet_embed.json()["preview_url"]
    assert sheet_embed.json()["preview_url"].endswith("/preview")


def test_embed_hides_edit_url_until_the_caller_can_edit(api, org, drive):
    library = _library(api, org)
    login(api, org.employee.email)
    created = api.post(
        "/api/v1/documents/google/create",
        json=_create_body(library, "Company notes", kind="slide", visibility="organization"),
        headers=CSRF,
    )
    assert created.status_code == 201, created.text
    login(api, org.sales_employee.email)
    embedded = api.get(f"/api/v1/documents/{created.json()['id']}/embed")
    assert embedded.status_code == 200, embedded.text
    assert embedded.json()["edit_url"] is None
    assert embedded.json()["preview_url"].startswith("https://docs.google.com/presentation/d/")
    assert embedded.json()["preview_url"].endswith("/preview")
    assert embedded.json()["open_url"].endswith("/edit")

    login(api, org.employee.email)
    hidden = api.post(
        "/api/v1/documents/google/create",
        json=_create_body(library, "Secret", kind="doc", visibility="private"),
        headers=CSRF,
    )
    login(api, org.sales_employee.email)
    assert_error(api.get(f"/api/v1/documents/{hidden.json()['id']}/embed"), 404, "NOT_FOUND")


def test_desired_permissions_diff_against_drive(db_session, org, drive):
    document = _google_document(db_session, org, visibility=Visibility.department)
    file_id = document.google_file_id
    drive.seed_file(
        file_id,
        mime_type=MIME_DOCUMENT,
        owners=(SERVICE_EMAIL, "original-owner@gmail.com"),
        permissions=[
            *drive.default_permissions(file_id),
            DrivePermission(id="human-owner", type="user", role="writer", email="original-owner@gmail.com"),
            DrivePermission(id="stray-perm", type="user", role="writer", email="stray@company.com"),
            DrivePermission(id="manager-perm", type="user", role="commenter", email=org.manager.email),
        ],
    )
    desired = compute_desired_permissions(db_session, document)
    assert desired.users[org.employee.email] == "writer"
    assert desired.users[org.admin.email] == "writer"
    assert desired.users[org.super_admin.email] == "writer"
    assert desired.users[org.manager.email] == "writer"
    assert org.bot.email not in desired.users
    assert org.guest.email not in desired.users
    assert org.deactivated.email not in desired.users
    assert org.sales_employee.email not in desired.users
    assert desired.domain is None

    changes = plan_drive_changes(
        desired,
        drive.list_permissions(file_id),
        service_account_email=drive.service_account_email,
        owner_emails=set(drive.files[file_id].owner_emails),
    )
    deleted = {change.permission_id for change in changes if change.op == "delete"}
    updated = {change.permission_id: change.role for change in changes if change.op == "update"}
    created = {change.email for change in changes if change.op == "create"}
    assert "stray-perm" in deleted
    assert "owner-" + file_id not in deleted
    assert "member-" + file_id not in deleted
    assert "human-owner" not in deleted
    assert updated["manager-perm"] == "writer"
    assert org.admin.email in created
    assert org.bot.email not in created

    sync_document_sharing(db_session, document, drive)
    shares = _shares(drive, file_id)
    assert shares[org.manager.email] == "writer"
    assert shares[org.employee.email] == "writer"
    assert shares[org.admin.email] == "writer"
    assert shares[org.super_admin.email] == "writer"
    assert "stray@company.com" not in shares
    assert "domain:company.com" not in shares
    ids = {permission.id: permission for permission in drive.list_permissions(file_id)}
    assert ids["human-owner"].role == "writer"
    assert ids[f"owner-{file_id}"].role == "owner"
    assert ids[f"member-{file_id}"].inherited is True
    assert document.drive_sync_status is DriveSyncStatus.synced


def test_organization_visibility_is_one_domain_share(db_session, org, drive):
    document = _google_document(db_session, org, visibility=Visibility.organization, default_access=AccessGrant.view)
    drive.seed_file(document.google_file_id, mime_type=MIME_DOCUMENT)
    desired = compute_desired_permissions(db_session, document)
    assert desired.domain == "company.com"
    assert desired.domain_role == "reader"
    assert org.guest.email not in desired.users
    assert org.sales_employee.email not in desired.users
    assert desired.users[org.manager.email] == "writer"

    document.default_access = AccessGrant.edit
    assert compute_desired_permissions(db_session, document).domain_role == "writer"
    document.default_access = AccessGrant.view
    sync_document_sharing(db_session, document, drive)
    shares = _shares(drive, document.google_file_id)
    assert shares["domain:company.com"] == "reader"
    assert sum(1 for key in shares if key.startswith("domain:")) == 1
    assert org.guest.email not in shares
    assert org.sales_employee.email not in shares


def test_guest_is_an_individual_share(db_session, org, drive):
    document = _google_document(
        db_session,
        org,
        visibility=Visibility.custom,
        grants=((PrincipalType.user, org.guest.id, AccessGrant.edit),),
    )
    drive.seed_file(document.google_file_id, mime_type=MIME_DOCUMENT)
    sync_document_sharing(db_session, document, drive)
    shares = _shares(drive, document.google_file_id)
    assert shares[org.guest.email] == "writer"
    assert org.sales_employee.email not in shares
    assert org.sales_manager.email not in shares
    assert "domain:company.com" not in shares
    assert shares[org.manager.email] == "writer"


def test_bots_are_not_shared_on_drive(db_session, org, drive):
    document = _google_document(
        db_session,
        org,
        visibility=Visibility.department,
        grants=((PrincipalType.user, org.bot.id, AccessGrant.edit),),
    )
    drive.seed_file(
        document.google_file_id,
        mime_type=MIME_DOCUMENT,
        permissions=[
            *drive.default_permissions(document.google_file_id),
            DrivePermission(id="bot-perm", type="user", role="writer", email=org.bot.email),
        ],
    )
    desired = compute_desired_permissions(db_session, document)
    assert org.bot.email not in desired.users
    sync_document_sharing(db_session, document, drive)
    shares = _shares(drive, document.google_file_id)
    assert org.bot.email not in shares
    assert shares[org.employee.email] == "writer"
    assert org.deactivated.email not in shares


def test_archive_revokes_drive_access(api, org, db_session, drive):
    library = _library(api, org)
    login(api, org.employee.email)
    created = api.post(
        "/api/v1/documents/google/create",
        json=_create_body(library, "Handbook", visibility="department"),
        headers=CSRF,
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["id"]
    db_session.expire_all()
    file_id = db_session.get(Document, document_id).google_file_id
    assert _shares(drive, file_id)[org.manager.email] == "writer"

    archived = api.post(f"/api/v1/documents/{document_id}/archive", headers=CSRF)
    assert archived.status_code == 200, archived.text
    shares = _shares(drive, file_id)
    assert org.manager.email not in shares
    assert org.guest.email not in shares
    assert shares[org.employee.email] == "writer"
    assert shares[org.admin.email] == "writer"
    assert shares[org.super_admin.email] == "writer"
    assert drive.files[file_id].trashed is False
    assert any(permission.role == "owner" and permission.email == SERVICE_EMAIL for permission in drive.list_permissions(file_id))


def test_soft_delete_keeps_the_file_and_limits_shares(api, org, db_session, drive):
    library = _library(api, org)
    login(api, org.employee.email)
    created = api.post("/api/v1/documents/google/create", json=_create_body(library, "Notes"), headers=CSRF)
    document_id = created.json()["id"]
    removed = api.delete(f"/api/v1/documents/{document_id}", headers=CSRF)
    assert removed.status_code == 204, removed.text
    db_session.expire_all()
    stored = db_session.get(Document, document_id)
    assert stored.deleted_at is not None
    assert drive.files[stored.google_file_id].trashed is False
    shares = _shares(drive, stored.google_file_id)
    assert org.manager.email not in shares
    assert shares[org.employee.email] == "writer"
    assert shares[org.admin.email] == "writer"


def test_deactivating_a_user_removes_their_drive_share(api, org, db_session, drive):
    library = _library(api, org)
    login(api, org.employee.email)
    created = api.post("/api/v1/documents/google/create", json=_create_body(library, "Notes"), headers=CSRF)
    db_session.expire_all()
    file_id = db_session.get(Document, created.json()["id"]).google_file_id
    assert _shares(drive, file_id)[org.manager.email] == "writer"
    login(api, org.super_admin.email)
    blocked = api.post(f"/api/v1/users/{org.manager.id}/deactivate", headers=CSRF)
    assert blocked.status_code == 200, blocked.text
    assert org.manager.email not in _shares(drive, file_id)


def test_private_documents_share_only_owner_and_admins(db_session, org, drive):
    document = _google_document(db_session, org, visibility=Visibility.private)
    drive.seed_file(document.google_file_id, mime_type=MIME_DOCUMENT)
    sync_document_sharing(db_session, document, drive)
    shares = _shares(drive, document.google_file_id)
    assert set(shares) == {org.employee.email, org.admin.email, org.super_admin.email}
    assert all(role == "writer" for role in shares.values())


def test_resync_repairs_drift_and_requires_manage(api, org, db_session, drive):
    library = _library(api, org)
    login(api, org.employee.email)
    created = api.post(
        "/api/v1/documents/google/create",
        json=_create_body(library, "Company", visibility="organization"),
        headers=CSRF,
    )
    document_id = created.json()["id"]
    db_session.expire_all()
    file_id = db_session.get(Document, document_id).google_file_id
    domain = next(permission for permission in drive.list_permissions(file_id) if permission.type == "domain")
    drive.delete_permission(file_id, domain.id)
    assert "domain:company.com" not in _shares(drive, file_id)

    repaired = api.post(f"/api/v1/documents/{document_id}/resync", headers=CSRF)
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["drive_sync_status"] == "synced"
    assert _shares(drive, file_id)["domain:company.com"] == "reader"

    login(api, org.sales_employee.email)
    assert_error(api.post(f"/api/v1/documents/{document_id}/resync", headers=CSRF), 403, "FORBIDDEN")


def test_permanent_delete_trashes_the_drive_file(api, org, db_session, drive):
    library = _library(api, org)
    login(api, org.employee.email)
    created = api.post("/api/v1/documents/google/create", json=_create_body(library, "Old notes"), headers=CSRF)
    document_id = created.json()["id"]
    assert_error(api.post(f"/api/v1/documents/{document_id}/permanent-delete", headers=CSRF), 409, "NOT_ARCHIVED")
    assert api.post(f"/api/v1/documents/{document_id}/archive", headers=CSRF).status_code == 200
    assert_error(api.post(f"/api/v1/documents/{document_id}/permanent-delete", headers=CSRF), 403, "FORBIDDEN")

    login(api, org.admin.email)
    removed = api.post(f"/api/v1/documents/{document_id}/permanent-delete", headers=CSRF)
    assert removed.status_code == 204, removed.text
    db_session.expire_all()
    stored = db_session.get(Document, document_id)
    assert stored.deleted_at is not None
    assert drive.files[stored.google_file_id].trashed is True
    assert_error(api.get(f"/api/v1/documents/{document_id}/embed"), 404, "NOT_FOUND")

    other = api.post("/api/v1/documents/google/create", json=_create_body(library, "Also old"), headers=CSRF)
    other_id = other.json()["id"]
    assert api.post(f"/api/v1/documents/{other_id}/archive", headers=CSRF).status_code == 200
    with acting_as(org.admin, {SCOPE_DOCS_READ, SCOPE_DOCS_WRITE}, method=AuthMethod.bearer):
        assert_error(api.post(f"/api/v1/documents/{other_id}/permanent-delete", headers=CSRF), 403, "SESSION_REQUIRED")
    db_session.expire_all()
    kept = db_session.get(Document, other_id)
    assert kept.deleted_at is None
    assert drive.files[kept.google_file_id].trashed is False


def test_reconcile_retries_failures(db_session, org, drive):
    document = _google_document(db_session, org, visibility=Visibility.department)
    drive.seed_file(document.google_file_id, mime_type=MIME_DOCUMENT)
    sync_document_sharing(db_session, document, drive)
    admin_permission = next(permission for permission in drive.list_permissions(document.google_file_id) if permission.email == org.admin.email)
    drive.delete_permission(document.google_file_id, admin_permission.id)
    document.drive_sync_status = DriveSyncStatus.failed
    document.drive_sync_error = "temporary"
    db_session.flush()
    assert reconcile_drive_sync(db_session, drive) == 1
    assert document.drive_sync_status is DriveSyncStatus.synced
    assert document.drive_sync_error is None
    assert _shares(drive, document.google_file_id)[org.admin.email] == "writer"
    assert reconcile_drive_sync(db_session, drive) == 0


def test_service_account_client_retries_and_always_passes_supports_all_drives():
    file_payload = {
        "id": FILE_ID,
        "name": "Notes",
        "mimeType": MIME_DOCUMENT,
        "modifiedTime": "2026-11-16T09:00:00.000Z",
        "trashed": False,
        "parents": [SHARED_FOLDER],
        "owners": [{"emailAddress": SERVICE_EMAIL}],
    }
    permission_payload = {"id": "perm-1", "type": "user", "role": "reader", "emailAddress": "ada@company.com"}
    log: list[tuple[str, dict]] = []
    service = _RecordingService(
        log,
        files={
            "get": file_payload,
            "create": file_payload,
            "copy": file_payload,
            "update": file_payload,
            "export": b"hello",
        },
        permissions={"list": {"permissions": []}, "create": permission_payload, "update": permission_payload, "delete": ""},
    )
    client = ServiceAccountDriveClient(service, service_account_email=SERVICE_EMAIL, sleeper=lambda _delay: None)
    client.get_file_metadata(FILE_ID)
    client.create_file(title="Notes", mime_type=MIME_DOCUMENT, folder_id=SHARED_FOLDER)
    client.create_file(title="Copy", mime_type=MIME_DOCUMENT, folder_id=SHARED_FOLDER, template_id=FILE_ID)
    client.export_text(FILE_ID)
    client.trash_file(FILE_ID)
    client.list_permissions(FILE_ID)
    client.create_permission(FILE_ID, role="reader", email="ada@company.com")
    client.update_permission(FILE_ID, "perm-1", role="writer")
    client.delete_permission(FILE_ID, "perm-1")
    assert log
    assert all(kwargs.get("supportsAllDrives") is True for _name, kwargs in log)

    delays: list[float] = []
    outcomes = [_http_error(429, "rateLimitExceeded"), _http_error(500, "backendError"), file_payload]
    flaky = _FlakyFiles(outcomes, delays)
    retried = ServiceAccountDriveClient(
        _FlakyService(flaky), service_account_email=SERVICE_EMAIL, sleeper=delays.append, max_attempts=5
    )
    assert retried.get_file_metadata(FILE_ID).id == FILE_ID
    assert delays == [0.5, 1.0]
    assert all(call["supportsAllDrives"] is True for call in flaky.calls)

    denied = _FlakyFiles([_http_error(403, "insufficientFilePermissions")], delays)
    forbidden = ServiceAccountDriveClient(
        _FlakyService(denied), service_account_email=SERVICE_EMAIL, sleeper=delays.append, max_attempts=5
    )
    before = len(delays)
    with pytest.raises(DriveForbidden):
        forbidden.get_file_metadata(FILE_ID)
    assert len(delays) == before

    limited = _FlakyFiles([_http_error(403, "userRateLimitExceeded"), file_payload], [])
    slept: list[float] = []
    limited_client = ServiceAccountDriveClient(
        _FlakyService(limited), service_account_email=SERVICE_EMAIL, sleeper=slept.append, max_attempts=4
    )
    assert limited_client.get_file_metadata(FILE_ID).name == "Notes"
    assert slept == [0.5]


def test_service_account_info_from_base64_or_file(tmp_path, monkeypatch):
    payload = {"type": "service_account", "client_email": "atlas@company.iam.gserviceaccount.com", "private_key": "secret"}
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_B64", encoded)
    assert service_account_info()["client_email"] == payload["client_email"]

    path = tmp_path / "sa.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(path))
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_B64", "not-used")
    assert service_account_info()["client_email"] == payload["client_email"]

    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_B64", "")
    with pytest.raises(Exception) as caught:
        service_account_info()
    assert caught.value.status_code == 500
    assert caught.value.detail["code"] == "MISCONFIGURED"


def _google_document(session, org, *, visibility, default_access=AccessGrant.view, grants=()):
    category = add_category(session, name=f"Guides {uuid4().hex[:8]}")
    folder = add_folder(session, name="Library", owner=org.employee, department=org.product)
    document = add_document(
        session,
        name="Handbook",
        folder=folder,
        owner=org.employee,
        department=org.product,
        category=category,
        visibility=visibility,
        default_access=default_access,
        source_type=SourceType.google_doc,
        status=DocumentStatus.active,
        grants=grants,
    )
    document.google_file_id = uuid4().hex
    document.google_mime_type = MIME_DOCUMENT
    document.google_web_url = google_urls(SourceType.google_doc, document.google_file_id).edit_url
    document.drive_sync_status = DriveSyncStatus.pending
    session.flush()
    return document


def _shares(drive, file_id) -> dict[str, str]:
    shares: dict[str, str] = {}
    for permission in drive.list_permissions(file_id):
        if permission.inherited or permission.role in {"owner", "organizer", "fileOrganizer"}:
            continue
        if permission.email and permission.email.lower() == drive.service_account_email.lower():
            continue
        if permission.type == "domain" and permission.domain:
            shares[f"domain:{permission.domain.lower()}"] = permission.role
        elif permission.email:
            shares[permission.email.lower()] = permission.role
    return shares


def _library(api, org):
    login(api, org.admin.email)
    category = api.post("/api/v1/categories", json={"name": f"Guides {uuid4().hex[:8]}"}, headers=CSRF)
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
    assert folder.status_code == 201, folder.text
    return {
        "category_id": category.json()["id"],
        "folder_id": folder.json()["id"],
        "department_id": str(org.product.id),
    }


def _metadata(library, **overrides):
    body = {
        "category_id": library["category_id"],
        "department_id": library["department_id"],
        "visibility": "department",
        "default_access": "view",
        "tag_ids": [],
    }
    body.update(overrides)
    return body


def _link_body(library, file_id, url=None):
    return {
        "url": url or f"https://docs.google.com/document/d/{file_id}/edit",
        "metadata": {**_metadata(library), "folder_id": library["folder_id"]},
    }


def _create_body(library, title, kind="doc", template=None, **overrides):
    return {
        "title": title,
        "type": kind,
        "template": template,
        "folder_id": library["folder_id"],
        "metadata": _metadata(library, **overrides),
    }


class _Call:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Resource:
    def __init__(self, log, payloads, label):
        self.log = log
        self.payloads = payloads
        self.label = label

    def __getattr__(self, name):
        def method(**kwargs):
            self.log.append((f"{self.label}.{name}", kwargs))
            return _Call(self.payloads[name])

        return method


class _RecordingService:
    def __init__(self, log, *, files, permissions):
        self.files_api = _Resource(log, files, "files")
        self.permissions_api = _Resource(log, permissions, "permissions")

    def files(self):
        return self.files_api

    def permissions(self):
        return self.permissions_api


class _FlakyFiles:
    def __init__(self, outcomes, delays):
        self.outcomes = list(outcomes)
        self.delays = delays
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)

        class _Request:
            def execute(_self):
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome

        return _Request()


class _FlakyService:
    def __init__(self, files):
        self._files = files

    def files(self):
        return self._files


def _http_error(status, reason):
    from googleapiclient.errors import HttpError

    class _Response:
        def __init__(self):
            self.status = status
            self.reason = reason

    body = {"error": {"code": status, "message": reason, "errors": [{"reason": reason, "message": reason}]}}
    return HttpError(_Response(), json.dumps(body).encode())
