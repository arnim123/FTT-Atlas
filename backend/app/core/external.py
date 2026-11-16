"""What a non-session credential is allowed to call.

Tokens, OAuth, and MCP use an allowlist. Anything not listed here is rejected,
including user administration, organization settings, token management,
permission changes, permanent delete, and taxonomy edits.
"""

import re

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.principal import Principal
from app.core.rate_limit import token_limiter

_UUID = r"[0-9a-fA-F-]{36}"
_TOKEN = r"[A-Za-z0-9_-]{20,}"

# (method, path). MCP and the protected-resource metadata document are included
# so a bearer call that reaches get_principal is not rejected before the MCP app.
_ALLOWED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GET", re.compile(r"^/api/v1/agent/me$")),
    ("GET", re.compile(r"^/api/v1/agent/taxonomy$")),
    ("GET", re.compile(r"^/api/v1/agent/search$")),
    ("GET", re.compile(r"^/api/v1/agent/folders$")),
    ("POST", re.compile(r"^/api/v1/agent/folders$")),
    ("GET", re.compile(rf"^/api/v1/agent/documents/{_UUID}$")),
    ("GET", re.compile(rf"^/api/v1/agent/documents/{_UUID}/content$")),
    ("GET", re.compile(rf"^/api/v1/agent/documents/{_UUID}/related$")),
    ("GET", re.compile(rf"^/api/v1/agent/documents/{_UUID}/download-link$")),
    ("GET", re.compile(rf"^/api/v1/agent/downloads/{_TOKEN}$")),
    ("POST", re.compile(r"^/api/v1/agent/documents/google/create$")),
    ("POST", re.compile(r"^/api/v1/agent/documents/google/link$")),
    ("PATCH", re.compile(rf"^/api/v1/agent/documents/{_UUID}$")),
    ("POST", re.compile(rf"^/api/v1/agent/documents/{_UUID}/move$")),
    ("POST", re.compile(rf"^/api/v1/agent/documents/{_UUID}/archive$")),
    ("GET", re.compile(r"^/api/v1/agent/openapi.json$")),
    ("POST", re.compile(r"^/mcp/?$")),
    ("GET", re.compile(r"^/mcp/?$")),
    ("DELETE", re.compile(r"^/mcp/?$")),
    ("GET", re.compile(r"^/\.well-known/oauth-protected-resource/mcp/?$")),
    ("GET", re.compile(r"^/\.well-known/oauth-protected-resource/?$")),
)

_WRITE_TOOLS = frozenset(
    {
        "create_folder",
        "create_google_doc",
        "link_google_doc",
        "update_document_metadata",
        "move_document",
        "archive_document",
    }
)


def route_allowed(method: str, path: str) -> bool:
    verb = method.upper()
    return any(verb == allowed and pattern.fullmatch(path) for allowed, pattern in _ALLOWED)


def rate_kind_for_http(method: str) -> str:
    if method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return "read"
    return "write"


def rate_kind_for_mcp(mcp_method: str, mcp_name: str) -> str:
    """Write tools spend the write budget. A tools/call with no name does too."""
    if mcp_method == "tools/call" and (not mcp_name or mcp_name in _WRITE_TOOLS):
        return "write"
    return "read"


def consume_token_rate(token_id: object, kind: str) -> None:
    settings = get_settings()
    limit = settings.token_write_rate_limit if kind == "write" else settings.token_read_rate_limit
    retry = token_limiter.consume(
        f"{token_id}:{kind}",
        limit=limit,
        window_seconds=settings.token_rate_window_seconds,
    )
    if retry is None:
        return
    raise ApiError(
        429,
        "RATE_LIMITED",
        "Too many requests for this token. Wait and try again.",
        headers={"Retry-After": str(retry)},
    )


def enforce_external_http(request: Request, principal: Principal) -> None:
    """Reject non-session calls that are outside the agent allowlist, then meter them."""
    if not route_allowed(request.method, request.url.path):
        raise ApiError(403, "EXTERNAL_ROUTE_FORBIDDEN", "This credential cannot call that endpoint.")
    if principal.token_id is None:
        return
    if request.url.path.startswith("/mcp"):
        return
    consume_token_rate(principal.token_id, rate_kind_for_http(request.method))
