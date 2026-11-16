"""Organization switches for external AI. Session admins only."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.principal import Principal, get_principal, require_roles
from app.schemas.access import OrgSettingsRead, OrgSettingsUpdate, to_org_settings
from app.services.org_settings import get_org_settings, update_org_settings

router = APIRouter()
read_router = APIRouter()

ADMINS = Depends(require_roles(UserRole.super_admin, UserRole.admin))


@read_router.get("/org-settings", response_model=OrgSettingsRead)
def read_org_settings(principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> OrgSettingsRead:
    """The switches every signed-in person needs before creating a token. Changes stay on the admin route."""
    del principal
    return to_org_settings(get_org_settings(session))


@router.get("/org-settings", response_model=OrgSettingsRead)
def get_settings_row(principal: Principal = ADMINS, session: Session = Depends(get_db)) -> OrgSettingsRead:
    """Read the external-access switches."""
    del principal
    return to_org_settings(get_org_settings(session))


@router.patch("/org-settings", response_model=OrgSettingsRead)
def patch_settings_row(
    body: OrgSettingsUpdate,
    principal: Principal = ADMINS,
    session: Session = Depends(get_db),
) -> OrgSettingsRead:
    """Turn external access or write scopes on or off, and cap token lifetime."""
    del principal
    row = update_org_settings(
        session,
        external_ai_enabled=body.external_ai_enabled,
        allow_write_scopes=body.allow_write_scopes,
        max_token_days=body.max_token_days,
    )
    return to_org_settings(row)
