"""OAuth 2.1 authorization server for the MCP resource.

Authlib's authorization server is shaped around Flask and stores bearer secrets
in the clear. These grants stay in Postgres as SHA-256 hashes, with the same
session cookie the web app already uses for Google sign-in.

The flow follows MCP authorization (2025-11-25): RFC 8414 metadata, RFC 7591
registration, Client ID Metadata Documents, RFC 8707 resource indicators,
RFC 9207 iss, PKCE S256, and RFC 7009 revocation. Only authorization_code and
rotating refresh_token are issued.
"""

import hashlib
import hmac
import ipaddress
import re
import secrets
import socket
import time
from base64 import b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import timedelta
from threading import Event, Thread
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
from uuid import UUID

import requests
from pydantic import AnyHttpUrl, ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.events import USER_ACCESS_CHANGED, event_bus
from app.core.principal import (
    SCOPE_DOCS_READ,
    SCOPE_DOCS_WRITE,
    SCOPE_VOCABULARY,
    AuthMethod,
    Principal,
    scopes_for_role,
)
from app.core.rate_limit import oauth_register_limiter
from app.core.security import hash_token
from app.models.base import utcnow
from app.models.oauth import OAuthAuthorizationCode, OAuthClient, OAuthGrant, OAuthToken
from app.models.user import User
from app.services.audit import remember_actor
from app.services.org_settings import get_org_settings
from app.services.tokens import TOKEN_PREFIX

ACCESS_PREFIX = "dms_oat_"
REFRESH_PREFIX = "dms_ort_"
CODE_PREFIX = "dms_oac_"
CODE_TTL = timedelta(minutes=10)
ACCESS_TTL = timedelta(hours=1)
REFRESH_TTL = timedelta(days=30)
LAST_USED_INTERVAL = timedelta(minutes=1)
_VERIFIER = re.compile(r"[A-Za-z0-9._~-]{43,128}")
_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
_GRANT_TYPES = frozenset({"authorization_code", "refresh_token"})
_AUTH_METHODS = frozenset({"none", "client_secret_basic", "client_secret_post"})
_METADATA_CACHE: dict[str, tuple[float, dict]] = {}
_stop = Event()
_cleanup_started = False


class OAuthError(Exception):
    def __init__(self, error: str, description: str, status: int = 400, headers: dict[str, str] | None = None) -> None:
        self.error = error
        self.description = description
        self.status = status
        self.headers = headers or {}


@dataclass(frozen=True)
class AuthorizeDecision:
    location: str | None = None
    error: str | None = None
    description: str | None = None
    status: int = 400


def issuer() -> str:
    return get_settings().public_base_url.rstrip("/")


def mcp_resource() -> str:
    return issuer() + "/mcp"


def protected_resource_metadata() -> dict:
    return {
        "resource": mcp_resource(),
        "authorization_servers": [issuer()],
        "scopes_supported": [SCOPE_DOCS_READ, SCOPE_DOCS_WRITE],
        "bearer_methods_supported": ["header"],
        "resource_name": get_settings().app_name,
    }


def authorization_server_metadata() -> dict:
    base = issuer()
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "revocation_endpoint": f"{base}/oauth/revoke",
        "scopes_supported": [SCOPE_DOCS_READ, SCOPE_DOCS_WRITE],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_basic", "client_secret_post"],
        "revocation_endpoint_auth_methods_supported": ["none", "client_secret_basic", "client_secret_post"],
        "client_id_metadata_document_supported": True,
        "authorization_response_iss_parameter_supported": True,
    }


def canonical_resource(value: str) -> str | None:
    text = (value or "").strip()
    if not text or any(char in text for char in "#?"):
        return None
    try:
        parsed = AnyHttpUrl(text)
    except ValidationError:
        return None
    if parsed.query or parsed.fragment:
        return None
    return str(parsed).removesuffix("/")


def resource_matches(value: str) -> bool:
    got = canonical_resource(value)
    expected = canonical_resource(mcp_resource())
    return got is not None and expected is not None and got == expected


def _reject_when_external_access_is_off(session: Session) -> None:
    if not get_org_settings(session).external_ai_enabled:
        raise OAuthError("access_denied", "External AI access is turned off.", 400)


def register_client(session: Session, body: dict, ip: str | None) -> tuple[dict, int]:
    _consume_registration(ip)
    redirects = body.get("redirect_uris")
    if not isinstance(redirects, list) or not 1 <= len(redirects) <= 10:
        raise OAuthError("invalid_redirect_uri", "redirect_uris must list 1 to 10 URIs.")
    if not all(isinstance(item, str) and redirect_allowed(item) for item in redirects):
        raise OAuthError("invalid_redirect_uri", "A redirect URI must be https, or http on localhost.")
    grants = body.get("grant_types") or ["authorization_code", "refresh_token"]
    if not isinstance(grants, list) or any(item not in _GRANT_TYPES for item in grants) or "authorization_code" not in grants:
        raise OAuthError("invalid_client_metadata", "Only authorization_code and refresh_token are supported.")
    responses = body.get("response_types") or ["code"]
    if responses != ["code"]:
        raise OAuthError("invalid_client_metadata", "Only the code response type is supported.")
    method = body.get("token_endpoint_auth_method") or "none"
    if method not in _AUTH_METHODS:
        raise OAuthError("invalid_client_metadata", "Unsupported token endpoint authentication method.")
    name = body.get("client_name") or "Unnamed application"
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise OAuthError("invalid_client_metadata", "client_name must be 120 characters or fewer.")
    address = (ip or "unknown")[:64]
    existing = session.scalar(
        select(func.count())
        .select_from(OAuthClient)
        .where(OAuthClient.source_ip == address, OAuthClient.registration_kind == "dynamic")
    ) or 0
    if existing >= get_settings().oauth_clients_per_ip:
        raise OAuthError("invalid_client_metadata", "Too many clients are registered from this address.")
    secret = None
    secret_hash = None
    if method != "none":
        secret = "dms_ocs_" + secrets.token_urlsafe(32)
        secret_hash = hash_token(secret)
    row = OAuthClient(
        client_id="dms_ocl_" + secrets.token_urlsafe(24),
        client_secret_hash=secret_hash,
        client_name=name.strip(),
        redirect_uris=list(redirects),
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method=method,
        registration_kind="dynamic",
        source_ip=address,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    payload = {
        "client_id": row.client_id,
        "client_id_issued_at": int(row.created_at.timestamp()),
        "client_name": row.client_name,
        "redirect_uris": list(row.redirect_uris),
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": method,
    }
    if secret is not None:
        payload["client_secret"] = secret
        payload["client_secret_expires_at"] = 0
    return payload, 201


def begin_authorization(session: Session, user: User | None, params: dict[str, str], return_url: str, ip: str | None) -> AuthorizeDecision:
    client_id = (params.get("client_id") or "").strip()
    if not client_id:
        return AuthorizeDecision(error="invalid_request", description="client_id is required.")
    try:
        client = _client_for_authorize(session, client_id, ip)
    except OAuthError as exc:
        return AuthorizeDecision(error=exc.error, description=exc.description, status=exc.status, location=None)
    redirect_uri = params.get("redirect_uri") or ""
    if not redirect_allowed(redirect_uri) or not any(redirect_matches(redirect_uri, item) for item in client.redirect_uris):
        return AuthorizeDecision(error="invalid_request", description="redirect_uri is not registered for this client.")
    state = params.get("state")
    if state is not None and len(state) > 512:
        return _redirect_error(redirect_uri, "invalid_request", "state is too long.", state)

    def fail(error: str, description: str) -> AuthorizeDecision:
        return _redirect_error(redirect_uri, error, description, state)

    if params.get("response_type") != "code":
        return fail("unsupported_response_type", "Only response_type=code is supported.")
    if params.get("response_mode") not in (None, "", "query"):
        return fail("invalid_request", "response_mode must be query.")
    if params.get("code_challenge_method") != "S256" or not params.get("code_challenge"):
        return fail("invalid_request", "PKCE S256 is required.")
    if len(params.get("code_challenge") or "") > 128:
        return fail("invalid_request", "code_challenge is too long.")
    resource = params.get("resource") or ""
    if not resource_matches(resource):
        return fail("invalid_target", "resource must be the MCP server URL.")
    try:
        asked = _parse_scope(params.get("scope"))
    except OAuthError as exc:
        return fail(exc.error, exc.description)
    if user is None:
        return AuthorizeDecision(location=_login_location(return_url))
    try:
        ceiling = _ceiling_for(user, asked)
    except OAuthError as exc:
        return fail(exc.error, exc.description)
    row = OAuthAuthorizationCode(
        oauth_client_id=client.id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        requested_scopes=ceiling,
        code_challenge=params["code_challenge"],
        code_challenge_method="S256",
        resource=canonical_resource(resource) or mcp_resource(),
        state=state,
        expires_at=utcnow() + CODE_TTL,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return AuthorizeDecision(location=_consent_location(row.id))


def consent_view(session: Session, user: User, request_id: UUID) -> dict:
    row, client = _pending(session, user, request_id)
    org = get_org_settings(session)
    offered = _offered(row.requested_scopes, allow_write=org.allow_write_scopes)
    return {
        "request_id": row.id,
        "app_name": client.client_name,
        "redirect_domain": redirect_domain(row.redirect_uri),
        "redirect_uri": row.redirect_uri,
        "verified": client_verified(client, row.redirect_uri),
        "localhost_redirect": is_loopback_redirect(row.redirect_uri),
        "scopes": offered,
        "write_requested": SCOPE_DOCS_WRITE in row.requested_scopes,
        "allow_write": org.allow_write_scopes and SCOPE_DOCS_WRITE in row.requested_scopes,
        "external_access": org.external_ai_enabled,
        "user_name": user.name,
    }


def submit_consent(session: Session, user: User, request_id: UUID, decision: str, scopes: list[str]) -> str:
    row, client = _pending(session, user, request_id)
    if decision == "deny":
        row.denied_at = utcnow()
        session.commit()
        return _callback(row.redirect_uri, error="access_denied", error_description="The request was denied.", state=row.state)
    if decision != "allow":
        raise ApiError(422, "INVALID_DECISION", "Choose allow or deny.")
    org = get_org_settings(session)
    if not org.external_ai_enabled:
        raise ApiError(403, "EXTERNAL_ACCESS_DISABLED", "External AI access is turned off.")
    chosen = _chosen_scopes(row.requested_scopes, scopes, allow_write=org.allow_write_scopes)
    grant = session.scalar(
        select(OAuthGrant).where(
            OAuthGrant.user_id == user.id,
            OAuthGrant.oauth_client_id == client.id,
            OAuthGrant.revoked_at.is_(None),
        )
    )
    if grant is None:
        grant = OAuthGrant(
            user_id=user.id,
            oauth_client_id=client.id,
            redirect_uri=row.redirect_uri,
            scopes=chosen,
        )
        session.add(grant)
        session.flush()
    else:
        grant.scopes = chosen
        grant.redirect_uri = row.redirect_uri
    raw = CODE_PREFIX + secrets.token_urlsafe(32)
    now = utcnow()
    row.grant_id = grant.id
    row.granted_scopes = chosen
    row.code_hash = hash_token(raw)
    row.expires_at = now + CODE_TTL
    session.commit()
    return _callback(row.redirect_uri, code=raw, state=row.state)


def exchange_token(session: Session, form: dict[str, str], authorization: str | None, ip: str | None) -> dict:
    grant_type = form.get("grant_type") or ""
    if grant_type == "authorization_code":
        return _exchange_code(session, form, authorization, ip)
    if grant_type == "refresh_token":
        return _exchange_refresh(session, form, authorization, ip)
    raise OAuthError("unsupported_grant_type", "Only authorization_code and refresh_token are supported.")


def revoke_presented_token(session: Session, form: dict[str, str], authorization: str | None, ip: str | None) -> None:
    client = _authenticate_client(session, form, authorization, ip)
    raw = form.get("token") or ""
    if not raw:
        return
    digest = hash_token(raw)
    token = session.scalar(select(OAuthToken).where(OAuthToken.token_hash == digest))
    if token is not None:
        if token.oauth_client_id != client.id:
            return
        if token.kind == "refresh":
            _revoke_grant(session, token.grant_id)
            return
        if token.revoked_at is None:
            token.revoked_at = utcnow()
            session.commit()
        return
    code = session.scalar(select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.code_hash == digest))
    if code is None or code.oauth_client_id != client.id:
        return
    if code.grant_id is not None:
        _revoke_grant(session, code.grant_id)
        return
    if code.used_at is None:
        code.used_at = utcnow()
        session.commit()


def list_grants(session: Session, user: User) -> list[dict]:
    rows = session.scalars(select(OAuthGrant).where(OAuthGrant.user_id == user.id).order_by(OAuthGrant.created_at.desc(), OAuthGrant.id.desc()))
    return _grant_rows(session, rows)


def list_all_grants(session: Session) -> list[dict]:
    rows = session.scalars(select(OAuthGrant).order_by(OAuthGrant.created_at.desc(), OAuthGrant.id.desc()))
    return _grant_rows(session, rows)


def revoke_any_grant(session: Session, grant_id: UUID) -> None:
    grant = session.get(OAuthGrant, grant_id)
    if grant is None:
        raise ApiError(404, "NOT_FOUND", "This connected app could not be found.")
    if grant.revoked_at is None:
        _revoke_grant(session, grant.id)


def _grant_rows(session: Session, rows) -> list[dict]:
    items = []
    for grant in rows:
        client = session.get(OAuthClient, grant.oauth_client_id)
        if client is None:
            continue
        items.append(_grant_payload(grant, client))
    return items


def revoke_grant_for_user(session: Session, user: User, grant_id: UUID) -> None:
    grant = session.get(OAuthGrant, grant_id)
    if grant is None or grant.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "This connected app could not be found.")
    if grant.revoked_at is None:
        _revoke_grant(session, grant.id)


def principal_for_credential(session: Session, raw: str, ip: str | None, *, path: str) -> Principal:
    if raw.startswith(TOKEN_PREFIX):
        from app.services.tokens import principal_for_token

        return principal_for_token(session, raw, ip)
    return principal_for_access_token(session, raw, ip, path=path)


def principal_for_access_token(session: Session, raw: str, ip: str | None, *, path: str) -> Principal:
    del ip
    if not raw.startswith(ACCESS_PREFIX):
        raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.")
    row = session.scalar(select(OAuthToken).where(OAuthToken.token_hash == hash_token(raw), OAuthToken.kind == "access"))
    now = utcnow()
    if row is None or row.revoked_at is not None:
        raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.")
    if row.expires_at <= now:
        raise ApiError(401, "TOKEN_EXPIRED", "This token has expired.")
    if not resource_matches(row.audience) or not path.startswith("/mcp"):
        raise ApiError(401, "INVALID_AUDIENCE", "This token was issued for a different resource.")
    grant = session.get(OAuthGrant, row.grant_id)
    if grant is None or grant.revoked_at is not None:
        raise ApiError(401, "TOKEN_REVOKED", "This token has been revoked.")
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise ApiError(401, "TOKEN_INACTIVE", "This token is no longer valid.")
    org = get_org_settings(session)
    scopes = _effective_scopes(user, set(row.scopes) & set(grant.scopes), org)
    if SCOPE_DOCS_READ not in scopes:
        raise ApiError(401, "TOKEN_INACTIVE", "This token is no longer valid.")
    client = session.get(OAuthClient, row.oauth_client_id)
    principal = Principal(
        user=user,
        auth_method=AuthMethod.oauth,
        scopes=frozenset(scopes),
        token_id=None,
        client_name=client.client_name if client is not None else None,
    )
    remember_actor(principal, oauth_client_id=row.oauth_client_id, rate_id=row.id)
    if not org.external_ai_enabled:
        raise ApiError(403, "EXTERNAL_ACCESS_DISABLED", "External AI access is turned off.")
    _touch_grant(session, grant, now)
    return principal


def clear_metadata_cache() -> None:
    _METADATA_CACHE.clear()


def cleanup_expired(session: Session) -> int:
    now = utcnow()
    codes = session.execute(delete(OAuthAuthorizationCode).where(OAuthAuthorizationCode.expires_at < now))
    tokens = session.execute(delete(OAuthToken).where(OAuthToken.expires_at < now))
    session.commit()
    return int(codes.rowcount or 0) + int(tokens.rowcount or 0)


def register_oauth_handlers() -> None:
    event_bus.subscribe(USER_ACCESS_CHANGED, revoke_oauth_for_deactivated_user)


def revoke_oauth_for_deactivated_user(payload: dict) -> None:
    changes = payload.get("changes") or {}
    active = changes.get("is_active")
    if not isinstance(active, dict) or active.get("to") is not False:
        return
    user_id = payload.get("user_id")
    if not user_id:
        return
    from app.core.database import current_request_session
    from app.core.sessions import open_session

    target = UUID(str(user_id))
    bound = current_request_session()
    if bound is not None:
        _revoke_user_grants(bound, target)
        return
    with open_session() as session:
        _revoke_user_grants(session, target)


def start_oauth_cleanup() -> None:
    global _cleanup_started
    settings = get_settings()
    if _cleanup_started or not settings.oauth_cleanup_enabled or settings.app_env == "test":
        return
    _cleanup_started = True
    _stop.clear()
    Thread(target=_cleanup_loop, name="oauth-cleanup", daemon=True).start()


def stop_oauth_cleanup() -> None:
    _stop.set()


def fetch_metadata_document(url: str) -> tuple[dict, int]:
    """GET a Client ID Metadata Document. Tests replace this."""
    _assert_public_metadata_url(url)
    try:
        response = requests.get(
            url,
            timeout=5,
            allow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": "Atlas-OAuth"},
        )
    except requests.RequestException as exc:
        raise OAuthError("invalid_client", "The client metadata document could not be fetched.", 401) from exc
    if response.status_code != 200 or len(response.content) > 65536:
        raise OAuthError("invalid_client", "The client metadata document could not be fetched.", 401)
    try:
        document = response.json()
    except ValueError as exc:
        raise OAuthError("invalid_client", "The client metadata document is not JSON.", 401) from exc
    if not isinstance(document, dict):
        raise OAuthError("invalid_client", "The client metadata document is not JSON.", 401)
    return document, _cache_seconds(response.headers.get("Cache-Control"))


def redirect_allowed(uri: str) -> bool:
    if not uri or len(uri) > 500 or any(ord(char) < 32 for char in uri):
        return False
    parts = urlsplit(uri)
    if parts.username or parts.password or parts.fragment or not parts.hostname:
        return False
    host = parts.hostname.lower()
    if parts.scheme == "https":
        return True
    return parts.scheme == "http" and host in _LOOPBACK


def redirect_matches(requested: str, registered: str) -> bool:
    """Exact match. Loopback URIs ignore the port, per RFC 8252 and Claude Code."""
    if requested == registered:
        return True
    left, right = urlsplit(requested), urlsplit(registered)
    host = (left.hostname or "").lower()
    other = (right.hostname or "").lower()
    if host not in _LOOPBACK or host != other:
        return False
    return left.scheme == right.scheme and left.path == right.path and left.query == right.query


def client_verified(client: OAuthClient, redirect_uri: str) -> bool:
    """Dynamic clients are unverified. Metadata clients are verified only on their own https host."""
    if client.registration_kind != "metadata":
        return False
    source = urlsplit(client.client_id)
    target = urlsplit(redirect_uri)
    return (
        source.scheme == "https"
        and target.scheme == "https"
        and bool(source.hostname)
        and source.hostname.lower() == (target.hostname or "").lower()
    )


def redirect_domain(uri: str) -> str:
    return (urlsplit(uri).hostname or "").lower()


def is_loopback_redirect(uri: str) -> bool:
    return (urlsplit(uri).hostname or "").lower() in _LOOPBACK


def _exchange_code(session: Session, form: dict[str, str], authorization: str | None, ip: str | None) -> dict:
    raw = form.get("code") or ""
    if not raw:
        raise OAuthError("invalid_request", "code is required.")
    client = _authenticate_client(session, form, authorization, ip)
    row = session.scalar(select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.code_hash == hash_token(raw)))
    if row is None or row.oauth_client_id != client.id or row.denied_at is not None:
        raise OAuthError("invalid_grant", "The authorization code is not valid.")
    if row.used_at is not None:
        if row.grant_id is not None:
            _revoke_grant(session, row.grant_id)
        raise OAuthError("invalid_grant", "The authorization code is not valid.")
    if row.expires_at <= utcnow():
        raise OAuthError("invalid_grant", "The authorization code has expired.")
    if form.get("redirect_uri") != row.redirect_uri:
        raise OAuthError("invalid_grant", "redirect_uri does not match the authorization request.")
    resource = form.get("resource") or ""
    if not resource_matches(resource) or not resource_matches(row.resource):
        raise OAuthError("invalid_target", "resource does not match this MCP server.")
    if not _pkce_ok(form.get("code_verifier") or "", row.code_challenge):
        raise OAuthError("invalid_grant", "code_verifier does not match the code challenge.")
    _reject_when_external_access_is_off(session)
    now = utcnow()
    consumed = session.execute(
        update(OAuthAuthorizationCode)
        .where(OAuthAuthorizationCode.id == row.id, OAuthAuthorizationCode.used_at.is_(None))
        .values(used_at=now)
        .returning(OAuthAuthorizationCode.id)
    )
    if consumed.first() is None:
        if row.grant_id is not None:
            _revoke_grant(session, row.grant_id)
        raise OAuthError("invalid_grant", "The authorization code is not valid.")
    return _issue_from_grant(session, client, row.grant_id, resource)


def _exchange_refresh(session: Session, form: dict[str, str], authorization: str | None, ip: str | None) -> dict:
    raw = form.get("refresh_token") or ""
    if not raw:
        raise OAuthError("invalid_request", "refresh_token is required.")
    client = _authenticate_client(session, form, authorization, ip)
    resource = form.get("resource") or ""
    if not resource_matches(resource):
        raise OAuthError("invalid_target", "resource does not match this MCP server.")
    _reject_when_external_access_is_off(session)
    row = session.scalar(select(OAuthToken).where(OAuthToken.token_hash == hash_token(raw)))
    if row is None or row.oauth_client_id != client.id or row.kind != "refresh" or not resource_matches(row.audience):
        raise OAuthError("invalid_grant", "The refresh token is not valid.")
    if row.replaced_at is not None:
        _revoke_grant(session, row.grant_id)
        raise OAuthError("invalid_grant", "The refresh token is not valid.")
    if row.revoked_at is not None or row.expires_at <= utcnow():
        raise OAuthError("invalid_grant", "The refresh token is not valid.")
    now = utcnow()
    rotated = session.execute(
        update(OAuthToken)
        .where(OAuthToken.id == row.id, OAuthToken.replaced_at.is_(None), OAuthToken.revoked_at.is_(None))
        .values(replaced_at=now, revoked_at=now)
        .returning(OAuthToken.id)
    )
    if rotated.first() is None:
        _revoke_grant(session, row.grant_id)
        raise OAuthError("invalid_grant", "The refresh token is not valid.")
    return _issue_from_grant(session, client, row.grant_id, resource)


def _issue_from_grant(session: Session, client: OAuthClient, grant_id: UUID | None, resource: str) -> dict:
    grant = session.get(OAuthGrant, grant_id) if grant_id is not None else None
    if grant is None or grant.revoked_at is not None or grant.oauth_client_id != client.id:
        raise OAuthError("invalid_grant", "The grant is no longer valid.")
    user = session.get(User, grant.user_id)
    if user is None or not user.is_active:
        raise OAuthError("invalid_grant", "The grant is no longer valid.")
    org = get_org_settings(session)
    if not org.external_ai_enabled:
        raise OAuthError("access_denied", "External AI access is turned off.", 400)
    scopes = _effective_scopes(user, set(grant.scopes), org)
    if SCOPE_DOCS_READ not in scopes:
        raise OAuthError("invalid_grant", "The grant is no longer valid.")
    audience = canonical_resource(resource) or mcp_resource()
    access = ACCESS_PREFIX + secrets.token_urlsafe(32)
    refresh = REFRESH_PREFIX + secrets.token_urlsafe(32)
    now = utcnow()
    session.add(
        OAuthToken(
            grant_id=grant.id,
            oauth_client_id=client.id,
            user_id=user.id,
            kind="access",
            token_hash=hash_token(access),
            audience=audience,
            scopes=scopes,
            expires_at=now + ACCESS_TTL,
        )
    )
    session.add(
        OAuthToken(
            grant_id=grant.id,
            oauth_client_id=client.id,
            user_id=user.id,
            kind="refresh",
            token_hash=hash_token(refresh),
            audience=audience,
            scopes=scopes,
            expires_at=now + REFRESH_TTL,
        )
    )
    session.commit()
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TTL.total_seconds()),
        "refresh_token": refresh,
        "scope": " ".join(scopes),
    }


def _authenticate_client(session: Session, form: dict[str, str], authorization: str | None, ip: str | None) -> OAuthClient:
    basic = _parse_basic(authorization)
    posted_id = form.get("client_id")
    posted_secret = form.get("client_secret")
    if basic and (posted_id or posted_secret):
        raise OAuthError("invalid_request", "Send client credentials once.")
    if basic:
        client_id, secret = basic
    else:
        client_id, secret = posted_id or "", posted_secret
    if not client_id:
        raise OAuthError("invalid_client", "client_id is required.", 401, {"WWW-Authenticate": 'Basic realm="atlas"'})
    client = _client_for_token(session, client_id, ip)
    if client.token_endpoint_auth_method == "none":
        if secret:
            raise OAuthError("invalid_client", "This client does not use a secret.", 401, {"WWW-Authenticate": 'Basic realm="atlas"'})
        return client
    digest = hash_token(secret or "")
    stored = client.client_secret_hash or ""
    if not secret or len(digest) != len(stored) or not hmac.compare_digest(digest, stored):
        raise OAuthError("invalid_client", "Client authentication failed.", 401, {"WWW-Authenticate": 'Basic realm="atlas"'})
    return client


def _client_for_authorize(session: Session, client_id: str, ip: str | None) -> OAuthClient:
    if client_id.startswith("https://"):
        return _upsert_metadata_client(session, client_id, _cached_metadata(client_id, ip), ip)
    row = session.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id, OAuthClient.registration_kind == "dynamic"))
    if row is None:
        raise OAuthError("invalid_client", "Unknown client.", 401)
    return row


def _client_for_token(session: Session, client_id: str, ip: str | None) -> OAuthClient:
    row = session.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if row is not None:
        return row
    if client_id.startswith("https://"):
        return _upsert_metadata_client(session, client_id, _cached_metadata(client_id, ip), ip)
    raise OAuthError("invalid_client", "Unknown client.", 401, {"WWW-Authenticate": 'Basic realm="atlas"'})


def _cached_metadata(url: str, ip: str | None) -> dict:
    now = time.monotonic()
    cached = _METADATA_CACHE.get(url)
    if cached is not None and cached[0] > now:
        return cached[1]
    _consume_registration(ip)
    document, ttl = fetch_metadata_document(url)
    _validate_metadata(url, document)
    _METADATA_CACHE[url] = (now + ttl, document)
    return document


def _validate_metadata(url: str, document: dict) -> None:
    if document.get("client_id") != url:
        raise OAuthError("invalid_client", "client_id does not match the metadata document URL.", 401)
    name = document.get("client_name")
    if not isinstance(name, str) or not name.strip():
        raise OAuthError("invalid_client", "The metadata document needs a client_name.", 401)
    redirects = document.get("redirect_uris")
    if not isinstance(redirects, list) or not redirects or not all(isinstance(item, str) and redirect_allowed(item) for item in redirects):
        raise OAuthError("invalid_client", "The metadata document needs usable redirect_uris.", 401)
    grants = document.get("grant_types")
    if grants is not None and (not isinstance(grants, list) or any(item not in _GRANT_TYPES for item in grants)):
        raise OAuthError("invalid_client", "The metadata document requests an unsupported grant.", 401)
    responses = document.get("response_types")
    if responses is not None and responses != ["code"]:
        raise OAuthError("invalid_client", "Only the code response type is supported.", 401)
    if document.get("token_endpoint_auth_method", "none") != "none":
        raise OAuthError("invalid_client", "Client metadata documents must authenticate with method none.", 401)


def _upsert_metadata_client(session: Session, url: str, document: dict, ip: str | None) -> OAuthClient:
    name = str(document["client_name"]).strip()[:120]
    redirects = [str(item) for item in document["redirect_uris"]]
    row = session.scalar(select(OAuthClient).where(OAuthClient.client_id == url))
    if row is None:
        row = OAuthClient(
            client_id=url,
            client_name=name,
            redirect_uris=redirects,
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="none",
            registration_kind="metadata",
            source_ip=(ip or None),
        )
        session.add(row)
    else:
        row.client_name = name
        row.redirect_uris = redirects
        row.registration_kind = "metadata"
    session.flush()
    return row


def _pending(session: Session, user: User, request_id: UUID) -> tuple[OAuthAuthorizationCode, OAuthClient]:
    row = session.get(OAuthAuthorizationCode, request_id)
    if row is None or row.user_id != user.id or row.code_hash is not None or row.denied_at is not None:
        raise ApiError(404, "NOT_FOUND", "This authorization request could not be found.")
    if row.expires_at <= utcnow():
        raise ApiError(400, "REQUEST_EXPIRED", "This authorization request has expired.")
    client = session.get(OAuthClient, row.oauth_client_id)
    if client is None:
        raise ApiError(404, "NOT_FOUND", "This authorization request could not be found.")
    return row, client


def _parse_scope(scope_text: str | None) -> list[str]:
    raw = (scope_text if scope_text is not None else SCOPE_DOCS_READ).split()
    if not raw:
        raw = [SCOPE_DOCS_READ]
    if any(item not in SCOPE_VOCABULARY for item in raw):
        raise OAuthError("invalid_scope", "Scopes are limited to docs:read and docs:write.")
    ordered: list[str] = []
    for item in raw:
        if item not in ordered:
            ordered.append(item)
    return ordered


def _ceiling_for(user: User, asked: list[str]) -> list[str]:
    role = set(scopes_for_role(user.role))
    ceiling = [item for item in asked if item in role]
    if SCOPE_DOCS_WRITE in ceiling and SCOPE_DOCS_READ not in ceiling and SCOPE_DOCS_READ in role:
        ceiling.append(SCOPE_DOCS_READ)
    if SCOPE_DOCS_READ not in ceiling:
        raise OAuthError("invalid_scope", "This account cannot grant the requested scopes.")
    return ceiling


def _offered(ceiling: list[str], *, allow_write: bool) -> list[str]:
    scopes = list(ceiling)
    if not allow_write:
        scopes = [item for item in scopes if item != SCOPE_DOCS_WRITE]
    return scopes


def _chosen_scopes(ceiling: list[str], requested: list[str], *, allow_write: bool) -> list[str]:
    if any(item not in SCOPE_VOCABULARY for item in requested):
        raise ApiError(422, "UNKNOWN_SCOPE", "Scopes are limited to docs:read and docs:write.")
    chosen = set(requested)
    if not chosen <= set(ceiling):
        raise ApiError(422, "SCOPE_UPGRADE", "You can only remove scopes from this request.")
    if not allow_write:
        chosen.discard(SCOPE_DOCS_WRITE)
    if SCOPE_DOCS_WRITE in chosen:
        chosen.add(SCOPE_DOCS_READ)
    if SCOPE_DOCS_READ not in chosen:
        raise ApiError(422, "SCOPE_REQUIRED", "docs:read is required.")
    return sorted(chosen)


def _effective_scopes(user: User, scopes: set[str], org) -> list[str]:
    granted = set(scopes) & set(scopes_for_role(user.role)) & set(SCOPE_VOCABULARY)
    if not org.allow_write_scopes:
        granted.discard(SCOPE_DOCS_WRITE)
    if SCOPE_DOCS_WRITE in granted:
        granted.add(SCOPE_DOCS_READ)
    return sorted(granted)


def _revoke_grant(session: Session, grant_id: UUID) -> None:
    grant = session.get(OAuthGrant, grant_id)
    if grant is None:
        return
    now = utcnow()
    if grant.revoked_at is None:
        grant.revoked_at = now
    tokens = session.scalars(select(OAuthToken).where(OAuthToken.grant_id == grant.id, OAuthToken.revoked_at.is_(None)))
    for token in tokens:
        token.revoked_at = now
    session.commit()


def _revoke_user_grants(session: Session, user_id: UUID) -> None:
    grant_ids = list(
        session.scalars(select(OAuthGrant.id).where(OAuthGrant.user_id == user_id, OAuthGrant.revoked_at.is_(None)))
    )
    for grant_id in grant_ids:
        _revoke_grant(session, grant_id)


def _touch_grant(session: Session, grant: OAuthGrant, now) -> None:
    seen = grant.last_used_at
    if seen is not None and now - seen < LAST_USED_INTERVAL:
        return
    grant.last_used_at = now
    session.commit()


def _grant_payload(grant: OAuthGrant, client: OAuthClient) -> dict:
    return {
        "id": grant.id,
        "user_id": grant.user_id,
        "client_name": client.client_name,
        "client_id": client.client_id,
        "redirect_domain": redirect_domain(grant.redirect_uri),
        "verified": client_verified(client, grant.redirect_uri),
        "scopes": list(grant.scopes),
        "created_at": grant.created_at,
        "last_used_at": grant.last_used_at,
        "revoked_at": grant.revoked_at,
    }


def _pkce_ok(verifier: str, challenge: str) -> bool:
    if not _VERIFIER.fullmatch(verifier):
        return False
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    computed = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    presented = challenge.replace("=", "")
    if len(computed) != len(presented):
        return False
    return hmac.compare_digest(computed, presented)


def _parse_basic(header: str | None) -> tuple[str, str] | None:
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "basic":
        return None
    try:
        decoded = b64decode(value.strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise OAuthError("invalid_client", "Client authentication failed.", 401, {"WWW-Authenticate": 'Basic realm="atlas"'}) from exc
    client_id, separator, secret = decoded.partition(":")
    if not separator:
        raise OAuthError("invalid_client", "Client authentication failed.", 401, {"WWW-Authenticate": 'Basic realm="atlas"'})
    return unquote(client_id), unquote(secret)


def _callback(redirect_uri: str, **params: str | None) -> str:
    parts = urlsplit(redirect_uri)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in params.items():
        if value is not None:
            query[key] = value
    query["iss"] = issuer()
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def _redirect_error(redirect_uri: str, error: str, description: str, state: str | None) -> AuthorizeDecision:
    return AuthorizeDecision(location=_callback(redirect_uri, error=error, error_description=description, state=state))


def _login_location(return_url: str) -> str:
    return f"{get_settings().public_app_url.rstrip('/')}/login?next={quote(return_url, safe='')}"


def _consent_location(request_id: UUID) -> str:
    return f"{get_settings().public_app_url.rstrip('/')}/oauth/consent?request={request_id}"


def _consume_registration(ip: str | None) -> None:
    settings = get_settings()
    retry = oauth_register_limiter.consume(
        f"register:{(ip or 'unknown')[:64]}",
        limit=settings.oauth_register_rate_limit,
        window_seconds=settings.oauth_register_window_seconds,
    )
    if retry is None:
        return
    raise OAuthError(
        "rate_limited",
        "Too many registration requests. Try again shortly.",
        429,
        {"Retry-After": str(retry)},
    )


def _assert_public_metadata_url(url: str) -> None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    if (
        parts.scheme != "https"
        or parts.username
        or parts.password
        or parts.fragment
        or not host
        or parts.path in {"", "/"}
        or host in _LOOPBACK
        or host.endswith(".localhost")
        or host.endswith(".local")
        or host.endswith(".internal")
    ):
        raise OAuthError("invalid_client", "client_id must be an https URL with a path.", 401)
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise OAuthError("invalid_client", "That client metadata URL is not allowed.", 401)
        return
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise OAuthError("invalid_client", "The client metadata host could not be resolved.", 401) from exc
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not addresses or any(not address.is_global for address in addresses):
        raise OAuthError("invalid_client", "That client metadata URL is not allowed.", 401)


def _cache_seconds(header: str | None) -> int:
    if not header:
        return 300
    for part in header.split(","):
        item = part.strip().lower()
        if item in {"no-store", "no-cache"}:
            return 60
        if item.startswith("max-age="):
            try:
                return min(3600, max(60, int(item.split("=", 1)[1])))
            except ValueError:
                return 300
    return 300


def _cleanup_loop() -> None:
    from app.core.database import SessionLocal

    while not _stop.is_set():
        session = SessionLocal()
        try:
            cleanup_expired(session)
        except Exception:
            session.rollback()
        finally:
            session.close()
        if _stop.wait(3600):
            return
