from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.errors import ApiError
from app.core.principal import SCOPE_DOCS_WRITE, Principal, require_roles
from app.schemas.content import ReindexRead
from app.services.content import reindex_document

router = APIRouter()


@router.post("/reindex", response_model=ReindexRead)
def post_reindex(
    document_id: UUID = Query(description="Document to extract and chunk again."),
    principal: Principal = Depends(require_roles(UserRole.super_admin, UserRole.admin)),
    session: Session = Depends(get_db),
) -> ReindexRead:
    """Queue text extraction for one document. Requires an admin and docs:write."""
    if SCOPE_DOCS_WRITE not in principal.scopes:
        raise ApiError(403, "MISSING_SCOPE", "This action requires a scope your credential does not grant.")
    result = reindex_document(session, principal, document_id)
    return ReindexRead(document_id=result.document_id, job_id=result.job_id, status=result.status)
