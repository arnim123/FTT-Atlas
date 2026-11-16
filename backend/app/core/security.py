import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.core.errors import ApiError

SESSION_TTL = timedelta(hours=8)
SESSION_ALGORITHM = "HS256"


class InvalidSession(Exception):
    """The cookie is missing, expired, or not a session token."""


def hash_token(secret: str) -> str:
    """Hex sha256 digest stored in api_tokens.token_hash. The raw secret is never stored."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def issue_session_token(user_id: UUID) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise ApiError(500, "MISCONFIGURED", "Session signing is not configured.")
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "iat": now, "exp": now + SESSION_TTL, "typ": "session"}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=SESSION_ALGORITHM)
    return token if isinstance(token, str) else token.decode("ascii")


def decode_session_token(token: str) -> UUID:
    settings = get_settings()
    if not settings.jwt_secret:
        raise InvalidSession
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[SESSION_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidSession from exc
    if payload.get("typ") != "session":
        raise InvalidSession
    try:
        return UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise InvalidSession from exc
