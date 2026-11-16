"""Tokens, the agent REST API, and the in-process MCP server."""

import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.core.enums import AccessGrant, ExtractionStatus, PrincipalType, Visibility
from app.core.rate_limit import token_limiter
from app.core.security import hash_token
from app.main import app
from app.models.access import ApiAuditLog, ApiToken
from app.models.base import utcnow
from app.services.agent import UNTRUSTED_NOTICE
from tests.helpers import CSRF, assert_error, login
from tests.library import add_category, add_document, add_folder

PHRASE = "UNTRUSTED-PHRASE-XYZ-DO-NOT-STORE"


def _issue(api, body: dict) -> dict:
    response = api.post("/api/v1/tokens", json=body, headers=CSRF)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["token"].startswith("dms_pat_")
    assert "token_hash" not in payload
    return payload


def _auth(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


def _same_error(left, right) -> None:
    assert left.status_code == right.status_code == 404
    assert left.json()["detail"] == right.json()["detail"]
    assert left.json()["detail"]["code"] == "NOT_FOUND"


@pytest.fixture
def shelf(db_session, org):
    category = add_category(db_session, name="Handbooks")
    home = add_folder(
        db_session,
        name="Product Library",
        owner=org.employee,
        department=org.product,
        visibility=Visibility.department,
    )
    folder = add_folder(
        db_session,
        name="Private Cabinet",
        owner=org.employee,
        department=org.product,
        visibility=Visibility.private,
    )
    shared = add_document(
        db_session,
        name="Shared Handbook",
        folder=home,
        owner=org.employee,
        department=org.product,
        category=category,
        visibility=Visibility.department,
        grants=((PrincipalType.user, org.guest.id, AccessGrant.view),),
    )
    hidden = add_document(
        db_session,
        name="Hidden Payroll",
        folder=folder,
        owner=org.employee,
        department=org.product,
        category=category,
        visibility=Visibility.private,
    )
    body = (PHRASE + " ") * 30
    for document in (shared, hidden):
        document.content_text = body
        document.extraction_status = ExtractionStatus.done
        document.storage_key = f"files/{document.id}"
    db_session.commit()
    return SimpleNamespace(folder=folder, shared=shared, hidden=hidden, category=category, text=body)


def _with_mcp(api, secret: str, fn):
    async def run():
        headers = _auth(secret)
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as http:
            async with Client(streamable_http_client("http://testserver/mcp", http_client=http)) as client:
                return await fn(client)

    return api.portal.call(run)


def _tool_text(result) -> str:
    parts = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def test_token_is_shown_once_and_only_its_hash_is_stored(api, db_session, org):
    login(api, org.employee.email)
    created = _issue(api, {"name": "laptop", "expires_in_days": 14})
    secret = created["token"]
    row = db_session.get(ApiToken, UUID(created["id"]))
    assert row.token_hash == hash_token(secret) == hashlib.sha256(secret.encode()).hexdigest()
    assert secret not in row.token_hash
    assert row.token_prefix == secret.split("_", 3)[0] + "_" + secret.split("_", 3)[1] + "_" + secret.split("_", 3)[2]
    assert row.token_prefix.startswith("dms_pat_")
    assert secret.startswith(row.token_prefix + "_")

    listed = api.get("/api/v1/tokens")
    assert listed.status_code == 200
    assert secret not in listed.text
    assert all("token" not in item or item.get("token") in (None, "") for item in listed.json()["items"])
    assert listed.json()["items"][0]["token_prefix"] == row.token_prefix

    me = api.get("/api/v1/agent/me", headers=_auth(secret))
    assert me.status_code == 200, me.text
    assert me.json()["email"] == org.employee.email
    assert me.json()["scopes"] == ["docs:read"]
    assert me.json()["auth_method"] == "bearer"

    wrong = secret[:-1] + ("A" if secret[-1] != "A" else "B")
    assert_error(api.get("/api/v1/agent/me", headers=_auth(wrong)), 401, "UNAUTHENTICATED")

    row.expires_at = utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert_error(api.get("/api/v1/agent/me", headers=_auth(secret)), 401, "TOKEN_EXPIRED")

    row.expires_at = utcnow() + timedelta(days=1)
    db_session.commit()
    revoked = api.delete(f"/api/v1/tokens/{row.id}", headers=CSRF)
    assert revoked.status_code == 204, revoked.text
    assert_error(api.get("/api/v1/agent/me", headers=_auth(secret)), 401, "TOKEN_REVOKED")


def test_read_token_cannot_write_and_write_token_can(api, db_session, org, shelf):
    login(api, org.admin.email)
    assert_error(
        api.post("/api/v1/tokens", json={"name": "nope", "scopes": ["docs:write"], "user_id": str(org.employee.id)}, headers=CSRF),
        422,
        "NOT_A_BOT",
    )
    denied = api.post(
        "/api/v1/tokens",
        json={"name": "writer", "scopes": ["docs:write"], "expires_in_days": 30},
        headers=CSRF,
    )
    assert denied.status_code == 403

    login(api, org.employee.email)
    assert_error(
        api.post("/api/v1/tokens", json={"name": "writer", "scopes": ["docs:write"]}, headers=CSRF),
        403,
        "WRITE_SCOPES_DISABLED",
    )
    reader = _issue(api, {"name": "reader"})
    blocked = api.post(f"/api/v1/agent/documents/{shelf.shared.id}/archive", headers=_auth(reader["token"]))
    assert_error(blocked, 403, "MISSING_SCOPE")

    login(api, org.admin.email)
    opened = api.patch("/api/v1/admin/org-settings", json={"allow_write_scopes": True}, headers=CSRF)
    assert opened.status_code == 200, opened.text
    assert opened.json()["allow_write_scopes"] is True

    login(api, org.employee.email)
    writer = _issue(api, {"name": "writer", "scopes": ["docs:read", "docs:write"]})
    assert writer["scopes"] == ["docs:read", "docs:write"]
    archived = api.post(f"/api/v1/agent/documents/{shelf.hidden.id}/archive", headers=_auth(writer["token"]))
    assert archived.status_code == 200, archived.text
    assert archived.json()["id"] == str(shelf.hidden.id)


def test_token_cannot_leave_the_agent_allowlist(api, org, shelf):
    login(api, org.employee.email)
    secret = _issue(api, {"name": "narrow"})["token"]
    for method, path in (
        ("GET", "/api/v1/users"),
        ("GET", "/api/v1/tokens"),
        ("GET", "/api/v1/admin/org-settings"),
        ("GET", "/api/v1/documents"),
    ):
        response = api.request(method, path, headers=_auth(secret))
        assert_error(response, 403, "EXTERNAL_ROUTE_FORBIDDEN")
    deleted = api.post(f"/api/v1/documents/{shelf.shared.id}/permanent-delete", headers=_auth(secret))
    assert_error(deleted, 403, "EXTERNAL_ROUTE_FORBIDDEN")

    login(api, org.admin.email)
    assert api.get("/api/v1/admin/org-settings").status_code == 200


def test_hidden_and_missing_documents_look_the_same(api, org, shelf):
    login(api, org.guest.email)
    secret = _issue(api, {"name": "guest"})["token"]
    headers = _auth(secret)
    missing = uuid4()

    visible = api.get(f"/api/v1/agent/documents/{shelf.shared.id}", headers=headers)
    assert visible.status_code == 200, visible.text
    card = visible.json()
    assert card["name"] == "Shared Handbook"
    assert card["my_access"] == "view"
    assert card["content_available"] is True
    assert set(card) >= {
        "id",
        "name",
        "description",
        "path",
        "source_type",
        "mime_type",
        "tags",
        "category",
        "department",
        "owner_name",
        "version",
        "last_modified_at",
        "my_access",
        "web_url",
        "google_url",
        "content_available",
    }

    _same_error(
        api.get(f"/api/v1/agent/documents/{shelf.hidden.id}", headers=headers),
        api.get(f"/api/v1/agent/documents/{missing}", headers=headers),
    )
    _same_error(
        api.get(f"/api/v1/agent/documents/{shelf.hidden.id}/content", headers=headers),
        api.get(f"/api/v1/agent/documents/{missing}/content", headers=headers),
    )
    _same_error(
        api.get(f"/api/v1/agent/documents/{shelf.hidden.id}/related", headers=headers),
        api.get(f"/api/v1/agent/documents/{missing}/related", headers=headers),
    )
    _same_error(
        api.get(f"/api/v1/agent/documents/{shelf.hidden.id}/download-link", headers=headers),
        api.get(f"/api/v1/agent/documents/{missing}/download-link", headers=headers),
    )
    _same_error(
        api.get("/api/v1/agent/folders", params={"parent_id": str(shelf.folder.id)}, headers=headers),
        api.get("/api/v1/agent/folders", params={"parent_id": str(uuid4())}, headers=headers),
    )

    found = api.get("/api/v1/agent/search", params={"q": "Payroll"}, headers=headers)
    assert found.status_code == 200, found.text
    assert all(item["id"] != str(shelf.hidden.id) for item in found.json()["items"])
    listed = api.get("/api/v1/agent/search", params={"q": "Handbook"}, headers=headers)
    assert any(item["id"] == str(shelf.shared.id) for item in listed.json()["items"])


def test_content_pages_are_untrusted_and_audit_omits_the_text(api, db_session, org, shelf):
    login(api, org.guest.email)
    created = _issue(api, {"name": "reader"})
    headers = _auth(created["token"])
    page = api.get(
        f"/api/v1/agent/documents/{shelf.shared.id}/content",
        params={"offset": 0, "limit": 24},
        headers=headers,
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["notice"] == UNTRUSTED_NOTICE
    assert body["truncated"] is True
    assert body["next_offset"] == 24
    assert body["total_chars"] == len(shelf.text)
    assert body["document_content"] == shelf.text[:24]
    assert PHRASE not in json.dumps(body["notice"])

    searched = api.get("/api/v1/agent/search", params={"q": PHRASE}, headers=headers)
    assert searched.status_code == 200

    login(api, org.guest.email)
    own = api.get("/api/v1/me/audit-log")
    assert own.status_code == 200, own.text
    rows = db_session.query(ApiAuditLog).all()
    assert rows
    blob = json.dumps([row.request_summary for row in rows])
    assert PHRASE not in blob
    assert "dms_pat_" not in blob
    assert any(row.token_id == UUID(created["id"]) and row.channel.value == "rest" for row in rows)
    assert all(row.user_id == org.guest.id for row in rows if row.token_id == UUID(created["id"]))


def test_bot_token_rate_limit_kill_switch_and_deactivation(api, db_session, org, monkeypatch):
    login(api, org.admin.email)
    bot = _issue(api, {"name": "indexer", "user_id": str(org.bot.id), "expires_in_days": 10})
    identity = api.get("/api/v1/agent/me", headers=_auth(bot["token"]))
    assert identity.status_code == 200, identity.text
    assert identity.json()["is_bot"] is True
    assert identity.json()["email"] == org.bot.email
    assert identity.json()["id"] == str(org.bot.id)

    monkeypatch.setenv("TOKEN_READ_RATE_LIMIT", "2")
    token_limiter.reset()
    assert api.get("/api/v1/agent/me", headers=_auth(bot["token"])).status_code == 200
    assert api.get("/api/v1/agent/me", headers=_auth(bot["token"])).status_code == 200
    limited = api.get("/api/v1/agent/me", headers=_auth(bot["token"]))
    assert_error(limited, 429, "RATE_LIMITED")
    assert int(limited.headers["retry-after"]) >= 1

    login(api, org.admin.email)
    closed = api.patch("/api/v1/admin/org-settings", json={"external_ai_enabled": False}, headers=CSRF)
    assert closed.status_code == 200, closed.text
    assert_error(api.get("/api/v1/agent/me", headers=_auth(bot["token"])), 403, "EXTERNAL_ACCESS_DISABLED")
    reopened = api.patch("/api/v1/admin/org-settings", json={"external_ai_enabled": True}, headers=CSRF)
    assert reopened.status_code == 200

    login(api, org.employee.email)
    secret = _issue(api, {"name": "mine"})["token"]
    login(api, org.admin.email)
    deactivated = api.post(f"/api/v1/users/{org.employee.id}/deactivate", headers=CSRF)
    assert deactivated.status_code == 200, deactivated.text
    assert_error(api.get("/api/v1/agent/me", headers=_auth(secret)), 401, "TOKEN_REVOKED")
    row = db_session.query(ApiToken).filter(ApiToken.user_id == org.employee.id).one()
    assert row.revoked_at is not None


def test_filtered_openapi_document(api):
    response = api.get("/api/v1/agent/openapi.json")
    assert response.status_code == 200, response.text
    schema = response.json()
    assert schema["openapi"] == "3.1.0"
    assert schema["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    paths = schema["paths"]
    assert paths
    assert all(path.startswith("/api/v1/agent/") for path in paths)
    assert not any("/downloads/" in path or path.endswith("/openapi.json") for path in paths)
    for item in paths.values():
        for operation in item.values():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            assert operation["operationId"].replace("_", "").isalnum()
            assert operation["operationId"] == operation["operationId"].lower()
            assert operation["security"] == [{"bearerAuth": []}]
            assert len(operation.get("description") or "") <= 300


def test_mcp_scopes_leaks_content_and_audit(api, db_session, org, shelf):
    login(api, org.guest.email)
    guest = _issue(api, {"name": "guest-mcp"})["token"]

    async def guest_calls(client):
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        hidden = await client.call_tool("get_document", {"document_id": str(shelf.hidden.id)})
        missing = await client.call_tool("get_document", {"document_id": str(uuid4())})
        read_hidden = await client.call_tool("read_document", {"document_id": str(shelf.hidden.id)})
        found = await client.call_tool("search_documents", {"q": "Payroll"})
        page = await client.call_tool(
            "read_document",
            {"document_id": str(shelf.shared.id), "offset": 0, "max_chars": 24},
        )
        prompt = await client.get_prompt("answer_from_company_knowledge", {"question": "Where is the handbook?"})
        return names, hidden, missing, read_hidden, found, page, prompt

    names, hidden, missing, read_hidden, found, page, prompt = _with_mcp(api, guest, guest_calls)
    assert "archive_document" not in names
    assert "create_folder" not in names
    assert "ask_knowledge_base" not in names
    assert "search_documents" in names
    assert "read_document" in names
    for result in (hidden, missing, read_hidden):
        assert result.is_error
        assert "not found or not accessible" in _tool_text(result)
    assert str(shelf.hidden.id) not in _tool_text(found)
    assert page.is_error is False
    structured = page.structured_content or json.loads(_tool_text(page))
    assert structured["notice"] == UNTRUSTED_NOTICE
    assert structured["truncated"] is True
    assert structured["document_content"] == shelf.text[:24]
    prompt_text = json.dumps(prompt.model_dump(mode="json"))
    assert "web_url" in prompt_text
    assert "search_documents" in prompt_text

    login(api, org.admin.email)
    assert api.patch("/api/v1/admin/org-settings", json={"allow_write_scopes": True}, headers=CSRF).status_code == 200
    login(api, org.employee.email)
    writer = _issue(api, {"name": "writer-mcp", "scopes": ["docs:write"]})["token"]

    async def writer_calls(client):
        listed = await client.list_tools()
        return {tool.name for tool in listed.tools}

    writer_names = _with_mcp(api, writer, writer_calls)
    assert "archive_document" in writer_names
    assert "create_google_doc" in writer_names

    rows = db_session.query(ApiAuditLog).filter(ApiAuditLog.channel == "mcp").all()
    assert rows
    blob = json.dumps([row.request_summary for row in rows])
    assert PHRASE not in blob
    assert any(row.operation == "read_document" for row in rows)


def test_mcp_requires_a_bearer_token(api):
    response = api.post(
        "/mcp",
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code == 401, response.text
    challenge = response.headers["www-authenticate"]
    assert 'resource_metadata="' in challenge
    assert "/.well-known/oauth-protected-resource" in challenge
    metadata = api.get("/.well-known/oauth-protected-resource/mcp")
    assert metadata.status_code == 200, metadata.text
