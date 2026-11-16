"""User invitations and account changes.

Every call takes the acting principal. Role limits live here so a new route
cannot skip them by calling the database itself.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.errors import ApiError
from app.core.events import USER_ACCESS_CHANGED
from app.core.principal import Principal
from app.models.department import Department
from app.models.user import User
from app.services.activity import emit_with_session
from app.services.names import display_name_from_email

MANAGE_ROLES = {UserRole.super_admin, UserRole.admin, UserRole.manager}
ADMIN_ROLES = {UserRole.super_admin, UserRole.admin}


@dataclass(frozen=True)
class UserFilters:
    search: str | None = None
    role: UserRole | None = None
    department_id: UUID | None = None
    status: str | None = None
    is_bot: bool | None = None
    page: int = 1
    page_size: int = 50


@dataclass
class UserPageResult:
    rows: list[tuple[User, Department]]
    total: int
    page: int
    page_size: int


def list_users(session: Session, principal: Principal, filters: UserFilters) -> UserPageResult:
    _ensure_manager(principal)
    criteria = _criteria(principal, filters)
    total = session.scalar(select(func.count()).select_from(User).where(*criteria)) or 0
    rows = session.execute(
        select(User, Department)
        .join(Department, Department.id == User.department_id)
        .where(*criteria)
        .order_by(User.name, User.id)
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    ).all()
    return UserPageResult(rows=[(user, department) for user, department in rows], total=total, page=filters.page, page_size=filters.page_size)


def list_directory(session: Session, principal: Principal) -> list[tuple[User, Department]]:
    """Names for sharing. Guests only see themselves. This is not the admin user list."""
    if principal.user.role == UserRole.guest:
        department = require_department(session, principal.user.department_id)
        return [(principal.user, department)]
    rows = session.execute(
        select(User, Department).join(Department, Department.id == User.department_id).order_by(User.name, User.id)
    ).all()
    return [(user, department) for user, department in rows]


def invite_user(
    session: Session,
    principal: Principal,
    *,
    email: str,
    role: UserRole,
    department_id: UUID,
    is_bot: bool,
) -> tuple[User, Department]:
    _ensure_can_assign(principal, target=None, new_role=role, new_department_id=department_id)
    if is_bot and role == UserRole.guest:
        raise ApiError(422, "INVALID_ACCOUNT", "Service users need an internal role.")
    _ensure_domain(email, role)
    department = require_department(session, department_id)
    if session.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise ApiError(409, "EMAIL_EXISTS", "A user with this email already exists.")
    user = User(
        email=email,
        name=display_name_from_email(email),
        role=role,
        department_id=department.id,
        is_active=True,
        is_bot=is_bot,
        invited_by=principal.user.id,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(409, "EMAIL_EXISTS", "A user with this email already exists.") from exc
    session.refresh(user)
    return user, department


def update_user(
    session: Session,
    principal: Principal,
    user_id: UUID,
    *,
    role: UserRole | None,
    department_id: UUID | None,
    name: str | None,
) -> tuple[User, Department]:
    target = _user(session, user_id)
    _ensure_can_assign(principal, target=target, new_role=role, new_department_id=department_id)
    if department_id is not None:
        require_department(session, department_id)
    if role is not None and role != target.role and role != UserRole.guest:
        _ensure_domain(target.email, role)
    _ensure_super_admin_remains(session, target, new_role=role, deactivate=False)
    changes: dict = {}
    if role is not None and role != target.role:
        changes["role"] = {"from": target.role.value, "to": role.value}
        target.role = role
    if department_id is not None and department_id != target.department_id:
        changes["department_id"] = {"from": str(target.department_id), "to": str(department_id)}
        target.department_id = department_id
    if name is not None and name != target.name:
        target.name = name
    session.commit()
    session.refresh(target)
    if changes:
        emit_with_session(session, USER_ACCESS_CHANGED, user_id=str(target.id), changes=changes)
    department = require_department(session, target.department_id)
    return target, department


def set_active(session: Session, principal: Principal, user_id: UUID, *, active: bool) -> tuple[User, Department]:
    target = _user(session, user_id)
    _ensure_can_assign(principal, target=target, new_role=None, new_department_id=None)
    if target.is_active != active:
        if not active:
            _ensure_super_admin_remains(session, target, new_role=None, deactivate=True)
            if principal.user.id == target.id:
                raise ApiError(403, "SELF_DEACTIVATE", "You cannot deactivate yourself.")
        previous = target.is_active
        target.is_active = active
        session.commit()
        session.refresh(target)
        emit_with_session(
            session,
            USER_ACCESS_CHANGED,
            user_id=str(target.id),
            changes={"is_active": {"from": previous, "to": active}},
        )
    department = require_department(session, target.department_id)
    return target, department


def _criteria(principal: Principal, filters: UserFilters) -> list:
    criteria = []
    department_id = filters.department_id
    if principal.user.role == UserRole.manager:
        if department_id is not None and department_id != principal.user.department_id:
            raise ApiError(403, "FORBIDDEN", "Managers can only view their own department.")
        department_id = principal.user.department_id
    if department_id is not None:
        criteria.append(User.department_id == department_id)
    if filters.role is not None:
        criteria.append(User.role == filters.role)
    if filters.is_bot is not None:
        criteria.append(User.is_bot.is_(filters.is_bot))
    if filters.status == "deactivated":
        criteria.append(User.is_active.is_(False))
    elif filters.status == "invited":
        criteria.extend([User.is_active.is_(True), User.is_bot.is_(False), User.last_login_at.is_(None)])
    elif filters.status == "active":
        criteria.append(User.is_active.is_(True))
        criteria.append(or_(User.is_bot.is_(True), User.last_login_at.is_not(None)))
    if filters.search and filters.search.strip():
        pattern = _contains(filters.search)
        criteria.append(or_(func.lower(User.name).like(pattern, escape="\\"), func.lower(User.email).like(pattern, escape="\\")))
    return criteria


def _ensure_manager(principal: Principal) -> None:
    if principal.user.role not in MANAGE_ROLES:
        raise ApiError(403, "FORBIDDEN", "You cannot view users.")


def _ensure_can_assign(
    principal: Principal,
    *,
    target: User | None,
    new_role: UserRole | None,
    new_department_id: UUID | None,
) -> None:
    actor = principal.user
    if actor.role not in MANAGE_ROLES:
        raise ApiError(403, "FORBIDDEN", "You cannot manage users.")
    if target is not None and target.role in ADMIN_ROLES and actor.role != UserRole.super_admin:
        raise ApiError(403, "FORBIDDEN", "Only a Super Admin can manage administrator accounts.")
    if new_role in ADMIN_ROLES and actor.role != UserRole.super_admin:
        raise ApiError(403, "FORBIDDEN", "Only a Super Admin can assign administrator roles.")
    if actor.role == UserRole.manager:
        if target is not None and (target.role != UserRole.employee or target.department_id != actor.department_id):
            raise ApiError(403, "FORBIDDEN", "Managers can manage employees in their own department only.")
        if new_role not in (None, UserRole.employee):
            raise ApiError(403, "FORBIDDEN", "Managers can only assign the employee role.")
        if new_department_id is not None and new_department_id != actor.department_id:
            raise ApiError(403, "FORBIDDEN", "Managers can only use their own department.")
        if target is None and new_department_id != actor.department_id:
            raise ApiError(403, "FORBIDDEN", "Managers can invite employees to their own department.")


def _ensure_domain(email: str, role: UserRole) -> None:
    if role == UserRole.guest:
        return
    domain = email.split("@", 1)[1]
    if domain not in get_settings().allowed_domain_set:
        raise ApiError(403, "DOMAIN_NOT_ALLOWED", "Internal roles require an allowed email domain.")


def _ensure_super_admin_remains(session: Session, target: User, *, new_role: UserRole | None, deactivate: bool) -> None:
    if target.role != UserRole.super_admin or not target.is_active:
        return
    loses_access = deactivate or (new_role is not None and new_role != UserRole.super_admin)
    if not loses_access:
        return
    others = session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.super_admin, User.is_active.is_(True), User.id != target.id)
    )
    if not others:
        raise ApiError(409, "LAST_SUPER_ADMIN", "At least one Super Admin must remain.")


def _user(session: Session, user_id: UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "User not found.")
    return user


def require_department(session: Session, department_id: UUID) -> Department:
    department = session.get(Department, department_id)
    if department is None:
        raise ApiError(404, "NOT_FOUND", "Department not found.")
    return department


def _contains(value: str) -> str:
    escaped = value.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
