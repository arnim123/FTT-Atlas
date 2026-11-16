"""Who is calling, and which credential established that.

Routers depend on `get_principal`. New credentials are added to `AUTHENTICATORS`;
the route functions stay the same. Bearer API tokens and OAuth are inserted ahead
of the session cookie so an explicit credential wins when both are present.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Protocol
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.enums import UserRole
from app.core.errors import ApiError
from app.core.security import InvalidSession, decode_session_token
from app.models.base import utcnow
from app.models.user import User

SCOPE_DOCS_READ = "docs:read"
SCOPE_DOCS_WRITE = "docs:write"
SCOPE_VOCABULARY = frozenset({SCOPE_DOCS_READ, SCOPE_DOCS_WRITE})
LAST_SEEN_INTERVAL = timedelta(minutes=5)

ROLE_SCOPES: dict[UserRole, frozenset[str]] = {
    UserRole.super_admin: frozenset({SCOPE_DOCS_READ, SCOPE_DOCS_WRITE}),
    UserRole.admin: frozenset({SCOPE_DOCS_READ, SCOPE_DOCS_WRITE}),
    UserRole.manager: frozenset({SCOPE_DOCS_READ, SCOPE_DOCS_WRITE}),
    UserRole.employee: frozenset({SCOPE_DOCS_READ, SCOPE_DOCS_WRITE}),
    UserRole.guest: frozenset({SCOPE_DOCS_READ}),
}


class AuthMethod(str, Enum):
    session = "session"
    bearer = "bearer"
    oauth = "oauth"


@dataclass(frozen=True)
class Principal:
    user: User
    auth_method: AuthMethod
    scopes: frozenset[str]
    token_id: UUID | None = None
    client_name: str | None = None


def scopes_for_role(role: UserRole) -> frozenset[str]:
    return ROLE_SCOPES[role]


class Authenticator(Protocol):
    def authenticate(self, request: Request, session: Session) -> Principal | None: ...


class BearerTokenAuthenticator:
    """API tokens. An Authorization header that is present and invalid is rejected.

    It does not fall through to the session cookie, so a bad token cannot ride
    along on a browser session.
    """

    def authenticate(self, request: Request, session: Session) -> Principal | None:
        header = request.headers.get("authorization")
        if not header:
            return None
        scheme, _, value = header.partition(" ")
        if scheme.lower() != "bearer":
            return None
        raw = value.strip()
        if not raw:
            raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.")
        from app.services.tokens import TOKEN_PREFIX, principal_for_token

        if not raw.startswith(TOKEN_PREFIX):
            return None
        return principal_for_token(session, raw, _client_ip(request))


class OAuthAuthenticator:
    """Opaque OAuth access tokens. A bearer value that is not an API token is rejected here.

    It does not fall through to the session cookie.
    """

    def authenticate(self, request: Request, session: Session) -> Principal | None:
        header = request.headers.get("authorization")
        if not header:
            return None
        scheme, _, value = header.partition(" ")
        if scheme.lower() != "bearer":
            return None
        raw = value.strip()
        if not raw:
            return None
        from app.services.tokens import TOKEN_PREFIX

        if raw.startswith(TOKEN_PREFIX):
            return None
        from app.services.oauth import principal_for_access_token

        return principal_for_access_token(session, raw, _client_ip(request), path=request.url.path)


class SessionCookieAuthenticator:
    def authenticate(self, request: Request, session: Session) -> Principal | None:
        raw = request.cookies.get(get_settings().session_cookie_name)
        if not raw:
            return None
        try:
            user_id = decode_session_token(raw)
        except InvalidSession:
            return None
        user = session.get(User, user_id)
        if user is None or not user.is_active or user.is_bot:
            return None
        return Principal(
            user=user,
            auth_method=AuthMethod.session,
            scopes=scopes_for_role(user.role),
            token_id=None,
            client_name=None,
        )


# First match wins. API tokens and OAuth are ahead of the session cookie so an explicit credential wins.
AUTHENTICATORS: list[Authenticator] = [
    BearerTokenAuthenticator(),
    OAuthAuthenticator(),
    SessionCookieAuthenticator(),
]


def get_principal(request: Request, session: Session = Depends(get_db)) -> Principal:
    for authenticator in AUTHENTICATORS:
        principal = authenticator.authenticate(request, session)
        if principal is not None:
            _touch_last_seen(session, principal.user)
            if principal.auth_method is not AuthMethod.session:
                from app.core.external import enforce_external_http

                enforce_external_http(request, principal)
            return principal
    raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.")


def require_roles(*roles: UserRole) -> Callable[..., Principal]:
    allowed = frozenset(roles)

    def checker(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.user.role not in allowed:
            raise ApiError(403, "FORBIDDEN", "You do not have access to this action.")
        return principal

    return checker


def require_scope(*scopes: str) -> Callable[..., Principal]:
    needed = frozenset(scopes)
    unknown = needed - SCOPE_VOCABULARY
    if unknown:
        raise ValueError(f"Unknown scope: {', '.join(sorted(unknown))}")

    def checker(principal: Principal = Depends(get_principal)) -> Principal:
        if not needed <= principal.scopes:
            raise ApiError(403, "MISSING_SCOPE", "This action requires a scope your credential does not grant.")
        return principal

    return checker


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hop = forwarded.split(",")[0].strip()
        return hop[:64] or None
    if request.client is not None and request.client.host:
        return request.client.host[:64]
    return None


def _touch_last_seen(session: Session, user: User) -> None:
    now = utcnow()
    seen = user.last_seen_at
    if seen is not None and now - seen < LAST_SEEN_INTERVAL:
        return
    user.last_seen_at = now
    session.commit()
