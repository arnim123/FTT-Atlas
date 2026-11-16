import re

import jwt
import pytest

from app.core.errors import ApiError
from app.core.rate_limit import google_login_limiter
from app.integrations.google_auth import verify_google_id_token
from app.models import Department
from tests.helpers import CSRF, assert_error, google_login, google_tokens, identity, login


def test_bootstrap_super_admin_from_google(api, db_session, monkeypatch):
    monkeypatch.setenv("SUPER_ADMIN_EMAILS", "founder@gmail.com")
    monkeypatch.setenv("AUTO_PROVISION", "false")
    db_session.add(Department(code="product", name="Product", description=None))
    db_session.flush()

    response = google_login(api, identity("founder@gmail.com", name="Founder", sub="sub-founder"))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "super_admin"
    assert body["email"] == "founder@gmail.com"
    assert body["department"]["code"] == "product"
    assert body["status"] == "active"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=28800" in cookie
    me = api.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "super_admin"
    assert me.json()["department"]["name"] == "Product"


def test_unknown_domain_is_rejected(api, db_session):
    db_session.add(Department(code="product", name="Product", description=None))
    db_session.flush()
    response = google_login(api, identity("person@gmail.com"))
    assert_error(response, 403, "DOMAIN_NOT_ALLOWED")
    assert "set-cookie" not in {key.lower() for key in response.headers}


def test_allowed_domain_without_auto_provision_is_rejected(api, db_session):
    db_session.add(Department(code="product", name="Product", description=None))
    db_session.flush()
    response = google_login(api, identity("new.hire@company.com"))
    assert_error(response, 403, "DOMAIN_NOT_ALLOWED")


def test_auto_provision_creates_an_employee(api, db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PROVISION", "true")
    db_session.add(Department(code="product", name="Product", description=None))
    db_session.flush()
    response = google_login(api, identity("new.hire@company.com", name=None))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "employee"
    assert body["name"] == "New Hire"
    assert body["department"]["code"] == "product"
    assert body["is_bot"] is False


def test_auto_provision_requires_the_default_department(api, monkeypatch):
    monkeypatch.setenv("AUTO_PROVISION", "true")
    monkeypatch.setenv("DEFAULT_DEPARTMENT_CODE", "missing")
    response = google_login(api, identity("new.hire@company.com"))
    assert_error(response, 500, "MISCONFIGURED")


def test_invited_user_can_sign_in_without_joining_the_domain_list(api, org):
    response = google_login(api, identity(org.guest.email, name="Someone Else", picture="https://cdn.example/n.png", sub="sub-noah"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "guest"
    assert body["name"] == "Noah Williams"
    assert body["avatar_url"] == "https://cdn.example/n.png"
    assert body["status"] == "active"


def test_first_login_promotes_a_bootstrap_email(api, org, events, monkeypatch):
    monkeypatch.setenv("SUPER_ADMIN_EMAILS", org.employee.email)
    response = google_login(api, identity(org.employee.email, sub="sub-emma"))
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "super_admin"
    assert events == [{"user_id": str(org.employee.id), "changes": {"role": {"from": "employee", "to": "super_admin"}}}]


def test_bootstrap_does_not_promote_someone_who_already_signed_in(api, org, events, monkeypatch):
    monkeypatch.setenv("SUPER_ADMIN_EMAILS", org.sales_employee.email)
    response = google_login(api, identity(org.sales_employee.email, sub="sub-sam"))
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "employee"
    assert events == []


def test_deactivated_user_cannot_sign_in(api, org, monkeypatch):
    monkeypatch.setenv("SUPER_ADMIN_EMAILS", org.deactivated.email)
    response = google_login(api, identity(org.deactivated.email))
    assert_error(response, 403, "ACCOUNT_DEACTIVATED")


def test_bot_cannot_sign_in_with_google(api, org, monkeypatch):
    monkeypatch.setenv("SUPER_ADMIN_EMAILS", org.bot.email)
    monkeypatch.setenv("AUTO_PROVISION", "true")
    response = google_login(api, identity(org.bot.email, sub="sub-bot"))
    assert_error(response, 403, "BOT_LOGIN_FORBIDDEN")


def test_unverified_google_email_is_rejected(api):
    response = google_login(api, identity("person@company.com", email_verified=False))
    assert_error(response, 401, "EMAIL_NOT_VERIFIED")


def test_invalid_google_token_is_rejected(api):
    with google_tokens(identity("person@company.com")):
        response = api.post("/api/v1/auth/google", json={"id_token": "nope"}, headers=CSRF)
    assert_error(response, 401, "INVALID_ID_TOKEN")


def test_session_cookie_flags_and_lifetime(api, org):
    response = login(api, org.super_admin.email)
    header = response.headers["set-cookie"]
    lowered = header.lower()
    assert "httponly" in lowered
    assert "samesite=lax" in lowered
    assert "max-age=28800" in lowered
    assert re.search(r"(?:^|;)\s*secure(?:;|$)", lowered) is None
    payload = jwt.decode(api.cookies["atlas_session"], "test-secret-key-for-atlas-sessions", algorithms=["HS256"])
    assert payload["typ"] == "session"
    assert payload["sub"] == str(org.super_admin.id)
    assert payload["exp"] - payload["iat"] == 8 * 60 * 60
    assert api.cookies["atlas_session"] not in response.text


def test_session_cookie_is_secure_in_production(api, org, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    response = google_login(api, identity(org.admin.email, sub="sub-sarah"))
    assert response.status_code == 200, response.text
    assert re.search(r"(?:^|;)\s*secure(?:;|$)", response.headers["set-cookie"].lower())


def test_logout_clears_the_cookie(api, org):
    login(api, org.employee.email)
    assert api.get("/api/v1/auth/me").status_code == 200
    response = api.post("/api/v1/auth/logout", headers=CSRF)
    assert response.status_code == 204
    assert api.get("/api/v1/auth/me").status_code == 401


def test_me_requires_authentication(api):
    assert_error(api.get("/api/v1/auth/me"), 401, "UNAUTHENTICATED")


def test_test_login_exists_only_in_the_test_environment(api, org, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    response = api.post("/api/v1/auth/test-login", json={"email": org.super_admin.email}, headers=CSRF)
    assert_error(response, 404, "NOT_FOUND")


def test_test_login_rejects_bots_and_deactivated_users(api, org):
    assert_error(api.post("/api/v1/auth/test-login", json={"email": org.bot.email}, headers=CSRF), 403, "BOT_LOGIN_FORBIDDEN")
    assert_error(
        api.post("/api/v1/auth/test-login", json={"email": org.deactivated.email}, headers=CSRF),
        403,
        "ACCOUNT_DEACTIVATED",
    )


def test_cookie_mutations_require_the_csrf_header(api):
    api.cookies.set("atlas_session", "not-a-real-session")
    blocked = api.post("/api/v1/auth/logout")
    assert_error(blocked, 403, "CSRF_REQUIRED")
    reached_auth = api.post("/api/v1/auth/logout", headers=CSRF)
    assert_error(reached_auth, 401, "UNAUTHENTICATED")


def test_requests_without_a_session_cookie_skip_csrf(api, db_session):
    db_session.add(Department(code="product", name="Product", description=None))
    db_session.flush()
    with google_tokens(identity("person@gmail.com")):
        response = api.post("/api/v1/auth/google", json={"id_token": "good-token"})
    assert_error(response, 403, "DOMAIN_NOT_ALLOWED")


def test_google_login_is_rate_limited(api, monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT", "2")
    google_login_limiter.reset()
    with google_tokens(identity("person@gmail.com")):
        for _ in range(2):
            response = api.post("/api/v1/auth/google", json={"id_token": "good-token"})
            assert response.status_code == 403
        blocked = api.post("/api/v1/auth/google", json={"id_token": "good-token"})
    assert_error(blocked, 429, "RATE_LIMITED")
    assert blocked.headers["retry-after"] == "60"


def test_google_verifier_checks_the_configured_audience(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-123")
    seen = {}

    def fake(token, request, audience):
        seen["token"] = token
        seen["audience"] = audience
        assert request is not None
        return {"sub": "abc", "email": "Ada@Company.com", "email_verified": "true", "name": " Ada ", "picture": "https://img"}

    monkeypatch.setattr("app.integrations.google_auth.google_id_token.verify_oauth2_token", fake)
    verified = verify_google_id_token("raw-token")
    assert seen == {"token": "raw-token", "audience": "client-123"}
    assert verified.email == "ada@company.com"
    assert verified.email_verified is True
    assert verified.name == "Ada"
    assert verified.picture == "https://img"


def test_google_verifier_reports_configuration_and_token_failures(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    with pytest.raises(ApiError) as missing:
        verify_google_id_token("raw-token")
    assert missing.value.status_code == 500
    assert missing.value.detail["code"] == "MISCONFIGURED"

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-123")

    def fake(*_args, **_kwargs):
        raise ValueError("bad token")

    monkeypatch.setattr("app.integrations.google_auth.google_id_token.verify_oauth2_token", fake)
    with pytest.raises(ApiError) as invalid:
        verify_google_id_token("raw-token")
    assert invalid.value.status_code == 401
    assert invalid.value.detail["code"] == "INVALID_ID_TOKEN"
