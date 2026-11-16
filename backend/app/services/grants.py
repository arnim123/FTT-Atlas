"""Explicit document and folder grants. Replacing grants is one transaction."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import PrincipalType
from app.core.errors import ApiError
from app.models.department import Department
from app.models.permission import DocumentPermission, FolderPermission
from app.models.user import User
from app.schemas.permissions import GrantInput

PermissionModel = type[DocumentPermission] | type[FolderPermission]


def load_grants(session: Session, model: PermissionModel, resource_id: UUID) -> list:
    return list(
        session.scalars(
            select(model).where(model.resource_id == resource_id).order_by(model.created_at, model.id)
        )
    )


def load_grants_for(session: Session, model: PermissionModel, resource_ids: list[UUID]) -> dict[UUID, list]:
    grouped: dict[UUID, list] = defaultdict(list)
    if not resource_ids:
        return grouped
    rows = session.scalars(select(model).where(model.resource_id.in_(resource_ids))).all()
    for row in rows:
        grouped[row.resource_id].append(row)
    return grouped


def validate_grants(session: Session, grants: list[GrantInput]) -> None:
    seen: set[tuple[PrincipalType, UUID]] = set()
    user_ids: list[UUID] = []
    department_ids: list[UUID] = []
    for grant in grants:
        key = (grant.principal_type, grant.principal_id)
        if key in seen:
            raise ApiError(422, "DUPLICATE_GRANT", "Each person or department can only be listed once.")
        seen.add(key)
        if grant.principal_type == PrincipalType.user:
            user_ids.append(grant.principal_id)
        else:
            department_ids.append(grant.principal_id)
    _require_known(session, User, user_ids, "One or more people do not exist.")
    _require_known(session, Department, department_ids, "One or more departments do not exist.")


def replace_grants(session: Session, model: PermissionModel, resource_id: UUID, grants: list[GrantInput], created_by: UUID) -> None:
    """Delete the previous rows and insert the new set. The caller commits."""
    session.execute(delete(model).where(model.resource_id == resource_id))
    for grant in grants:
        session.add(
            model(
                resource_id=resource_id,
                principal_type=grant.principal_type,
                principal_id=grant.principal_id,
                access=grant.access,
                created_by=created_by,
            )
        )
    session.flush()


def _require_known(session: Session, model, identifiers: list[UUID], message: str) -> None:
    if not identifiers:
        return
    found = set(session.scalars(select(model.id).where(model.id.in_(identifiers))))
    missing = [str(identifier) for identifier in identifiers if identifier not in found]
    if missing:
        raise ApiError(422, "UNKNOWN_PRINCIPAL", message, details={"ids": missing})
