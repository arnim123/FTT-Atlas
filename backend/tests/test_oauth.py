"""OAuth 2.1 authorization server: discovery, PKCE, rotation, and consent."""

import base64
import hashlib
import json
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import select

from app.core.security import hash_token
from app.main import app
from app.models.access import ApiAuditLog
from app.models.base import utcnow
from app.models.oauth import OAuthAuthorizationCode, OAuthClient, OAuthToken
from app.services.oauth import cleanup_expired, fetch_metadata_document
from tests.helpers import CSRF, assert_error, login

RESOURCE = "http://127.0.0.1:8000/mcp"
REDIRECT = "https://client.example/callback"


def _pkce(verifier: str | None = None) -> tuple[str, str]:
    raw = verifier or secrets.token_urlsafe(48)
    verifier = "".join(char for char in raw if char.isalnum() or char in "-._~")[:64]
    if len(verifier) < 43:
        verifier = (verifier + ("a" * 43))[:64]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _register(api, redirect: str = REDIRECT, **extra) -> dict:
    body = {
        "client_name": extra.pop("client_name", "In-test client"),
        "redirect_uris": [redirect],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    body.update(extra)
    response = api.post("/oauth/register", json=body)
    assert response.status_code == 201, response.text
    assert "client_secret" not in response.json()
    return response.json()


def _authorize(api, client_id: str, redirect: str, challenge: str, **extra):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": RESOURCE,
        "scope": "docs:read",
        "state": "state-1",
    }
    params.update(extra)
    return api.get("/oauth/authorize", params=params, follow_redirects=False)


def _request_id(response) -> str:
    assert response.status_code == 302, response.text
    location = response.headers["location"]
    assert "/oauth/consent?request=" in location
    return parse_qs(urlsplit(location).query)["request"][0]


def _allow(api, request_id: str, scopes: list[str]):
    return api.post(
        "/api/v1/oauth/consent",
        json={"request_id": request_id, "decision": "allow", "scopes": scopes},
        headers=CSRF,
    )


def _code_from(redirect_to: str) -> str:
    query = parse_qs(urlsplit(redirect_to).query)
    assert query["iss"] == ["http://127.0.0.1:8000"]
    assert query["state"] == ["state-1"]
    return query["code"][0]


def _token(api, client_id: str, redirect: str, code: str, verifier: str, **extra) -> dict:
    form = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect,
        "code": code,
        "code_verifier": verifier,
        "resource": RESOURCE,
    }
    form.update(extra)
    response = api.post("/oauth/token", data=form)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def _connect(api, *, scopes: str = "docs:read", allow: list[str] | None = None, redirect: str = REDIRECT):
    registered = _register(api, redirect)
    verifier, challenge = _pkce()
    login(api, "emma.davis@company.com")
    started = _authorize(api, registered["client_id"], redirect, challenge, scope=scopes)
    request_id = _request_id(started)
    allowed = _allow(api, request_id, allow or ["docs:read"])
    assert allowed.status_code == 200, allowed.text
    code = _code_from(allowed.json()["redirect_to"])
    tokens = _token(api, registered["client_id"], redirect, code, verifier)
    return registered, tokens, verifier


def _with_mcp(api, secret: str, fn):
    async def run():
        transport = httpx2.ASGITransport(app=app)
        headers = {"Authorization": f"Bearer {secret}"}
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


def test_metadata_documents_and_mcp_challenge(api):
    challenge = api.post(
        "/mcp",
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert challenge.status_code == 401, challenge.text
    header = challenge.headers["www-authenticate"]
    assert header.startswith("Bearer ")
    assert 'error="invalid_token"' in header
    assert 'resource_metadata="' in header
    metadata_url = header.split('resource_metadata="', 1)[1].split('"', 1)[0]
    assert metadata_url == "http://127.0.0.1:8000/.well-known/oauth-protected-resource/mcp"

    document = api.get("/.well-known/oauth-protected-resource/mcp")
    root = api.get("/.well-known/oauth-protected-resource")
    server = api.get("/.well-known/oauth-authorization-server")
    assert document.status_code == root.status_code == server.status_code == 200
    resource = document.json()
    assert root.json() == resource
    assert resource["resource"] == RESOURCE
    assert resource["authorization_servers"] == ["http://127.0.0.1:8000"]
    assert resource["scopes_supported"] == ["docs:read", "docs:write"]
    assert resource["bearer_methods_supported"] == ["header"]
    metadata = server.json()
    assert metadata["issuer"] == "http://127.0.0.1:8000"
    assert metadata["issuer"] == resource["authorization_servers"][0]
    assert metadata["authorization_endpoint"] == "http://127.0.0.1:8000/oauth/authorize"
    assert metadata["token_endpoint"] == "http://127.0.0.1:8000/oauth/token"
    assert metadata["registration_endpoint"] == "http://127.0.0.1:8000/oauth/register"
    assert metadata["revocation_endpoint"] == "http://127.0.0.1:8000/oauth/revoke"
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert metadata["grant_types_supported"] == ["authorization_code", "refresh_token"]
    assert "password" not in metadata["grant_types_supported"]
    assert metadata["response_types_supported"] == ["code"]
    assert "none" in metadata["token_endpoint_auth_methods_supported"]
    assert metadata["client_id_metadata_document_supported"] is True
    assert metadata["authorization_response_iss_parameter_supported"] is True
    assert "offline_access" not in json.dumps(metadata)


def test_authorization_code_pkce_flow_records_the_client(api, db_session, org):
    registered, tokens, _verifier = _connect(api)
    assert tokens["token_type"] == "Bearer"
    assert tokens["expires_in"] == 3600
    assert tokens["scope"] == "docs:read"
    access = tokens["access_token"]
    assert access.startswith("dms_oat_")
    stored = db_session.scalar(select(OAuthToken).where(OAuthToken.token_hash == hash_token(access)))
    assert stored is not None
    assert stored.token_hash != access
    assert stored.audience == RESOURCE
    client = db_session.scalar(select(OAuthClient).where(OAuthClient.client_id == registered["client_id"]))
    assert client is not None
    assert client.registration_kind == "dynamic"

    async def whoami(client):
        return await client.call_tool("whoami", {})

    result = _with_mcp(api, access, whoami)
    body = result.structured_content or json.loads(_tool_text(result))
    assert body["auth_method"] == "oauth"
    assert body["client_name"] == "In-test client"
    assert body["email"] == org.employee.email
    assert body["scopes"] == ["docs:read"]
    assert body.get("token_id") is None

    rows = db_session.query(ApiAuditLog).all()
    assert any(row.oauth_client_id == client.id and row.token_id is None for row in rows)
    assert_error(api.get("/api/v1/agent/me", headers={"Authorization": f"Bearer {access}"}), 401, "INVALID_AUDIENCE")
    login(api, org.admin.email)
    listed = api.get("/api/v1/oauth/grants")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    login(api, org.employee.email)
    grants = api.get("/api/v1/oauth/grants")
    assert grants.status_code == 200, grants.text
    assert grants.json()["items"][0]["client_name"] == "In-test client"
    assert grants.json()["items"][0]["verified"] is False
    assert grants.json()["items"][0]["redirect_domain"] == "client.example"


def test_missing_session_returns_to_google_login(api):
    registered = _register(api)
    _verifier, challenge = _pkce()
    started = _authorize(api, registered["client_id"], REDIRECT, challenge)
    assert started.status_code == 302, started.text
    location = started.headers["location"]
    assert location.startswith("http://localhost:5173/login?next=")
    assert "oauth%2Fauthorize" in location or "oauth/authorize" in location


def test_wrong_verifier_and_plain_pkce_are_rejected(api, org):
    del org
    registered = _register(api)
    verifier, challenge = _pkce()
    login(api, "emma.davis@company.com")
    request_id = _request_id(_authorize(api, registered["client_id"], REDIRECT, challenge))
    allowed = _allow(api, request_id, ["docs:read"])
    code = _code_from(allowed.json()["redirect_to"])
    wrong = api.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": registered["client_id"],
            "redirect_uri": REDIRECT,
            "code": code,
            "code_verifier": verifier[:-1] + ("a" if verifier[-1] != "a" else "b"),
            "resource": RESOURCE,
        },
    )
    assert wrong.status_code == 400, wrong.text
    assert wrong.json()["error"] == "invalid_grant"

    plain = _authorize(
        api,
        registered["client_id"],
        REDIRECT,
        challenge,
        code_challenge_method="plain",
        state="state-1",
    )
    assert plain.status_code == 302
    query = parse_qs(urlsplit(plain.headers["location"]).query)
    assert query["error"] == ["invalid_request"]
    assert query["iss"] == ["http://127.0.0.1:8000"]
    assert "code" not in query


def test_code_reuse_revokes_the_grant(api, db_session, org):
    registered = _register(api)
    verifier, challenge = _pkce()
    login(api, "emma.davis@company.com")
    request_id = _request_id(_authorize(api, registered["client_id"], REDIRECT, challenge))
    code = _code_from(_allow(api, request_id, ["docs:read"]).json()["redirect_to"])
    first = _token(api, registered["client_id"], REDIRECT, code, verifier)
    second = api.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": registered["client_id"],
            "redirect_uri": REDIRECT,
            "code": code,
            "code_verifier": verifier,
            "resource": RESOURCE,
        },
    )
    assert second.status_code == 400
    assert second.json()["error"] == "invalid_grant"
    denied = api.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {first['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert denied.status_code == 401, denied.text
    grant_revoked = db_session.scalar(select(OAuthToken).where(OAuthToken.token_hash == hash_token(first["access_token"])))
    assert grant_revoked is not None
    assert grant_revoked.revoked_at is not None


def test_redirect_must_match_and_loopback_ports_are_allowed(api, org):
    registered = _register(api)
    _verifier, challenge = _pkce()
    login(api, "emma.davis@company.com")
    mismatch = _authorize(api, registered["client_id"], "https://evil.example/callback", challenge)
    assert mismatch.status_code == 400, mismatch.text
    assert mismatch.json()["error"] == "invalid_request"
    assert "location" not in mismatch.headers

    loopback = "http://127.0.0.1/callback"
    local = _register(api, loopback, client_name="Local tool")
    started = _authorize(api, local["client_id"], "http://127.0.0.1:4545/callback", challenge, state="state-1")
    assert started.status_code == 302, started.text
    assert "/oauth/consent?request=" in started.headers["location"]
    wrong_path = _authorize(api, local["client_id"], "http://127.0.0.1:4545/other", challenge)
    assert wrong_path.status_code == 400


def test_refresh_rotation_detects_reuse(api, org):
    registered, tokens, _verifier = _connect(api)
    first_access = tokens["access_token"]
    first_refresh = tokens["refresh_token"]
    rotated = api.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": registered["client_id"],
            "refresh_token": first_refresh,
            "resource": RESOURCE,
        },
    )
    assert rotated.status_code == 200, rotated.text
    second = rotated.json()
    assert second["access_token"] != first_access
    assert second["refresh_token"] != first_refresh

    async def whoami(client):
        return await client.call_tool("whoami", {})

    identity = _with_mcp(api, second["access_token"], whoami)
    body = identity.structured_content or json.loads(_tool_text(identity))
    assert body["auth_method"] == "oauth"

    reused = api.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": registered["client_id"],
            "refresh_token": first_refresh,
            "resource": RESOURCE,
        },
    )
    assert reused.status_code == 400
    assert reused.json()["error"] == "invalid_grant"
    blocked = api.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {second['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert blocked.status_code == 401, blocked.text
    again = api.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": registered["client_id"],
            "refresh_token": second["refresh_token"],
            "resource": RESOURCE,
        },
    )
    assert again.status_code == 400
    assert again.json()["error"] == "invalid_grant"


def test_scope_downgrade_and_rejected_upgrade(api, org):
    login(api, org.admin.email)
    assert api.patch("/api/v1/admin/org-settings", json={"allow_write_scopes": True}, headers=CSRF).status_code == 200
    registered = _register(api)
    verifier, challenge = _pkce()
    login(api, org.employee.email)
    request_id = _request_id(_authorize(api, registered["client_id"], REDIRECT, challenge, scope="docs:read docs:write"))
    view = api.get("/api/v1/oauth/consent-request", params={"request_id": request_id})
    assert view.status_code == 200, view.text
    assert view.json()["verified"] is False
    assert view.json()["write_requested"] is True
    assert view.json()["allow_write"] is True
    assert view.json()["scopes"] == ["docs:read", "docs:write"]
    allowed = _allow(api, request_id, ["docs:read"])
    assert allowed.status_code == 200, allowed.text
    tokens = _token(api, registered["client_id"], REDIRECT, _code_from(allowed.json()["redirect_to"]), verifier)
    assert tokens["scope"] == "docs:read"

    read_only = _register(api, "https://client.example/read", client_name="Reader")
    _verifier, read_challenge = _pkce()
    read_request = _request_id(_authorize(api, read_only["client_id"], "https://client.example/read", read_challenge))
    upgrade = _allow(api, read_request, ["docs:read", "docs:write"])
    assert_error(upgrade, 422, "SCOPE_UPGRADE")


def test_org_setting_strips_write_scope(api, org):
    del org
    registered = _register(api)
    verifier, challenge = _pkce()
    login(api, "emma.davis@company.com")
    request_id = _request_id(_authorize(api, registered["client_id"], REDIRECT, challenge, scope="docs:read docs:write"))
    view = api.get("/api/v1/oauth/consent-request", params={"request_id": request_id}).json()
    assert view["write_requested"] is True
    assert view["allow_write"] is False
    assert view["scopes"] == ["docs:read"]
    tokens = _token(api, registered["client_id"], REDIRECT, _code_from(_allow(api, request_id, ["docs:read", "docs:write"]).json()["redirect_to"]), verifier)
    assert tokens["scope"] == "docs:read"


def test_revoked_grant_and_deactivated_user_invalidate_tokens(api, org):
    _registered, tokens, _verifier = _connect(api)
    access = tokens["access_token"]
    login(api, org.employee.email)
    grant_id = api.get("/api/v1/oauth/grants").json()["items"][0]["id"]
    assert api.delete(f"/api/v1/oauth/grants/{grant_id}", headers=CSRF).status_code == 204
    denied = api.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {access}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert denied.status_code == 401

    _registered, fresh, _verifier = _connect(api)
    login(api, org.admin.email)
    assert api.post(f"/api/v1/users/{org.employee.id}/deactivate", headers=CSRF).status_code == 200
    inactive = api.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {fresh['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert inactive.status_code == 401, inactive.text
    assert api.post(f"/api/v1/users/{org.employee.id}/reactivate", headers=CSRF).status_code == 200
    still_revoked = api.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {fresh['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert still_revoked.status_code == 401, still_revoked.text


def test_audience_mismatch_and_kill_switch(api, db_session, org):
    registered, tokens, verifier = _connect(api)
    wrong = api.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": registered["client_id"],
            "refresh_token": tokens["refresh_token"],
            "resource": "https://evil.example/mcp",
        },
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"] == "invalid_target"

    stored = db_session.scalar(select(OAuthToken).where(OAuthToken.token_hash == hash_token(tokens["access_token"])))
    stored.audience = "https://evil.example/mcp"
    db_session.commit()
    mismatched = api.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert mismatched.status_code == 401

    stored.audience = RESOURCE
    db_session.commit()
    login(api, org.admin.email)
    assert api.patch("/api/v1/admin/org-settings", json={"external_ai_enabled": False}, headers=CSRF).status_code == 200
    blocked = api.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert_error(blocked, 403, "EXTERNAL_ACCESS_DISABLED")
    refresh = api.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": registered["client_id"],
            "refresh_token": tokens["refresh_token"],
            "resource": RESOURCE,
        },
    )
    assert refresh.status_code == 400
    assert refresh.json()["error"] == "access_denied"

    login(api, org.employee.email)
    pending = _register(api, "https://client.example/other", client_name="Later")
    _verifier, challenge = _pkce()
    request_id = _request_id(_authorize(api, pending["client_id"], "https://client.example/other", challenge))
    assert_error(_allow(api, request_id, ["docs:read"]), 403, "EXTERNAL_ACCESS_DISABLED")
    del verifier


def test_dynamic_clients_are_unverified_and_metadata_clients_can_be(api, org, monkeypatch):
    document = {
        "client_id": "https://chatgpt.com/oauth/client.json",
        "client_name": "ChatGPT",
        "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect", "http://127.0.0.1/callback"],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }

    def fake(url: str):
        assert url == document["client_id"]
        return document, 300

    monkeypatch.setattr("app.services.oauth.fetch_metadata_document", fake)
    _verifier, challenge = _pkce()
    login(api, "emma.davis@company.com")
    started = _authorize(
        api,
        document["client_id"],
        "https://chatgpt.com/connector_platform_oauth_redirect",
        challenge,
    )
    request_id = _request_id(started)
    view = api.get("/api/v1/oauth/consent-request", params={"request_id": request_id})
    assert view.status_code == 200, view.text
    assert view.json()["verified"] is True
    assert view.json()["app_name"] == "ChatGPT"
    assert view.json()["redirect_domain"] == "chatgpt.com"

    local = _authorize(api, document["client_id"], "http://127.0.0.1:3210/callback", challenge, state="state-1")
    local_view = api.get("/api/v1/oauth/consent-request", params={"request_id": _request_id(local)})
    assert local_view.json()["verified"] is False
    assert local_view.json()["localhost_redirect"] is True


def test_registration_is_limited_and_rejects_other_grants(api, monkeypatch):
    monkeypatch.setenv("OAUTH_CLIENTS_PER_IP", "1")
    first = _register(api)
    assert first["client_id"].startswith("dms_ocl_")
    second = api.post(
        "/oauth/register",
        json={
            "client_name": "Second",
            "redirect_uris": ["https://client.example/second"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert second.status_code == 400, second.text
    assert second.json()["error"] == "invalid_client_metadata"
    password = api.post(
        "/oauth/token",
        data={"grant_type": "password", "username": "a", "password": "b", "client_id": first["client_id"]},
    )
    assert password.status_code == 400
    assert password.json()["error"] == "unsupported_grant_type"
    implicit = api.post(
        "/oauth/register",
        json={
            "client_name": "Implicit",
            "redirect_uris": ["https://client.example/implicit"],
            "response_types": ["token"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert implicit.json()["error"] == "invalid_client_metadata"


def test_revocation_and_cleanup(api, db_session, org):
    registered, tokens, _verifier = _connect(api)
    gone = api.post(
        "/oauth/revoke",
        data={"token": tokens["refresh_token"], "client_id": registered["client_id"], "token_type_hint": "refresh_token"},
    )
    assert gone.status_code == 200, gone.text
    unknown = api.post("/oauth/revoke", data={"token": "dms_ort_missing", "client_id": registered["client_id"]})
    assert unknown.status_code == 200
    blocked = api.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert blocked.status_code == 401

    code = db_session.scalar(select(OAuthAuthorizationCode))
    access = db_session.scalar(select(OAuthToken).where(OAuthToken.kind == "access"))
    code_id, access_id = code.id, access.id
    past = utcnow() - timedelta(seconds=5)
    code.expires_at = past
    access.expires_at = past
    db_session.commit()
    cleanup_expired(db_session)
    db_session.expire_all()
    assert db_session.get(OAuthAuthorizationCode, code_id) is None
    assert db_session.get(OAuthToken, access_id) is None


def test_metadata_url_must_be_public_https():
    for url in ("http://127.0.0.1/client.json", "https://127.0.0.1/client.json", "https://example.com"):
        try:
            fetch_metadata_document(url)
        except Exception as exc:
            assert getattr(exc, "error", None) == "invalid_client"
        else:
            raise AssertionError(url)


def test_oauth_is_between_the_api_token_and_the_session(api, org):
    from app.core.principal import AUTHENTICATORS, BearerTokenAuthenticator, OAuthAuthenticator, SessionCookieAuthenticator

    assert len(AUTHENTICATORS) == 3
    assert isinstance(AUTHENTICATORS[0], BearerTokenAuthenticator)
    assert isinstance(AUTHENTICATORS[1], OAuthAuthenticator)
    assert isinstance(AUTHENTICATORS[2], SessionCookieAuthenticator)
    login(api, org.admin.email)
    assert_error(api.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}), 401, "UNAUTHENTICATED")
    assert api.get("/api/v1/auth/me").json()["email"] == org.admin.email
