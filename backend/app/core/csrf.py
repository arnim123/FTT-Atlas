"""Reject cookie-authenticated mutations that did not come from our own scripts.

A browser will attach the session cookie to a cross-site request, but it will not
attach a custom header without a CORS preflight. Bearer calls have no cookie, so
they skip this check even when they use a mutating method.
"""

from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import error_detail

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CSRFMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"].upper() in MUTATING_METHODS:
            cookie_name = get_settings().session_cookie_name
            # A bearer credential is not attached by the browser on its own, so it is not a CSRF vector.
            bearer = _header(scope, "authorization").lower().startswith("bearer ")
            # /oauth/* authenticates the client. The session cookie may ride along
            # after login, and the consent API under /api/v1/oauth stays protected.
            protocol = (scope.get("path") or "").startswith("/oauth/")
            if _cookie_present(scope, cookie_name) and not bearer and not protocol and not _header(scope, "x-requested-with"):
                response = JSONResponse(
                    status_code=403,
                    content={"detail": error_detail("CSRF_REQUIRED", "This request needs an X-Requested-With header.")},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _header(scope, name: str) -> str:
    target = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []):
        if key.lower() == target:
            return value.decode("latin-1").strip()
    return ""


def _cookie_present(scope, name: str) -> bool:
    for key, value in scope.get("headers", []):
        if key.lower() != b"cookie":
            continue
        for part in value.decode("latin-1").split(";"):
            if "=" not in part:
                continue
            cookie_name, cookie_value = part.split("=", 1)
            if cookie_name.strip() == name and cookie_value.strip():
                return True
    return False
