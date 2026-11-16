from collections.abc import Callable

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.principal import Principal, get_principal
from app.core.rate_limit import google_login_limiter
from app.core.security import SESSION_TTL, issue_session_token
from app.integrations.google_auth import get_google_verifier
from app.schemas.users import GoogleLoginRequest, TestLoginRequest, UserRead, to_user_read
from app.services.auth import authenticate_google, login_for_tests
from app.services.users import require_department

router = APIRouter()


@router.post("/google", response_model=UserRead)
def google_login(
    body: GoogleLoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
    verify: Callable = Depends(get_google_verifier),
) -> UserRead:
    settings = get_settings()
    host = request.client.host if request.client else "unknown"
    if not google_login_limiter.allow(host, limit=settings.auth_rate_limit, window_seconds=settings.auth_rate_limit_window_seconds):
        raise ApiError(
            429,
            "RATE_LIMITED",
            "Too many sign-in attempts. Try again shortly.",
            headers={"Retry-After": str(settings.auth_rate_limit_window_seconds)},
        )
    user = authenticate_google(session, verify(body.id_token))
    _set_session_cookie(response, issue_session_token(user.id))
    return to_user_read(user, require_department(session, user.department_id))


@router.post("/test-login", response_model=UserRead, include_in_schema=False)
def test_login(body: TestLoginRequest, response: Response, session: Session = Depends(get_db)) -> UserRead:
    """Enabled only when APP_ENV=test. The service rejects every other environment."""
    user = login_for_tests(session, body.email)
    _set_session_cookie(response, issue_session_token(user.id))
    return to_user_read(user, require_department(session, user.department_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, principal: Principal = Depends(get_principal)) -> None:
    """Anonymous callers are rejected by get_principal before the cookie is cleared."""
    del principal
    _clear_session_cookie(response)


@router.get("/me", response_model=UserRead)
def me(principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> UserRead:
    return to_user_read(principal.user, require_department(session, principal.user.department_id))


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
