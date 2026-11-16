"""Who called the external API. Rows never contain document text."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import AuditChannel, UserRole
from app.core.principal import Principal, get_principal, require_roles
from app.schemas.access import AuditPage, to_audit
from app.services.audit import audit_page, list_audit, next_audit_cursor

router = APIRouter()
admin_router = APIRouter()

ADMINS = Depends(require_roles(UserRole.super_admin, UserRole.admin))


@router.get("/audit-log", response_model=AuditPage)
def get_my_audit(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> AuditPage:
    """Your external API calls, newest first."""
    page_size, offset = audit_page(limit, cursor)
    rows, total = list_audit(session, user_id=principal.user.id, limit=page_size, offset=offset)
    return AuditPage(items=[to_audit(row) for row in rows], next_cursor=next_audit_cursor(page_size, offset, total))


@admin_router.get("/audit-log", response_model=AuditPage)
def get_admin_audit(
    principal: Principal = ADMINS,
    session: Session = Depends(get_db),
    user_id: UUID | None = None,
    token_id: UUID | None = None,
    channel: AuditChannel | None = None,
    operation: str | None = Query(default=None, max_length=300),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> AuditPage:
    """Every external call. Filter by user, token, channel, or operation."""
    del principal
    page_size, offset = audit_page(limit, cursor)
    rows, total = list_audit(
        session,
        user_id=user_id,
        token_id=token_id,
        channel=channel,
        operation=operation,
        limit=page_size,
        offset=offset,
    )
    return AuditPage(items=[to_audit(row) for row in rows], next_cursor=next_audit_cursor(page_size, offset, total))
