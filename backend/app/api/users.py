from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.principal import Principal, get_principal, require_roles
from app.schemas.users import InviteUser, UpdateUser, UserPage, UserRead, to_user_read
from app.services.users import UserFilters, invite_user, list_directory, list_users, set_active, update_user

router = APIRouter()

MANAGERS = Depends(require_roles(UserRole.super_admin, UserRole.admin, UserRole.manager))


@router.get("", response_model=UserPage)
def get_users(
    principal: Principal = MANAGERS,
    session: Session = Depends(get_db),
    search: str | None = None,
    role: UserRole | None = None,
    department_id: UUID | None = None,
    status: str | None = Query(default=None, pattern="^(active|invited|deactivated)$"),
    is_bot: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> UserPage:
    result = list_users(
        session,
        principal,
        UserFilters(
            search=search,
            role=role,
            department_id=department_id,
            status=status,
            is_bot=is_bot,
            page=page,
            page_size=page_size,
        ),
    )
    return UserPage(
        items=[to_user_read(user, department) for user, department in result.rows],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/directory", response_model=list[UserRead])
def get_directory(principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> list[UserRead]:
    """People you can name when sharing. Guests receive only their own account."""
    return [to_user_read(user, department) for user, department in list_directory(session, principal)]


@router.post("/invite", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def post_invite(body: InviteUser, principal: Principal = MANAGERS, session: Session = Depends(get_db)) -> UserRead:
    user, department = invite_user(
        session,
        principal,
        email=body.email,
        role=body.role,
        department_id=body.department_id,
        is_bot=body.is_bot,
    )
    return to_user_read(user, department)


@router.patch("/{user_id}", response_model=UserRead)
def patch_user(user_id: UUID, body: UpdateUser, principal: Principal = MANAGERS, session: Session = Depends(get_db)) -> UserRead:
    user, department = update_user(
        session,
        principal,
        user_id,
        role=body.role,
        department_id=body.department_id,
        name=body.name,
    )
    return to_user_read(user, department)


@router.post("/{user_id}/deactivate", response_model=UserRead)
def post_deactivate(user_id: UUID, principal: Principal = MANAGERS, session: Session = Depends(get_db)) -> UserRead:
    user, department = set_active(session, principal, user_id, active=False)
    return to_user_read(user, department)


@router.post("/{user_id}/reactivate", response_model=UserRead)
def post_reactivate(user_id: UUID, principal: Principal = MANAGERS, session: Session = Depends(get_db)) -> UserRead:
    user, department = set_active(session, principal, user_id, active=True)
    return to_user_read(user, department)
