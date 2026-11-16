"""Google sign-in and the test-only login used by the suite."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bootstrap import ensure_root_folder
from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.errors import ApiError
from app.core.events import USER_ACCESS_CHANGED
from app.integrations.google_auth import GoogleIdentity
from app.models.base import utcnow
from app.models.department import Department
from app.models.user import User
from app.services.activity import emit_with_session
from app.services.names import display_name_from_email


def authenticate_google(session: Session, identity: GoogleIdentity) -> User:
    if not identity.email_verified:
        raise ApiError(401, "EMAIL_NOT_VERIFIED", "Google account email is not verified.")
    user = _user_by_email(session, identity.email)
    changes: dict = {}
    if user is None:
        user = _provision(session, identity)
    else:
        changes = _accept_existing(user, identity)
    _commit_user(session, user)
    ensure_root_folder(session, user)
    if changes:
        emit_with_session(session, USER_ACCESS_CHANGED, user_id=str(user.id), changes=changes)
    return user


def login_for_tests(session: Session, email: str) -> User:
    settings = get_settings()
    allowed = settings.app_env == "test" or (settings.app_env == "development" and settings.allow_test_login)
    if not allowed:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    user = _user_by_email(session, email.strip().lower())
    if user is None:
        raise ApiError(404, "NOT_FOUND", "User not found.")
    _reject_blocked(user)
    now = utcnow()
    user.last_login_at = now
    user.last_seen_at = now
    session.commit()
    session.refresh(user)
    return user


def _accept_existing(user: User, identity: GoogleIdentity) -> dict:
    _reject_blocked(user)
    changes: dict = {}
    settings = get_settings()
    first_login = user.last_login_at is None
    if first_login and user.email in settings.super_admin_email_set and user.role != UserRole.super_admin:
        changes["role"] = {"from": user.role.value, "to": UserRole.super_admin.value}
        user.role = UserRole.super_admin
    user.google_sub = identity.sub
    if identity.picture:
        user.avatar_url = identity.picture
    now = utcnow()
    user.last_login_at = now
    user.last_seen_at = now
    return changes


def _provision(session: Session, identity: GoogleIdentity) -> User:
    settings = get_settings()
    if identity.email in settings.super_admin_email_set:
        role = UserRole.super_admin
    elif _domain_of(identity.email) in settings.allowed_domain_set and settings.auto_provision:
        role = UserRole.employee
    else:
        raise ApiError(403, "DOMAIN_NOT_ALLOWED", "This Google account is outside your company domain.")
    department = session.scalar(select(Department).where(Department.code == settings.default_department_code))
    if department is None:
        raise ApiError(500, "MISCONFIGURED", "The default department is not configured.")
    now = utcnow()
    name = identity.name[:200] if identity.name else display_name_from_email(identity.email)
    return User(
        email=identity.email,
        name=name,
        avatar_url=identity.picture,
        google_sub=identity.sub,
        role=role,
        department_id=department.id,
        is_active=True,
        is_bot=False,
        last_login_at=now,
        last_seen_at=now,
    )


def _reject_blocked(user: User) -> None:
    if not user.is_active:
        raise ApiError(403, "ACCOUNT_DEACTIVATED", "Your account has been deactivated. Contact your workspace administrator to restore access.")
    if user.is_bot:
        raise ApiError(403, "BOT_LOGIN_FORBIDDEN", "Service accounts cannot sign in with Google.")


def _user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(func.lower(User.email) == email))


def _domain_of(email: str) -> str:
    return email.split("@", 1)[1]


def _commit_user(session: Session, user: User) -> None:
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        constraint = str(exc.orig).lower()
        if "google_sub" in constraint:
            raise ApiError(409, "CONFLICT", "An account with this Google identity already exists.") from exc
        raise ApiError(409, "EMAIL_EXISTS", "A user with this email already exists.") from exc
    session.refresh(user)
