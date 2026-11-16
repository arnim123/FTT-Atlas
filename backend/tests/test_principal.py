from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.enums import UserRole
from app.core.errors import ApiError
from app.core.principal import (
    SCOPE_DOCS_READ,
    SCOPE_DOCS_WRITE,
    AuthMethod,
    Principal,
    SessionCookieAuthenticator,
    get_principal,
    require_roles,
    require_scope,
    scopes_for_role,
)
from app.core.security import issue_session_token
from app.models.base import utcnow
from app.models.user import User
from tests.helpers import assert_error, login, request_with_cookie


def test_session_cookie_builds_the_principal(api, db_session, org):
    login(api, org.admin.email)
    admin = SessionCookieAuthenticator().authenticate(request_with_cookie(api.cookies["atlas_session"]), db_session)
    assert admin is not None
    assert admin.user.id == org.admin.id
    assert admin.auth_method is AuthMethod.session
    assert admin.scopes == frozenset({SCOPE_DOCS_READ, SCOPE_DOCS_WRITE})
    assert admin.token_id is None
    assert admin.client_name is None

    login(api, org.guest.email)
    guest = SessionCookieAuthenticator().authenticate(request_with_cookie(api.cookies["atlas_session"]), db_session)
    assert guest is not None
    assert guest.scopes == frozenset({SCOPE_DOCS_READ})
    assert scopes_for_role(UserRole.guest) == guest.scopes

    wired = get_principal(request_with_cookie(api.cookies["atlas_session"]), db_session)
    assert wired.user.id == org.guest.id
    assert wired.auth_method is AuthMethod.session


def test_inactive_and_bot_cookies_are_not_principals(api, db_session, org):
    authenticator = SessionCookieAuthenticator()
    for user in (org.bot, org.deactivated):
        token = issue_session_token(user.id)
        assert authenticator.authenticate(request_with_cookie(token), db_session) is None
    assert authenticator.authenticate(request_with_cookie("not-a-jwt"), db_session) is None
    with pytest.raises(ApiError) as caught:
        get_principal(request_with_cookie(issue_session_token(org.bot.id)), db_session)
    assert caught.value.status_code == 401


def test_authenticators_run_in_order_without_router_changes(api, db_session, org, monkeypatch):
    login(api, org.admin.email)
    sentinel = Principal(
        user=org.guest,
        auth_method=AuthMethod.bearer,
        scopes=frozenset({SCOPE_DOCS_READ}),
        token_id=uuid4(),
        client_name="later",
    )

    class Stub:
        def authenticate(self, request, session):
            return sentinel

    monkeypatch.setattr(
        "app.core.principal.AUTHENTICATORS",
        [Stub(), SessionCookieAuthenticator()],
    )
    principal = get_principal(
        request_with_cookie(api.cookies["atlas_session"], path="/api/v1/agent/me"),
        db_session,
    )
    assert principal is sentinel
    assert principal.token_id is not None
    assert principal.client_name == "later"


def test_last_seen_updates_at_most_once_per_five_minutes(api, org):
    login(api, org.employee.email)
    first = api.get("/api/v1/auth/me").json()["last_seen_at"]
    assert api.get("/api/v1/auth/me").json()["last_seen_at"] == first

    recent = utcnow() - timedelta(minutes=4)
    org.employee.last_seen_at = recent
    assert _same(api.get("/api/v1/auth/me").json()["last_seen_at"], recent)

    stale = utcnow() - timedelta(minutes=6)
    org.employee.last_seen_at = stale
    assert not _same(api.get("/api/v1/auth/me").json()["last_seen_at"], stale)


def test_deactivated_session_stops_working(api, org, db_session):
    login(api, org.employee.email)
    org.employee.is_active = False
    db_session.flush()
    assert_error(api.get("/api/v1/auth/me"), 401, "UNAUTHENTICATED")


def test_scope_and_role_dependencies():
    admin = _principal(UserRole.admin, frozenset({SCOPE_DOCS_READ}))
    guest = _principal(UserRole.guest, scopes_for_role(UserRole.guest))
    require_scope(SCOPE_DOCS_READ)(principal=admin)
    with pytest.raises(ApiError) as missing:
        require_scope(SCOPE_DOCS_WRITE)(principal=admin)
    assert missing.value.detail["code"] == "MISSING_SCOPE"
    with pytest.raises(ValueError):
        require_scope("docs:delete")

    require_roles(UserRole.admin, UserRole.super_admin)(principal=admin)
    with pytest.raises(ApiError) as forbidden:
        require_roles(UserRole.admin)(principal=guest)
    assert forbidden.value.status_code == 403
    assert forbidden.value.detail["code"] == "FORBIDDEN"


def _principal(role: UserRole, scopes: frozenset[str]) -> Principal:
    user = User(
        id=uuid4(),
        email=f"{role.value}@company.com",
        name=role.value,
        role=role,
        department_id=uuid4(),
        is_active=True,
        is_bot=False,
    )
    return Principal(user=user, auth_method=AuthMethod.session, scopes=scopes, token_id=None, client_name=None)


def _same(rendered: str, moment) -> bool:
    from datetime import datetime

    parsed = datetime.fromisoformat(rendered.replace("Z", "+00:00"))
    return abs(parsed - moment) < timedelta(seconds=1)
