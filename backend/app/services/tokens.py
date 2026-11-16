"""API tokens. Only a prefix and a SHA-256 hash are stored. The secret is shown once."""

import hmac
import re
import secrets
from base64 import urlsafe_b64encode
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.events import USER_ACCESS_CHANGED, event_bus
from app.core.principal import SCOPE_DOCS_READ, SCOPE_DOCS_WRITE, SCOPE_VOCABULARY, AuthMethod, Principal, scopes_for_role
from app.core.security import hash_token
from app.models.access import ApiToken
from app.models.base import utcnow
from app.models.user import User
from app.services.audit import remember_actor
from app.services.org_settings import get_org_settings

TOKEN_PREFIX = "dms_pat_"
_TOKEN = re.compile(rf"^({TOKEN_PREFIX}[A-Za-z0-9]{{8}})_(.+)$")
_DUMMY_HASH = hash_token("dms_pat_00000000_dummy")
DEFAULT_TOKEN_DAYS = 90
LAST_USED_INTERVAL = timedelta(minutes=1)
_ADMIN_ROLES = frozenset({"super_admin", "admin"})


def register_token_handlers() -> None:
    event_bus.subscribe(USER_ACCESS_CHANGED, revoke_tokens_for_deactivated_user)


def create_token(
    session: Session,
    principal: Principal,
    *,
    name: str,
    scopes: list[str] | None,
    expires_in_days: int | None,
    user_id: UUID | None,
) -> tuple[ApiToken, str]:
    target = _target_user(session, principal, user_id)
    if not target.is_active:
        raise ApiError(403, "ACCOUNT_DEACTIVATED", "Deactivated users cannot receive tokens.")
    org = get_org_settings(session)
    granted = _scopes_for_issue(target, scopes, allow_write=org.allow_write_scopes)
    days = _lifetime_days(expires_in_days, org.max_token_days)
    prefix, secret = _mint(session)
    row = ApiToken(
        user_id=target.id,
        name=name.strip(),
        token_prefix=prefix,
        token_hash=hash_token(secret),
        scopes=granted,
        expires_at=utcnow() + timedelta(days=days),
        created_by=principal.user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, secret


def list_tokens(session: Session, *, user_id: UUID | None = None) -> list[ApiToken]:
    query = select(ApiToken).order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
    if user_id is not None:
        query = query.where(ApiToken.user_id == user_id)
    return list(session.scalars(query))


def revoke_token(session: Session, token_id: UUID, *, user_id: UUID | None = None) -> None:
    row = session.get(ApiToken, token_id)
    if row is None or (user_id is not None and row.user_id != user_id):
        raise ApiError(404, "NOT_FOUND", "Token not found.")
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        session.commit()


def principal_for_token(session: Session, raw: str, ip: str | None) -> Principal:
    """Validate a bearer secret. Raises 401 or 403. Does not fall through to another credential."""
    row = _match(session, raw)
    now = utcnow()
    if row.revoked_at is not None:
        raise ApiError(401, "TOKEN_REVOKED", "This token has been revoked.")
    if row.expires_at is None or row.expires_at <= now:
        raise ApiError(401, "TOKEN_EXPIRED", "This token has expired.")
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise ApiError(401, "TOKEN_INACTIVE", "This token is no longer valid.")
    org = get_org_settings(session)
    scopes = set(row.scopes) & set(scopes_for_role(user.role)) & set(SCOPE_VOCABULARY)
    if not org.allow_write_scopes:
        scopes.discard(SCOPE_DOCS_WRITE)
    if SCOPE_DOCS_WRITE in scopes:
        scopes.add(SCOPE_DOCS_READ)
    if SCOPE_DOCS_READ not in scopes:
        raise ApiError(401, "TOKEN_INACTIVE", "This token is no longer valid.")
    principal = Principal(
        user=user,
        auth_method=AuthMethod.bearer,
        scopes=frozenset(scopes),
        token_id=row.id,
        client_name=row.name,
    )
    remember_actor(principal)
    if not org.external_ai_enabled:
        raise ApiError(403, "EXTERNAL_ACCESS_DISABLED", "External AI access is turned off.")
    _touch_used(session, row, ip, now)
    return principal


def revoke_tokens_for_deactivated_user(payload: dict) -> None:
    """A deactivated user cannot keep calling with a token issued earlier."""
    changes = payload.get("changes") or {}
    active = changes.get("is_active")
    if not isinstance(active, dict) or active.get("to") is not False:
        return
    user_id = payload.get("user_id")
    if not user_id:
        return
    from app.core.database import current_request_session
    from app.core.sessions import open_session

    bound = current_request_session()
    if bound is not None:
        _revoke_all(bound, UUID(str(user_id)))
        return
    with open_session() as session:
        _revoke_all(session, UUID(str(user_id)))


def _revoke_all(session: Session, user_id: UUID) -> None:
    now = utcnow()
    rows = session.scalars(select(ApiToken).where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None)))
    changed = False
    for row in rows:
        row.revoked_at = now
        changed = True
    if changed:
        session.commit()


def _match(session: Session, raw: str) -> ApiToken:
    matched = _TOKEN.fullmatch(raw.strip())
    digest = hash_token(raw.strip())
    row = None
    if matched:
        row = session.scalar(select(ApiToken).where(ApiToken.token_prefix == matched.group(1)))
    candidate = row.token_hash if row is not None and len(row.token_hash) == len(digest) else _DUMMY_HASH
    if not hmac.compare_digest(candidate, digest) or row is None:
        raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.")
    return row


def _mint(session: Session) -> tuple[str, str]:
    for _ in range(5):
        prefix = TOKEN_PREFIX + secrets.token_hex(4)
        if session.scalar(select(ApiToken.id).where(ApiToken.token_prefix == prefix)) is not None:
            continue
        secret_body = urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
        return prefix, f"{prefix}_{secret_body}"
    raise ApiError(500, "TOKEN_ISSUE_FAILED", "Could not issue a token. Try again.")


def _lifetime_days(requested: int | None, maximum: int) -> int:
    days = DEFAULT_TOKEN_DAYS if requested is None else requested
    if days < 1:
        raise ApiError(422, "TOKEN_EXPIRY_INVALID", "Token expiry must be at least 1 day.")
    if days > maximum:
        raise ApiError(422, "TOKEN_EXPIRY_TOO_LONG", f"Token expiry cannot exceed {maximum} days.")
    return days


def _scopes_for_issue(user: User, requested: list[str] | None, *, allow_write: bool) -> list[str]:
    asked = frozenset(requested or [SCOPE_DOCS_READ])
    if not asked or not asked <= SCOPE_VOCABULARY:
        raise ApiError(422, "UNKNOWN_SCOPE", "Tokens can only carry docs:read and docs:write.")
    if not asked <= scopes_for_role(user.role):
        raise ApiError(403, "MISSING_SCOPE", "This account cannot be granted that scope.")
    if SCOPE_DOCS_WRITE in asked and not allow_write:
        raise ApiError(403, "WRITE_SCOPES_DISABLED", "Write scopes are turned off for external access.")
    granted = set(asked)
    granted.add(SCOPE_DOCS_READ)
    return sorted(granted)


def _target_user(session: Session, principal: Principal, user_id: UUID | None) -> User:
    if user_id is None or user_id == principal.user.id:
        return principal.user
    if principal.user.role.value not in _ADMIN_ROLES:
        raise ApiError(403, "FORBIDDEN", "You can only create tokens for yourself.")
    target = session.get(User, user_id)
    if target is None or not target.is_bot:
        raise ApiError(422, "NOT_A_BOT", "Administrators can create tokens for bot users only.")
    return target


def _touch_used(session: Session, row: ApiToken, ip: str | None, now) -> None:
    seen = row.last_used_at
    if seen is not None and now - seen < LAST_USED_INTERVAL:
        return
    row.last_used_at = now
    if ip:
        row.last_used_ip = ip[:64]
    session.commit()
