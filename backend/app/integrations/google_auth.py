from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings
from app.core.errors import ApiError


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str | None = None
    picture: str | None = None


def verify_google_id_token(token: str) -> GoogleIdentity:
    settings = get_settings()
    if not settings.google_client_id:
        raise ApiError(500, "MISCONFIGURED", "Google sign-in is not configured.")
    try:
        claims = google_id_token.verify_oauth2_token(token, google_requests.Request(), settings.google_client_id)
    except Exception as exc:
        raise ApiError(401, "INVALID_ID_TOKEN", "Google token could not be verified.") from exc
    email = claims.get("email")
    subject = claims.get("sub")
    if not isinstance(email, str) or not email.strip() or not subject:
        raise ApiError(401, "INVALID_ID_TOKEN", "Google token is missing an email.")
    verified = claims.get("email_verified")
    name = claims.get("name")
    picture = claims.get("picture")
    return GoogleIdentity(
        sub=str(subject),
        email=email.strip().lower(),
        email_verified=verified is True or verified == "true",
        name=name.strip() if isinstance(name, str) and name.strip() else None,
        picture=picture if isinstance(picture, str) and picture else None,
    )


def get_google_verifier():
    return verify_google_id_token
