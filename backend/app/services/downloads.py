"""Short-lived HMAC download URLs for uploaded files.

The signature names the user and the document. Redeeming it checks access again
through the document service, so a link dies when permission or the kill switch does.
"""

import hashlib
import hmac
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.principal import SCOPE_DOCS_READ, SCOPE_DOCS_WRITE, AuthMethod, Principal, scopes_for_role
from app.models.base import utcnow
from app.models.user import User
from app.services.org_settings import get_org_settings

LINK_TTL = timedelta(minutes=5)


def issue_download_link(session: Session, principal: Principal, document_id: UUID) -> tuple[str, object]:
    from app.services.documents import get_document

    result = get_document(session, principal, document_id)
    if not result.document.storage_key:
        raise ApiError(404, "NO_FILE", "This document has no uploaded file.")
    expires = utcnow() + LINK_TTL
    payload = {
        "d": str(document_id),
        "u": str(principal.user.id),
        "t": "" if principal.token_id is None else str(principal.token_id),
        "e": int(expires.timestamp()),
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = _pack(body, _sign(body))
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/api/v1/agent/downloads/{token}", expires


def redeem_download_link(session: Session, token: str) -> tuple[Principal, UUID]:
    """Return the principal and document id bound into a valid link."""
    try:
        raw = urlsafe_b64decode(_pad(token))
        body, signature = raw.rsplit(b".", 1)
        expected = _sign(body)
    except (ValueError, UnicodeError) as exc:
        raise ApiError(404, "NOT_FOUND", "Document not found.") from exc
    if not hmac.compare_digest(signature, expected):
        raise ApiError(404, "NOT_FOUND", "Document not found.")
    try:
        payload = json.loads(body)
        document_id = UUID(payload["d"])
        user_id = UUID(payload["u"])
        expires = int(payload["e"])
        token_id = UUID(payload["t"]) if payload.get("t") else None
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(404, "NOT_FOUND", "Document not found.") from exc
    if expires < int(utcnow().timestamp()):
        raise ApiError(401, "LINK_EXPIRED", "This download link has expired. Ask for a new one.")
    if not get_org_settings(session).external_ai_enabled:
        raise ApiError(403, "EXTERNAL_ACCESS_DISABLED", "External AI access is turned off.")
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise ApiError(404, "NOT_FOUND", "Document not found.")
    scopes = set(scopes_for_role(user.role))
    scopes.discard(SCOPE_DOCS_WRITE)
    if SCOPE_DOCS_READ not in scopes:
        raise ApiError(404, "NOT_FOUND", "Document not found.")
    principal = Principal(
        user=user,
        auth_method=AuthMethod.bearer if token_id else AuthMethod.session,
        scopes=frozenset({SCOPE_DOCS_READ}),
        token_id=token_id,
        client_name="download-link",
    )
    return principal, document_id


def _sign(body: bytes) -> bytes:
    secret = get_settings().jwt_secret
    if not secret:
        raise ApiError(500, "MISCONFIGURED", "Download links are not configured.")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()


def _pack(body: bytes, signature: bytes) -> str:
    return urlsafe_b64encode(body + b"." + signature).decode("ascii").rstrip("=")


def _pad(value: str) -> str:
    return value + "=" * (-len(value) % 4)
