from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import SCOPE_DOCS_READ, SCOPE_DOCS_WRITE, Principal, require_scope
from app.schemas.folders import FolderCreate, FolderMove, FolderNode, FolderRead, FolderUpdate, to_folder_read
from app.schemas.permissions import GrantRead, PermissionsRead, PermissionsUpdate
from app.services import folders as folder_service

router = APIRouter()

READER = Depends(require_scope(SCOPE_DOCS_READ))
WRITER = Depends(require_scope(SCOPE_DOCS_WRITE))


@router.get("/tree", response_model=list[FolderNode])
def get_tree(principal: Principal = READER, session: Session = Depends(get_db)) -> list[FolderNode]:
    """Nested folders the caller can see, including path-only ancestors, with document counts."""
    return folder_service.folder_tree(session, principal)


@router.post("", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def post_folder(body: FolderCreate, principal: Principal = WRITER, session: Session = Depends(get_db)) -> FolderRead:
    """Create a folder. Top-level folders are limited to admins and that department's manager."""
    folder, my_access = folder_service.create_folder(session, principal, body)
    return to_folder_read(folder, my_access)


@router.patch("/{folder_id}", response_model=FolderRead)
def patch_folder(
    folder_id: UUID,
    body: FolderUpdate,
    principal: Principal = WRITER,
    session: Session = Depends(get_db),
) -> FolderRead:
    """Rename a folder or change its description. The stored path stays the same."""
    folder, my_access = folder_service.update_folder(session, principal, folder_id, body)
    return to_folder_read(folder, my_access)


@router.post("/{folder_id}/move", response_model=FolderRead)
def post_move(
    folder_id: UUID,
    body: FolderMove,
    principal: Principal = WRITER,
    session: Session = Depends(get_db),
) -> FolderRead:
    """Move a folder. Cycles are rejected and descendant paths update in one transaction."""
    folder, my_access = folder_service.move_folder(session, principal, folder_id, body.parent_id)
    return to_folder_read(folder, my_access)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: UUID, principal: Principal = WRITER, session: Session = Depends(get_db)) -> None:
    """Soft-delete a folder and its descendant folders. Refuses when documents are still inside."""
    folder_service.delete_folder(session, principal, folder_id)


@router.get("/{folder_id}/permissions", response_model=PermissionsRead)
def get_permissions(folder_id: UUID, principal: Principal = READER, session: Session = Depends(get_db)) -> PermissionsRead:
    """Read visibility and explicit grants. Hidden folders return 404."""
    folder, grants, my_access = folder_service.get_folder_permissions(session, principal, folder_id)
    return _permissions(folder, grants, my_access)


@router.put("/{folder_id}/permissions", response_model=PermissionsRead)
def put_permissions(
    folder_id: UUID,
    body: PermissionsUpdate,
    principal: Principal = WRITER,
    session: Session = Depends(get_db),
) -> PermissionsRead:
    """Replace visibility, the default audience, and every grant in one transaction."""
    folder, grants, my_access = folder_service.put_folder_permissions(session, principal, folder_id, body)
    return _permissions(folder, grants, my_access)


def _permissions(folder, grants, my_access) -> PermissionsRead:
    return PermissionsRead(
        visibility=folder.visibility,
        default_access=folder.default_access,
        grants=[GrantRead(principal_type=grant.principal_type, principal_id=grant.principal_id, access=grant.access) for grant in grants],
        my_access=my_access,
    )
