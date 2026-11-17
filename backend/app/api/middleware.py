"""HTTPS, the external-AI kill switch, token rate limits, and audit rows.

The audit row is written for every bearer call. It records the route or MCP tool
name and never the document text.
"""

import mimetypes
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from starlette.responses import FileResponse, JSONResponse, Response

from app.core.config import get_settings
from app.core.enums import AuditChannel
from app.core.errors import ApiError, error_detail
from app.core.external import consume_token_rate, rate_kind_for_mcp
from app.core.sessions import open_session
from app.services.audit import (
    bind_audit_scope,
    current_actor,
    push_actor,
    reset_actor,
    reset_audit_scope,
    summarize_query,
    write_audit,
)
from app.services.oauth import principal_for_credential

_EXTERNAL_PREFIXES = (
    "/mcp",
    "/api/v1/agent",
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-authorization-server",
    "/oauth",
)


class ExternalGateMiddleware:
    """MCP-only checks that have to happen before the protocol handler.

    REST checks live in get_principal. Invalid MCP tokens fall through so the
    SDK can answer 401 with the protected-resource metadata URL.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if path.startswith(_EXTERNAL_PREFIXES) and _production_http(scope):
            await _send_error(scope, receive, send, 403, "HTTPS_REQUIRED", "External access requires HTTPS.")
            return
        if path.startswith("/mcp"):
            blocked = await _mcp_admission(scope, receive, send)
            if blocked:
                return
        await self.app(scope, receive, send)


class AuditMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        marker = push_actor()
        scope_marker = bind_audit_scope(scope)
        status = 500
        started = time.perf_counter()

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            actor = scope.get("external_actor") or current_actor()
            reset_actor(marker)
            reset_audit_scope(scope_marker)
            if actor is not None:
                _record(scope, actor, status, started)


async def _mcp_admission(scope, receive, send) -> bool:
    path = scope.get("path") or ""
    header = _header(scope, "authorization")
    if not header.lower().startswith("bearer "):
        return False
    raw = header[7:].strip()
    if not raw:
        return False
    try:
        with open_session() as session:
            principal = principal_for_credential(session, raw, _ip(scope), path=path)
    except ApiError as exc:
        code, message = _error_parts(exc)
        if code == "EXTERNAL_ACCESS_DISABLED":
            await _send_error(scope, receive, send, 403, code, message)
            return True
        return False
    try:
        kind = rate_kind_for_mcp(_header(scope, "mcp-method"), _header(scope, "mcp-name"))
        rate_id = (current_actor() or {}).get("rate_id") or principal.token_id
        if rate_id is not None:
            consume_token_rate(rate_id, kind)
    except ApiError as exc:
        code, message = _error_parts(exc)
        retry = "1"
        if exc.headers and exc.headers.get("Retry-After"):
            retry = exc.headers["Retry-After"]
        await _send_error(scope, receive, send, exc.status_code, code, message, headers={"Retry-After": retry})
        return True
    return False


def _record(scope, actor, status: int, started: float) -> None:
    path = scope.get("path") or ""
    method = scope.get("method") or ""
    if path.startswith("/mcp"):
        channel = AuditChannel.mcp
        operation = _header(scope, "mcp-name") or _header(scope, "mcp-method") or "mcp"
    else:
        channel = AuditChannel.rest
        operation = f"{method} {path}"
    query = parse_qs((scope.get("query_string") or b"").decode("latin-1"), keep_blank_values=False)
    flat = {key: values[-1] for key, values in query.items() if values}
    summary = {"method": method, "path": path, "query": summarize_query(flat)}
    mcp_method = _header(scope, "mcp-method")
    mcp_name = _header(scope, "mcp-name")
    if mcp_method:
        summary["mcp_method"] = mcp_method
    if mcp_name:
        summary["mcp_name"] = mcp_name
    duration_ms = int((time.perf_counter() - started) * 1000)
    with open_session() as session:
        write_audit(
            session,
            token_id=actor.get("token_id"),
            oauth_client_id=actor.get("oauth_client_id"),
            user_id=actor["user_id"],
            channel=channel,
            operation=operation,
            status_code=status,
            duration_ms=duration_ms,
            ip=_ip(scope),
            user_agent=_header(scope, "user-agent") or None,
            request_summary=summary,
        )


class OAuthCorsMiddleware:
    """Lock the API to the frontend origin. Public OAuth protocol routes stay open."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        policy = _cors_policy(scope, path)
        no_store = _no_store(path)
        if policy is None and not no_store:
            await self.app(scope, receive, send)
            return
        if scope.get("method") == "OPTIONS" and policy is not None:
            from starlette.responses import Response

            await Response(status_code=204, headers=policy)(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                present = {key.lower() for key, _ in headers}
                extra: dict[str, str] = {}
                if policy is not None:
                    extra.update(policy)
                if no_store and b"cache-control" not in present:
                    extra["Cache-Control"] = "no-store"
                    extra["Pragma"] = "no-cache"
                for key, value in extra.items():
                    encoded = key.lower().encode("latin-1")
                    if encoded not in present:
                        headers.append((encoded, value.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _cors_policy(scope, path: str) -> dict[str, str] | None:
    if path.startswith("/oauth") or path.startswith("/.well-known/oauth-"):
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, MCP-Protocol-Version",
            "Access-Control-Max-Age": "600",
        }
    if not path.startswith("/api/"):
        return None
    origin = _header(scope, "origin").rstrip("/")
    allowed = _frontend_origins()
    if origin and origin not in allowed:
        return None
    chosen = origin or get_settings().public_app_url.rstrip("/")
    return {
        "Access-Control-Allow-Origin": chosen,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Requested-With",
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }


def _frontend_origins() -> set[str]:
    settings = get_settings()
    configured = settings.public_app_url.rstrip("/")
    allowed = {configured, settings.public_base_url.rstrip("/")}
    if settings.app_env == "production":
        return allowed
    parsed = urlparse(configured)
    if not parsed.scheme or not parsed.hostname:
        return allowed
    port = parsed.port
    for host in ("localhost", "127.0.0.1"):
        if port:
            allowed.add(f"{parsed.scheme}://{host}:{port}")
        else:
            allowed.add(f"{parsed.scheme}://{host}")
    return allowed


def _no_store(path: str) -> bool:
    return (
        path.startswith("/api/v1/tokens")
        or path.startswith("/api/v1/admin/tokens")
        or path.startswith("/api/v1/oauth")
        or path.startswith("/oauth/")
    )


def _production_http(scope) -> bool:
    if get_settings().app_env != "production":
        return False
    forwarded = _header(scope, "x-forwarded-proto").split(",")[0].strip().lower()
    scheme = forwarded or str(scope.get("scheme") or "")
    return scheme != "https"


def _header(scope, name: str) -> str:
    target = name.lower().encode("latin-1")
    for key, value in scope.get("headers") or ():
        if key.lower() == target:
            return value.decode("latin-1").strip()
    return ""


def _ip(scope) -> str | None:
    forwarded = _header(scope, "x-forwarded-for")
    if forwarded:
        hop = forwarded.split(",")[0].strip()
        return hop[:64] or None
    client = scope.get("client")
    if client and client[0]:
        return str(client[0])[:64]
    return None


def _error_parts(exc: ApiError) -> tuple[str, str]:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return str(detail.get("code") or "ERROR"), str(detail.get("message") or "Request failed.")


_APP_PREFIXES = ("/api", "/mcp", "/oauth", "/.well-known", "/docs", "/redoc", "/openapi.json")


class FrontendMiddleware:
    """Serve the built web app on the public address. API and MCP paths stay on the backend."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not _serve_frontend(scope.get("path") or ""):
            await self.app(scope, receive, send)
            return
        await _frontend_file(scope, receive, send)


def _serve_frontend(path: str) -> bool:
    if not get_settings().frontend_dist.strip():
        return False
    return not path.startswith(_APP_PREFIXES)


def _frontend_file(scope, receive, send):
    root = Path(get_settings().frontend_dist).resolve()
    relative = (scope.get("path") or "/").lstrip("/")
    target = (root / relative).resolve() if relative else root / "index.html"
    if root not in target.parents and target != root:
        return Response(status_code=404)(scope, receive, send)
    if target.is_file():
        media = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return FileResponse(target, media_type=media)(scope, receive, send)
    if "." in Path(relative).name:
        return Response(status_code=404)(scope, receive, send)
    index = root / "index.html"
    if not index.is_file():
        return Response(status_code=404)(scope, receive, send)
    return FileResponse(index, media_type="text/html", headers={"Cache-Control": "no-cache"})(scope, receive, send)


async def _send_error(scope, receive, send, status: int, code: str, message: str, headers: dict[str, str] | None = None) -> None:
    response = JSONResponse(status_code=status, content={"detail": error_detail(code, message)}, headers=headers)
    await response(scope, receive, send)
