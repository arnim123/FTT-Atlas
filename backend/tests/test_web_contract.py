"""Routes the web app adds on top of the agent API."""

from uuid import uuid4

from app.integrations.drive import DEMO_SHARED_FILE_ID
from tests.helpers import CSRF, assert_error, login
from tests.test_documents_api import _document_body, _library


def test_public_config_has_no_secrets(api):
    response = api.get("/api/v1/config")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["public_base_url"].startswith("http")
    assert "demo_google_url" in body
    assert DEMO_SHARED_FILE_ID in (body["demo_google_url"] or "")
    assert "private_key" not in response.text
    assert "jwt" not in response.text.lower()


def test_api_cors_is_locked_to_the_frontend_origin(api, monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("APP_ENV", "development")
    allowed = api.get("/api/v1/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    blocked = api.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


def test_document_events_and_directory(api, org):
    library = _library(api, org)
    login(api, org.employee.email)
    created = api.post("/api/v1/documents", json=_document_body(library, "Inventory notes"), headers=CSRF)
    assert created.status_code == 201, created.text
    document_id = created.json()["id"]
    assert created.json()["drive_sync_status"] == "not_applicable"
    events = api.get(f"/api/v1/documents/{document_id}/events")
    assert events.status_code == 200, events.text
    assert events.json()["items"][0]["channel"] == "web"
    login(api, org.guest.email)
    denied = api.get(f"/api/v1/documents/{document_id}/events")
    assert_error(denied, 404, "NOT_FOUND")
    directory = api.get("/api/v1/users/directory")
    assert directory.status_code == 200, directory.text
    assert len(directory.json()) == 1
    assert directory.json()[0]["id"] == str(org.guest.id)


def test_token_responses_are_not_cached(api, org):
    login(api, org.admin.email)
    created = api.post(
        "/api/v1/tokens",
        json={"name": f"web-{uuid4().hex[:8]}", "scopes": ["docs:read"], "expires_in_days": 30},
        headers=CSRF,
    )
    assert created.status_code == 201, created.text
    assert created.headers["cache-control"] == "no-store"
    assert created.json()["token"].startswith("dms_pat_")


def test_member_can_read_org_settings(api, org):
    login(api, org.employee.email)
    response = api.get("/api/v1/org-settings")
    assert response.status_code == 200, response.text
    assert "external_ai_enabled" in response.json()
    blocked = api.patch("/api/v1/admin/org-settings", json={"external_ai_enabled": False}, headers=CSRF)
    assert_error(blocked, 403, "FORBIDDEN")
