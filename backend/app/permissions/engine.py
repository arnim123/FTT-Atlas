"""Permission rules for documents and folders.

The functions in this module are pure. They never open a session, execute SQL,
or read the clock. `can` and `access_level` inspect the user, the resource, and
the grants the caller already loaded. `accessible_documents_query` and
`accessible_folders_query` return SQLAlchemy boolean expressions; the caller
runs them.

Role `manager` is the department manager. Access levels, from lowest to
highest, are none, view, edit, and manage. The level on a resource is the
highest positive grant, then the restrictions below, then the scope ceiling:

    effective = min(role_based_access, scope_allowed_access)

Positive grants (the highest one wins):

- super_admin and admin: manage on every live resource
- owner: manage
- department manager: manage on a resource in their own department
- an explicit user grant: view or edit, as stored
- a department grant: view or edit for members of that department, guests included
- visibility department: people in that department, except guests, get default_access
- visibility organization: everyone except guests gets default_access

Restrictions (these only remove access):

- an inactive user gets nothing, including admins and owners
- a soft-deleted resource is invisible to everyone, including admins
- visibility private admits only the owner and admins. Department managers and
  explicit grants do not open a private resource
- visibility custom adds no default audience. Owner, admins, the department
  manager, and explicit grants still apply
- guests do not receive a visibility default. They keep explicit user and
  department grants, and those grants stop at edit unless the guest is the owner
- an archived document admits only the owner, an admin, and the department
  manager of that document's department. Grants and visibility defaults do not
  survive archival. A private archived document stays owner-and-admin only,
  because the private restriction still applies

Scopes never widen a decision. `docs:read` caps the result at view, so a
manager holding only that scope cannot edit or manage. `docs:write` caps the
result at manage. A credential with neither scope caps it at none. When
`scopes` is omitted, the user's session scopes are used (`scopes_for_role`).

A folder is listed when the user can view it, or can view a folder or document
inside it. Ancestors of a visible item are path-only containers: the tree shows
their names and hides their details. `direct_folder_access_query` is the direct
half of that rule; `accessible_folders_query` includes the ancestors.
"""

from collections.abc import Sequence, Set as AbstractSet
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy import and_, exists, false as sql_false, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.core.enums import AccessGrant, DocumentStatus, PrincipalType, UserRole, Visibility
from app.core.principal import SCOPE_DOCS_READ, SCOPE_DOCS_WRITE, scopes_for_role
from app.models.document import Document
from app.models.folder import Folder
from app.models.permission import DocumentPermission, FolderPermission
from app.models.user import User

AccessLevel = Literal["none", "view", "edit", "manage"]
Action = Literal["view", "edit", "manage"]

_RANK: dict[str, int] = {"none": 0, "view": 1, "edit": 2, "manage": 3}
_ADMIN_ROLES = frozenset({UserRole.super_admin, UserRole.admin})


class Resource(Protocol):
    owner_id: UUID
    department_id: UUID
    visibility: Visibility
    default_access: AccessGrant
    deleted_at: object


class Grant(Protocol):
    principal_type: PrincipalType
    principal_id: UUID
    access: AccessGrant


def can(
    user: User,
    resource: Resource,
    action: Action,
    grants: Sequence[Grant] = (),
    scopes: AbstractSet[str] | None = None,
) -> bool:
    """True when the user's effective access is at least `action`."""
    if action not in ("view", "edit", "manage"):
        raise ValueError(f"Unknown action: {action}")
    return _RANK[access_level(user, resource, grants, scopes)] >= _RANK[action]


def access_level(
    user: User,
    resource: Resource,
    grants: Sequence[Grant] = (),
    scopes: AbstractSet[str] | None = None,
) -> AccessLevel:
    """Effective access after role rules and the scope ceiling."""
    role_level = _role_access(user, resource, grants)
    ceiling = scope_ceiling(_resolved_scopes(user, scopes))
    return _lower(role_level, ceiling)


def scope_ceiling(scopes: AbstractSet[str]) -> AccessLevel:
    """The highest level a credential may reach. Write covers manage; read stops at view."""
    if SCOPE_DOCS_WRITE in scopes:
        return "manage"
    if SCOPE_DOCS_READ in scopes:
        return "view"
    return "none"


def accessible_documents_query(user: User, scopes: AbstractSet[str] | None = None) -> ColumnElement[bool]:
    """SQL boolean for documents this user may view. Excludes soft-deleted rows.

    Archived and private documents stay inside the filter: archived rows are
    visible to the owner, an admin, and that department's manager (unless the
    document is also private); private rows are visible to the owner and admins.
    """
    if not _query_can_view(user, scopes):
        return sql_false()
    if user.role in _ADMIN_ROLES:
        return Document.deleted_at.is_(None)

    private = Document.visibility == Visibility.private
    archived = Document.status == DocumentStatus.archived
    closed = and_(
        or_(private, archived),
        or_(_owner(Document, user), and_(_manager(Document, user), Document.visibility != Visibility.private)),
    )
    opened = and_(
        Document.visibility != Visibility.private,
        Document.status == DocumentStatus.active,
        _open_access(Document, DocumentPermission, user),
    )
    return and_(Document.deleted_at.is_(None), or_(closed, opened))


def direct_folder_access_query(
    user: User,
    scopes: AbstractSet[str] | None = None,
    *,
    folder: type[Folder] | Folder = Folder,
) -> ColumnElement[bool]:
    """SQL boolean for folders the user may view directly. Excludes soft-deleted rows."""
    if not _query_can_view(user, scopes):
        return sql_false()
    if user.role in _ADMIN_ROLES:
        return folder.deleted_at.is_(None)
    opened = and_(
        folder.visibility != Visibility.private,
        _open_access(folder, FolderPermission, user),
    )
    return and_(
        folder.deleted_at.is_(None),
        or_(and_(folder.visibility == Visibility.private, _owner(folder, user)), opened),
    )


def accessible_folders_query(user: User, scopes: AbstractSet[str] | None = None) -> ColumnElement[bool]:
    """SQL boolean for folders that should appear in the tree.

    A folder matches when the user can view it, can view a descendant folder,
    or can view a document stored in it or in a descendant. Ancestors that match
    only because of something inside them are path-only containers.
    """
    if not _query_can_view(user, scopes):
        return sql_false()

    direct = direct_folder_access_query(user, scopes, folder=Folder)
    # Correlate Folder explicitly. A nested IN (SELECT ...) otherwise adds a
    # second folders FROM and matches every folder that contains any visible item.
    child_prefix = _like_children(Folder.path)
    descendant = aliased(Folder)
    descendant_visible = (
        exists(
            select(descendant.id).where(
                direct_folder_access_query(user, scopes, folder=descendant),
                descendant.path.like(child_prefix, escape="\\"),
            )
        )
        .correlate(Folder)
    )
    contained = aliased(Folder)
    document_visible = (
        exists(
            select(Document.id).where(
                accessible_documents_query(user, scopes),
                Document.folder_id == contained.id,
                contained.deleted_at.is_(None),
                or_(contained.id == Folder.id, contained.path.like(child_prefix, escape="\\")),
            )
        )
        .correlate(Folder)
    )
    return and_(Folder.deleted_at.is_(None), or_(direct, descendant_visible, document_visible))


def _role_access(user: User, resource: Resource, grants: Sequence[Grant]) -> AccessLevel:
    if not user.is_active or getattr(resource, "deleted_at", None) is not None:
        return "none"

    private = resource.visibility == Visibility.private
    archived = getattr(resource, "status", None) == DocumentStatus.archived
    level: AccessLevel = "none"
    if user.role in _ADMIN_ROLES or user.id == resource.owner_id:
        level = "manage"
    elif user.role == UserRole.manager and user.department_id == resource.department_id and not private:
        level = "manage"

    if private or archived:
        return level

    explicit = _explicit_grant(user, grants)
    if explicit is not None:
        level = _higher(level, explicit)
    return _higher(level, _visibility_default(user, resource))


def _explicit_grant(user: User, grants: Sequence[Grant]) -> AccessLevel | None:
    best: AccessLevel | None = None
    for grant in grants:
        matches_user = grant.principal_type == PrincipalType.user and grant.principal_id == user.id
        matches_department = (
            grant.principal_type == PrincipalType.department and grant.principal_id == user.department_id
        )
        if not matches_user and not matches_department:
            continue
        granted: AccessLevel = "edit" if grant.access == AccessGrant.edit else "view"
        best = granted if best is None else _higher(best, granted)
    return best


def _visibility_default(user: User, resource: Resource) -> AccessLevel:
    if user.role == UserRole.guest:
        return "none"
    if resource.visibility == Visibility.department and user.department_id == resource.department_id:
        return "edit" if resource.default_access == AccessGrant.edit else "view"
    if resource.visibility == Visibility.organization:
        return "edit" if resource.default_access == AccessGrant.edit else "view"
    return "none"


def _open_access(entity: Folder | Document | type[Folder] | type[Document], permission_model, user: User):
    return or_(
        _owner(entity, user),
        _manager(entity, user),
        _grant_exists(permission_model, entity, PrincipalType.user, user.id),
        _grant_exists(permission_model, entity, PrincipalType.department, user.department_id),
        _visibility_default_sql(entity, user),
    )


def _visibility_default_sql(entity, user: User):
    if user.role == UserRole.guest:
        return sql_false()
    return or_(
        and_(entity.visibility == Visibility.department, entity.department_id == user.department_id),
        entity.visibility == Visibility.organization,
    )


def _grant_exists(permission_model, entity, principal_type: PrincipalType, principal_id: UUID):
    return exists(
        select(permission_model.id).where(
            permission_model.resource_id == entity.id,
            permission_model.principal_type == principal_type,
            permission_model.principal_id == principal_id,
        )
    )


def _like_children(path_column):
    """LIKE pattern for descendants of a path. Escapes \\, %, and _ in the path."""
    escaped = path_column
    for character, replacement in (("\\", "\\\\"), ("%", "\\%"), ("_", "\\_")):
        escaped = func.replace(escaped, character, replacement)
    return escaped.concat("/%")


def _owner(entity, user: User):
    return entity.owner_id == user.id


def _manager(entity, user: User):
    if user.role != UserRole.manager:
        return sql_false()
    return entity.department_id == user.department_id


def _query_can_view(user: User, scopes: AbstractSet[str] | None) -> bool:
    return user.is_active and _RANK[scope_ceiling(_resolved_scopes(user, scopes))] >= _RANK["view"]


def _resolved_scopes(user: User, scopes: AbstractSet[str] | None) -> AbstractSet[str]:
    if scopes is None:
        return scopes_for_role(user.role)
    return scopes


def _higher(current: AccessLevel, new: AccessLevel) -> AccessLevel:
    return new if _RANK[new] > _RANK[current] else current


def _lower(current: AccessLevel, new: AccessLevel) -> AccessLevel:
    return current if _RANK[current] <= _RANK[new] else new
