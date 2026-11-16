"""Folder tree, moves, and grants.

Paths are materialized from folder ids (`/{id}/{child_id}`), so a rename does
not rewrite the subtree. A move rewrites path and depth for the folder and
every descendant in the same transaction, after rejecting a cycle. There is no
depth cap.

The tree includes a folder the caller cannot open when they can open something
inside it. Those ancestors are path-only: name, child list, and document count.
"""

from collections import defaultdict
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.core.errors import ApiError
from app.core.principal import Principal
from app.models.base import utcnow
from app.models.department import Department
from app.models.document import Document
from app.models.folder import Folder
from app.models.permission import FolderPermission
from app.permissions.engine import access_level, accessible_documents_query, accessible_folders_query, can, direct_folder_access_query
from app.schemas.folders import FolderCreate, FolderNode, FolderUpdate
from app.schemas.permissions import AccessName, PermissionsUpdate
from app.services.activity import commit_and_emit
from app.services.grants import load_grants, load_grants_for, replace_grants, validate_grants

_ADMIN_ROLES = {UserRole.super_admin, UserRole.admin}
_PATH_ONLY = "none"


def folder_tree(session: Session, principal: Principal) -> list[FolderNode]:
    user = principal.user
    scopes = principal.scopes
    folders = list(
        session.scalars(
            select(Folder)
            .where(accessible_folders_query(user, scopes))
            .order_by(Folder.sort_order, Folder.name, Folder.id)
        )
    )
    if not folders:
        return []
    visible = {folder.id: folder for folder in folders}
    direct_ids = set(session.scalars(select(Folder.id).where(direct_folder_access_query(user, scopes))))
    grants = load_grants_for(session, FolderPermission, list(direct_ids))
    raw_counts = dict(
        session.execute(
            select(Document.folder_id, func.count())
            .where(accessible_documents_query(user, scopes))
            .group_by(Document.folder_id)
        ).all()
    )
    children: dict[UUID | None, list[Folder]] = defaultdict(list)
    for folder in folders:
        children[folder.parent_id].append(folder)
    for kids in children.values():
        kids.sort(key=lambda item: (item.sort_order, item.name.lower(), str(item.id)))

    totals: dict[UUID, int] = {}

    def total(folder_id: UUID) -> int:
        if folder_id in totals:
            return totals[folder_id]
        count = int(raw_counts.get(folder_id, 0))
        for child in children.get(folder_id, []):
            count += total(child.id)
        totals[folder_id] = count
        return count

    def node(folder: Folder) -> FolderNode:
        level: AccessName = _PATH_ONLY
        if folder.id in direct_ids:
            level = access_level(user, folder, grants.get(folder.id, ()), scopes)
        path_only = level == _PATH_ONLY
        return FolderNode(
            id=folder.id,
            name=folder.name,
            parent_id=folder.parent_id,
            path_only=path_only,
            document_count=total(folder.id),
            my_access=level,
            children=[node(child) for child in children.get(folder.id, [])],
            description=None if path_only else folder.description,
            department_id=None if path_only else folder.department_id,
            owner_id=None if path_only else folder.owner_id,
            visibility=None if path_only else folder.visibility,
            default_access=None if path_only else folder.default_access,
            depth=None if path_only else folder.depth,
            sort_order=None if path_only else folder.sort_order,
            path=None if path_only else folder.path,
        )

    roots = [folder for folder in folders if folder.parent_id not in visible]
    roots.sort(key=lambda item: (item.sort_order, item.name.lower(), str(item.id)))
    return [node(folder) for folder in roots]


def create_folder(session: Session, principal: Principal, payload: FolderCreate) -> tuple[Folder, AccessName]:
    parent = None
    if payload.parent_id is not None:
        parent = require_folder(session, principal, payload.parent_id, "edit")
        if payload.department_id != parent.department_id:
            raise ApiError(422, "DEPARTMENT_MISMATCH", "A folder uses its parent folder's department.")
        department_id = parent.department_id
    else:
        _require_root_creator(principal, payload.department_id)
        _require_department(session, payload.department_id)
        department_id = payload.department_id
    _require_unique_name(session, parent.id if parent else None, payload.name)
    folder_id = uuid4()
    folder = Folder(
        id=folder_id,
        name=payload.name,
        parent_id=parent.id if parent else None,
        path=f"/{folder_id}" if parent is None else f"{parent.path}/{folder_id}",
        depth=0 if parent is None else parent.depth + 1,
        department_id=department_id,
        owner_id=principal.user.id,
        visibility=payload.visibility,
        default_access=payload.default_access,
        description=payload.description,
        sort_order=_next_sort(session, parent.id if parent else None),
    )
    session.add(folder)
    commit_and_emit(session)
    return folder, access_level(principal.user, folder, (), principal.scopes)


def update_folder(session: Session, principal: Principal, folder_id: UUID, payload: FolderUpdate) -> tuple[Folder, AccessName]:
    folder = require_folder(session, principal, folder_id, "manage")
    if "name" in payload.model_fields_set and payload.name is not None:
        _require_unique_name(session, folder.parent_id, payload.name, exclude_id=folder.id)
        folder.name = payload.name
    if "description" in payload.model_fields_set:
        folder.description = payload.description
    if "sort_order" in payload.model_fields_set and payload.sort_order is not None:
        folder.sort_order = payload.sort_order
    commit_and_emit(session)
    grants = load_grants(session, FolderPermission, folder.id)
    return folder, access_level(principal.user, folder, grants, principal.scopes)


def move_folder(session: Session, principal: Principal, folder_id: UUID, parent_id: UUID | None) -> tuple[Folder, AccessName]:
    folder = require_folder(session, principal, folder_id, "manage")
    if parent_id is None:
        _require_root_creator(principal, folder.department_id)
        destination = None
        new_path = f"/{folder.id}"
        new_depth = 0
    else:
        destination = require_folder(session, principal, parent_id, "edit")
        if destination.id == folder.id or destination.path == folder.path or destination.path.startswith(f"{folder.path}/"):
            raise ApiError(409, "CYCLE", "A folder cannot be moved into itself.")
        if destination.department_id != folder.department_id and principal.user.role not in _ADMIN_ROLES:
            raise ApiError(422, "DEPARTMENT_MISMATCH", "A folder stays in its department when it moves.")
        new_path = f"{destination.path}/{folder.id}"
        new_depth = destination.depth + 1
    new_parent_id = destination.id if destination else None
    if folder.parent_id == new_parent_id:
        grants = load_grants(session, FolderPermission, folder.id)
        return folder, access_level(principal.user, folder, grants, principal.scopes)
    _require_unique_name(session, new_parent_id, folder.name, exclude_id=folder.id)
    _rewrite_subtree(session, folder, new_path, new_depth, new_parent_id)
    commit_and_emit(session)
    grants = load_grants(session, FolderPermission, folder.id)
    return folder, access_level(principal.user, folder, grants, principal.scopes)


def delete_folder(session: Session, principal: Principal, folder_id: UUID) -> None:
    folder = require_folder(session, principal, folder_id, "manage")
    rows = _subtree(session, folder)
    identifiers = [row.id for row in rows]
    document_count = session.scalar(
        select(func.count()).select_from(Document).where(Document.deleted_at.is_(None), Document.folder_id.in_(identifiers))
    ) or 0
    if document_count:
        raise ApiError(
            409,
            "FOLDER_NOT_EMPTY",
            "Move or delete the documents in this folder first.",
            details={"documents": document_count},
        )
    deleted_at = utcnow()
    for row in rows:
        row.deleted_at = deleted_at
    commit_and_emit(session)


def get_folder_permissions(session: Session, principal: Principal, folder_id: UUID) -> tuple[Folder, list, AccessName]:
    folder = require_folder(session, principal, folder_id, "view")
    grants = load_grants(session, FolderPermission, folder.id)
    return folder, grants, access_level(principal.user, folder, grants, principal.scopes)


def put_folder_permissions(
    session: Session, principal: Principal, folder_id: UUID, payload: PermissionsUpdate
) -> tuple[Folder, list, AccessName]:
    folder = require_folder(session, principal, folder_id, "manage")
    validate_grants(session, payload.grants)
    folder.visibility = payload.visibility
    folder.default_access = payload.default_access
    replace_grants(session, FolderPermission, folder.id, payload.grants, principal.user.id)
    commit_and_emit(session)
    grants = load_grants(session, FolderPermission, folder.id)
    return folder, grants, access_level(principal.user, folder, grants, principal.scopes)


def require_folder(session: Session, principal: Principal, folder_id: UUID, action: str) -> Folder:
    folder = session.get(Folder, folder_id)
    if folder is None or folder.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", "Folder not found.")
    grants = load_grants(session, FolderPermission, folder.id)
    if not can(principal.user, folder, "view", grants, principal.scopes):
        raise ApiError(404, "NOT_FOUND", "Folder not found.")
    if action != "view" and not can(principal.user, folder, action, grants, principal.scopes):
        raise ApiError(403, "FORBIDDEN", "You do not have access to this action.")
    return folder


def _rewrite_subtree(session: Session, folder: Folder, new_path: str, new_depth: int, parent_id: UUID | None) -> None:
    """Point the folder at its new parent and rewrite descendant paths before commit."""
    rows = _subtree(session, folder)
    old_root = folder.path
    old_paths = {row.id: row.path for row in rows}
    old_depths = {row.id: row.depth for row in rows}
    delta = new_depth - folder.depth
    for row in rows:
        row.path = f"tmp/{row.id}"
    session.flush()
    for row in rows:
        suffix = old_paths[row.id][len(old_root) :]
        row.path = f"{new_path}{suffix}"
        row.depth = old_depths[row.id] + delta
    folder.parent_id = parent_id
    session.flush()


def _subtree(session: Session, folder: Folder) -> list[Folder]:
    pattern = _like_prefix(folder.path)
    return list(
        session.scalars(
            select(Folder).where(
                Folder.deleted_at.is_(None),
                or_(Folder.id == folder.id, Folder.path.like(pattern, escape="\\")),
            )
        )
    )


def folder_display_paths(session: Session, folder_ids: set[UUID]) -> dict[UUID, str]:
    """Folder names from the root down, joined with ' / '.

    The path is the location of a document the caller can already see. Ancestor
    names are included even when the caller cannot open those folders.
    """
    if not folder_ids:
        return {}
    loaded: dict[UUID, Folder] = {}
    pending = set(folder_ids)
    while pending:
        rows = list(session.scalars(select(Folder).where(Folder.id.in_(pending))))
        pending = set()
        for folder in rows:
            loaded[folder.id] = folder
            if folder.parent_id is not None and folder.parent_id not in loaded:
                pending.add(folder.parent_id)

    paths: dict[UUID, str] = {}
    for folder_id in folder_ids:
        parts: list[str] = []
        seen: set[UUID] = set()
        current = loaded.get(folder_id)
        while current is not None and current.id not in seen:
            seen.add(current.id)
            parts.append(current.name)
            parent_id = current.parent_id
            current = loaded.get(parent_id) if parent_id is not None else None
        parts.reverse()
        paths[folder_id] = " / ".join(parts)
    return paths


def _like_prefix(path: str) -> str:
    escaped = path.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}/%"


def _require_root_creator(principal: Principal, department_id: UUID) -> None:
    user = principal.user
    if user.role in _ADMIN_ROLES:
        return
    if user.role == UserRole.manager and user.department_id == department_id:
        return
    raise ApiError(403, "FORBIDDEN", "Only an administrator or that department's manager can create a top-level folder.")


def _require_department(session: Session, department_id: UUID) -> None:
    if session.get(Department, department_id) is None:
        raise ApiError(422, "UNKNOWN_DEPARTMENT", "Choose a department that exists.")


def _require_unique_name(session: Session, parent_id: UUID | None, name: str, exclude_id: UUID | None = None) -> None:
    statement = select(Folder.id).where(Folder.deleted_at.is_(None), func.lower(Folder.name) == name.lower())
    if parent_id is None:
        statement = statement.where(Folder.parent_id.is_(None))
    else:
        statement = statement.where(Folder.parent_id == parent_id)
    if exclude_id is not None:
        statement = statement.where(Folder.id != exclude_id)
    if session.scalar(statement) is not None:
        raise ApiError(409, "NAME_EXISTS", "A folder with this name already exists here.")


def _next_sort(session: Session, parent_id: UUID | None) -> int:
    statement = select(func.max(Folder.sort_order)).where(Folder.deleted_at.is_(None))
    if parent_id is None:
        statement = statement.where(Folder.parent_id.is_(None))
    else:
        statement = statement.where(Folder.parent_id == parent_id)
    current = session.scalar(statement)
    return 0 if current is None else int(current) + 1
