from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import SCOPE_DOCS_READ, Principal, require_scope
from app.schemas.dashboard import DashboardResponse, to_dashboard_response
from app.services.dashboard import get_dashboard

router = APIRouter()


@router.get("", response_model=DashboardResponse)
def get_workspace_dashboard(
    principal: Principal = Depends(require_scope(SCOPE_DOCS_READ)),
    session: Session = Depends(get_db),
) -> DashboardResponse:
    """Counts and recent documents the caller is allowed to see."""
    return to_dashboard_response(get_dashboard(session, principal))
