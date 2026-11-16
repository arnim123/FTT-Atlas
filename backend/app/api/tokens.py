"""Session-only token management. Bearer tokens cannot call these routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.principal import Principal, get_principal, require_roles
from app.schemas.access import TokenCreate, TokenCreated, TokenPage, TokenRead, to_token_created, to_token_read
from app.services.tokens import create_token, list_tokens, revoke_token

router = APIRouter()
admin_router = APIRouter()

ADMINS = Depends(require_roles(UserRole.super_admin, UserRole.admin))


@router.post("", response_model=TokenCreated, status_code=status.HTTP_201_CREATED)
def post_token(
    body: TokenCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> TokenCreated:
    """Create a token. The secret is returned once. Write scopes need the organization switch."""
    row, secret = create_token(
        session,
        principal,
        name=body.name,
        scopes=body.scopes,
        expires_in_days=body.expires_in_days,
        user_id=body.user_id,
    )
    return to_token_created(row, secret)


@router.get("", response_model=TokenPage)
def get_tokens(principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> TokenPage:
    """List your tokens. Secrets are not included."""
    rows = list_tokens(session, user_id=principal.user.id)
    return TokenPage(items=[to_token_read(row) for row in rows])


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_token(
    token_id: UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> None:
    """Revoke one of your tokens."""
    revoke_token(session, token_id, user_id=principal.user.id)


@admin_router.get("/tokens", response_model=TokenPage)
def get_admin_tokens(principal: Principal = ADMINS, session: Session = Depends(get_db)) -> TokenPage:
    """List every token. Admins only."""
    del principal
    return TokenPage(items=[to_token_read(row) for row in list_tokens(session)])


@admin_router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_token(token_id: UUID, principal: Principal = ADMINS, session: Session = Depends(get_db)) -> None:
    """Revoke any token. Admins only."""
    del principal
    revoke_token(session, token_id)
