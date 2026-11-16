from contextlib import contextmanager
from uuid import UUID

from starlette.requests import Request

from app.core.errors import ApiError
from app.core.principal import AuthMethod, Principal, get_principal
from app.integrations.google_auth import GoogleIdentity
from app.main import app

CSRF = {"X-Requested-With": "fetch"}


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    detail = response.json()["detail"]
    assert detail["code"] == code
    return detail


def login(api, email: str):
    response = api.post("/api/v1/auth/test-login", json={"email": email}, headers=CSRF)
    assert response.status_code == 200, response.text
    return response


def identity(email: str, *, sub="google-sub", email_verified=True, name="Ada Lovelace", picture="https://example.com/a.png") -> GoogleIdentity:
    return GoogleIdentity(sub=sub, email=email.strip().lower(), email_verified=email_verified, name=name, picture=picture)


@contextmanager
def google_tokens(person: GoogleIdentity, token: str = "good-token"):
    from app.integrations.google_auth import get_google_verifier

    def verifier(raw: str) -> GoogleIdentity:
        if raw != token:
            raise ApiError(401, "INVALID_ID_TOKEN", "Google token could not be verified.")
        return person

    app.dependency_overrides[get_google_verifier] = lambda: verifier
    try:
        yield token
    finally:
        app.dependency_overrides.pop(get_google_verifier, None)


def google_login(api, person: GoogleIdentity, token: str = "good-token"):
    with google_tokens(person, token):
        return api.post("/api/v1/auth/google", json={"id_token": token}, headers=CSRF)


@contextmanager
def acting_as(user, scopes, *, method: AuthMethod = AuthMethod.session, token_id: UUID | None = None, client_name: str | None = None):
    """Install a principal without a session cookie. Scopes are exactly the set given."""
    principal = Principal(
        user=user,
        auth_method=method,
        scopes=frozenset(scopes),
        token_id=token_id,
        client_name=client_name,
    )
    app.dependency_overrides[get_principal] = lambda bound=principal: bound
    try:
        yield principal
    finally:
        app.dependency_overrides.pop(get_principal, None)


def request_with_cookie(token: str | None, cookie_name: str = "atlas_session", path: str = "/") -> Request:
    headers = []
    if token is not None:
        headers.append((b"cookie", f"{cookie_name}={token}".encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    return Request(scope)
