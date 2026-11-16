"""OAuth 2.1 authorization server and the signed-in consent API.

Public routes speak the OAuth error shape. The consent and grant routes use the
same {code, message} errors as the rest of the API and require the session cookie.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.principal import Principal, SessionCookieAuthenticator, get_principal, require_roles
from app.schemas.oauth import ConsentResult, ConsentSubmit, ConsentView, OAuthGrantPage, OAuthGrantRead
from app.services.oauth import (
    AuthorizeDecision,
    OAuthError,
    authorization_server_metadata,
    begin_authorization,
    consent_view,
    exchange_token,
    issuer,
    list_all_grants,
    list_grants,
    protected_resource_metadata,
    register_client,
    revoke_any_grant,
    revoke_grant_for_user,
    revoke_presented_token,
    submit_consent,
)

public_router = APIRouter()
router = APIRouter()
admin_router = APIRouter()

ADMINS = Depends(require_roles(UserRole.super_admin, UserRole.admin))

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


@public_router.get("/.well-known/oauth-protected-resource", response_model=None, include_in_schema=False)
@public_router.get("/.well-known/oauth-protected-resource/mcp", response_model=None, include_in_schema=False)
def protected_resource() -> JSONResponse:
    return JSONResponse(protected_resource_metadata(), headers={"Cache-Control": "public, max-age=300"})


@public_router.get("/.well-known/oauth-authorization-server", response_model=None, include_in_schema=False)
def authorization_server() -> JSONResponse:
    return JSONResponse(authorization_server_metadata(), headers={"Cache-Control": "public, max-age=300"})


@public_router.api_route("/oauth/authorize", methods=["GET", "POST"], response_model=None, include_in_schema=False)
async def authorize(request: Request, session: Session = Depends(get_db)) -> RedirectResponse | JSONResponse:
    params = {key: value for key, value in request.query_params.items()}
    if request.method == "POST":
        form = await request.form()
        for key, value in form.items():
            if isinstance(value, str):
                params.setdefault(key, value)
    user = SessionCookieAuthenticator().authenticate(request, session)
    decision = begin_authorization(
        session,
        user.user if user is not None else None,
        params,
        _return_url(request),
        _ip(request),
    )
    return _authorization_response(decision)


@public_router.post("/oauth/token", response_model=None, include_in_schema=False)
async def token(request: Request, session: Session = Depends(get_db)) -> JSONResponse:
    try:
        body = exchange_token(session, await _form(request), request.headers.get("authorization"), _ip(request))
    except OAuthError as exc:
        return _oauth_error(exc)
    return JSONResponse(body, headers=_NO_STORE)


@public_router.post("/oauth/register", response_model=None, include_in_schema=False)
async def register(request: Request, session: Session = Depends(get_db)) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception as exc:
        return _oauth_error(OAuthError("invalid_client_metadata", "Registration requires a JSON object."))
    if not isinstance(payload, dict):
        return _oauth_error(OAuthError("invalid_client_metadata", "Registration requires a JSON object."))
    try:
        body, status = register_client(session, payload, _ip(request))
    except OAuthError as exc:
        return _oauth_error(exc)
    return JSONResponse(body, status_code=status, headers=_NO_STORE)


@public_router.post("/oauth/revoke", response_model=None, include_in_schema=False)
async def revoke(request: Request, session: Session = Depends(get_db)) -> JSONResponse:
    try:
        revoke_presented_token(session, await _form(request), request.headers.get("authorization"), _ip(request))
    except OAuthError as exc:
        return _oauth_error(exc)
    return JSONResponse({}, headers=_NO_STORE)


@router.get("/consent-request", response_model=ConsentView)
def get_consent_request(
    request_id: UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> ConsentView:
    return ConsentView(**consent_view(session, principal.user, request_id))


@router.post("/consent", response_model=ConsentResult)
def post_consent(
    body: ConsentSubmit,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> ConsentResult:
    redirect_to = submit_consent(session, principal.user, body.request_id, body.decision, body.scopes)
    return ConsentResult(decision=body.decision, redirect_to=redirect_to)


@router.get("/grants", response_model=OAuthGrantPage)
def get_grants(principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> OAuthGrantPage:
    return OAuthGrantPage(items=[OAuthGrantRead(**item) for item in list_grants(session, principal.user)])


@admin_router.get("/grants", response_model=OAuthGrantPage)
def get_admin_grants(principal: Principal = ADMINS, session: Session = Depends(get_db)) -> OAuthGrantPage:
    """Every connected app. Admins only."""
    del principal
    return OAuthGrantPage(items=[OAuthGrantRead(**item) for item in list_all_grants(session)])


@admin_router.delete("/grants/{grant_id}", status_code=204)
def delete_admin_grant(grant_id: UUID, principal: Principal = ADMINS, session: Session = Depends(get_db)) -> None:
    """Disconnect any app. Admins only."""
    del principal
    revoke_any_grant(session, grant_id)


@router.delete("/grants/{grant_id}", status_code=204)
def delete_grant(
    grant_id: UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> None:
    revoke_grant_for_user(session, principal.user, grant_id)


def _authorization_response(decision: AuthorizeDecision) -> RedirectResponse | JSONResponse:
    if decision.location:
        return RedirectResponse(decision.location, status_code=302, headers=_NO_STORE)
    return _oauth_error(OAuthError(decision.error or "invalid_request", decision.description or "The request is invalid.", decision.status))


def _oauth_error(exc: OAuthError) -> JSONResponse:
    headers = {"Cache-Control": "no-store", "Pragma": "no-cache", **exc.headers}
    return JSONResponse({"error": exc.error, "error_description": exc.description}, status_code=exc.status, headers=headers)


def _return_url(request: Request) -> str:
    query = request.url.query
    target = f"{issuer()}/oauth/authorize"
    if query:
        target = f"{target}?{query}"
    return target


async def _form(request: Request) -> dict[str, str]:
    content = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" not in content and "multipart/form-data" not in content:
        raise OAuthError("invalid_request", "This endpoint accepts application/x-www-form-urlencoded.")
    form = await request.form()
    values: dict[str, str] = {}
    for key, value in form.multi_items():
        if not isinstance(value, str):
            raise OAuthError("invalid_request", "Request fields must be strings.")
        values[key] = value
    return values


def _ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hop = forwarded.split(",")[0].strip()
        return hop[:64] or None
    if request.client is not None and request.client.host:
        return request.client.host[:64]
    return None
