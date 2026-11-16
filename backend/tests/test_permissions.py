"""Table-driven access rules and the SQL filters that implement them."""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.enums import AccessGrant, DocumentStatus, PrincipalType, UserRole, Visibility
from app.core.principal import SCOPE_DOCS_READ, SCOPE_DOCS_WRITE, scopes_for_role
from app.models.document import Document
from app.models.folder import Folder
from app.models.user import User
from app.permissions.engine import (
    access_level,
    accessible_documents_query,
    accessible_folders_query,
    can,
    direct_folder_access_query,
)
from tests.library import add_category, add_document, add_folder

_RANK = {"none": 0, "view": 1, "edit": 2, "manage": 3}
_ROLES = ("super_admin", "admin", "manager", "employee", "guest")
_VISIBILITIES = ("private", "department", "organization", "custom")
_ACTIONS = ("view", "edit", "manage")
_SCOPES = {
    "none": frozenset(),
    "read": frozenset({SCOPE_DOCS_READ}),
    "write": frozenset({SCOPE_DOCS_WRITE}),
    "read_write": frozenset({SCOPE_DOCS_READ, SCOPE_DOCS_WRITE}),
}
_RELATIONSHIPS = ("owner", "same_dept", "other_dept", "user_granted", "dept_granted", "inactive", "archived")


def _higher(current: str, new: str) -> str:
    return new if _RANK[new] > _RANK[current] else current


def _lower(current: str, new: str) -> str:
    return current if _RANK[current] <= _RANK[new] else new


def _ceiling(scope_name: str) -> str:
    if scope_name in {"write", "read_write"}:
        return "manage"
    if scope_name == "read":
        return "view"
    return "none"


def _spec_level(role: str, visibility: str, relationship: str, default_access: str, grant_access: str) -> str:
    """Independent reading of the permission rules, used as the matrix oracle."""
    if relationship == "inactive":
        return "none"
    is_owner = relationship == "owner"
    same_department = relationship in {"owner", "same_dept", "archived"}
    private = visibility == "private"
    archived = relationship == "archived"
    if role in {"super_admin", "admin"} or is_owner:
        level = "manage"
    elif role == "manager" and same_department and not private:
        level = "manage"
    else:
        level = "none"
    if private or archived:
        return level
    if relationship in {"user_granted", "dept_granted"}:
        level = _higher(level, grant_access)
    if role != "guest":
        if visibility == "department" and same_department:
            level = _higher(level, default_access)
        elif visibility == "organization":
            level = _higher(level, default_access)
    return level


def _case(role, visibility, relationship, action, scope_name, default_access, grant_access):
    dept_a, dept_b = uuid4(), uuid4()
    owner_id, user_id = uuid4(), uuid4()
    same = relationship in {"owner", "same_dept", "archived", "inactive"}
    user = User(
        id=owner_id if relationship == "owner" else user_id,
        email=f"{role}@company.com",
        name=role,
        role=UserRole(role),
        department_id=dept_a if same else dept_b,
        is_active=relationship != "inactive",
        is_bot=False,
    )
    resource = SimpleNamespace(
        owner_id=owner_id,
        department_id=dept_a,
        visibility=Visibility(visibility),
        default_access=AccessGrant(default_access),
        deleted_at=None,
        status=DocumentStatus.archived if relationship == "archived" else DocumentStatus.active,
    )
    grants = []
    if relationship == "user_granted":
        grants.append(SimpleNamespace(principal_type=PrincipalType.user, principal_id=user.id, access=AccessGrant(grant_access)))
    if relationship == "dept_granted":
        grants.append(
            SimpleNamespace(principal_type=PrincipalType.department, principal_id=user.department_id, access=AccessGrant(grant_access))
        )
    expected_level = _lower(_spec_level(role, visibility, relationship, default_access, grant_access), _ceiling(scope_name))
    expected = _RANK[expected_level] >= _RANK[action]
    actual = can(user, resource, action, grants, _SCOPES[scope_name])
    return expected, actual, f"{role} {visibility} {relationship} default={default_access} grant={grant_access} {action} {scope_name}"


@pytest.mark.parametrize("relationship", _RELATIONSHIPS)
def test_permission_matrix(relationship):
    failures = []
    grant_levels = ("view", "edit") if relationship in {"user_granted", "dept_granted"} else ("view",)
    for role in _ROLES:
        for visibility in _VISIBILITIES:
            for action in _ACTIONS:
                for scope_name in _SCOPES:
                    for default_access in ("view", "edit"):
                        for grant_access in grant_levels:
                            expected, actual, label = _case(
                                role, visibility, relationship, action, scope_name, default_access, grant_access
                            )
                            if expected is not actual:
                                failures.append(f"{label}: expected {expected} got {actual}")
                            if len(failures) >= 12:
                                break
    assert not failures, "\n".join(failures)


def test_rules_do_not_touch_the_database():
    source = Path("app/permissions/engine.py").read_text()
    assert "session.execute" not in source
    assert "Session(" not in source


def test_golden_access_rules():
    dept_a, dept_b = uuid4(), uuid4()
    owner_id = uuid4()

    def user(role, department, *, active=True, user_id=None):
        return User(
            id=user_id or uuid4(),
            email=f"{role.value}@company.com",
            name=role.value,
            role=role,
            department_id=department,
            is_active=active,
            is_bot=False,
        )

    def resource(visibility, *, owner=owner_id, department=dept_a, default=AccessGrant.view, status=DocumentStatus.active, deleted_at=None):
        return SimpleNamespace(
            owner_id=owner,
            department_id=department,
            visibility=visibility,
            default_access=default,
            status=status,
            deleted_at=deleted_at,
        )

    def grant(principal_type, principal_id, access):
        return SimpleNamespace(principal_type=principal_type, principal_id=principal_id, access=access)

    inactive_admin = user(UserRole.super_admin, dept_a, active=False, user_id=owner_id)
    assert can(inactive_admin, resource(Visibility.organization), "view", (), _SCOPES["read_write"]) is False

    admin = user(UserRole.admin, dept_b)
    private = resource(Visibility.private)
    assert can(admin, private, "manage", (), _SCOPES["write"]) is True
    assert can(admin, private, "edit", (), _SCOPES["read"]) is False
    assert can(admin, private, "view", (), _SCOPES["read"]) is True
    assert access_level(admin, private, (), _SCOPES["read"]) == "view"

    employee = user(UserRole.employee, dept_a, user_id=owner_id)
    assert can(employee, private, "manage", (), _SCOPES["write"]) is True
    assert can(employee, private, "manage", (), _SCOPES["read"]) is False
    assert can(employee, private, "view", (), _SCOPES["none"]) is False

    peer = user(UserRole.employee, dept_a)
    assert can(peer, private, "view", (), _SCOPES["write"]) is False
    edit_grant = [grant(PrincipalType.user, peer.id, AccessGrant.edit)]
    assert can(peer, private, "view", edit_grant, _SCOPES["write"]) is False

    manager = user(UserRole.manager, dept_a)
    assert can(manager, private, "view", (), _SCOPES["write"]) is False
    departmental = resource(Visibility.department)
    assert can(manager, departmental, "manage", (), _SCOPES["write"]) is True
    other_manager = user(UserRole.manager, dept_b)
    assert can(other_manager, private, "view", (), _SCOPES["write"]) is False

    custom = resource(Visibility.custom)
    assert can(peer, custom, "edit", edit_grant, _SCOPES["write"]) is True
    assert can(peer, custom, "edit", edit_grant, _SCOPES["read"]) is False
    assert can(peer, custom, "view", edit_grant, _SCOPES["read"]) is True
    view_grant = [grant(PrincipalType.user, peer.id, AccessGrant.view)]
    assert can(peer, custom, "edit", view_grant, _SCOPES["write"]) is False
    assert can(peer, custom, "view", (), _SCOPES["write"]) is False

    guest = user(UserRole.guest, dept_b)
    org_edit = resource(Visibility.organization, default=AccessGrant.edit)
    assert can(guest, org_edit, "view", (), _SCOPES["read"]) is False
    guest_edit = [grant(PrincipalType.user, guest.id, AccessGrant.edit)]
    assert can(guest, custom, "edit", guest_edit, _SCOPES["write"]) is True
    assert can(guest, custom, "edit", guest_edit, _SCOPES["read"]) is False
    guest_view = [grant(PrincipalType.user, guest.id, AccessGrant.view)]
    assert can(guest, custom, "view", guest_view, _SCOPES["read"]) is True
    same_guest = user(UserRole.guest, dept_a)
    assert can(same_guest, resource(Visibility.department, default=AccessGrant.edit), "view", (), _SCOPES["read"]) is False
    dept_grant = [grant(PrincipalType.department, guest.department_id, AccessGrant.edit)]
    assert can(guest, custom, "edit", dept_grant, _SCOPES["write"]) is True

    assert can(peer, resource(Visibility.department, default=AccessGrant.view), "view", (), _SCOPES["write"]) is True
    assert can(peer, resource(Visibility.department, default=AccessGrant.view), "edit", (), _SCOPES["write"]) is False
    assert can(peer, resource(Visibility.department, default=AccessGrant.edit), "edit", (), _SCOPES["write"]) is True
    outsider = user(UserRole.employee, dept_b)
    assert can(outsider, resource(Visibility.organization, default=AccessGrant.view), "view", (), _SCOPES["write"]) is True
    assert can(outsider, resource(Visibility.organization, default=AccessGrant.view), "edit", (), _SCOPES["write"]) is False
    assert can(outsider, resource(Visibility.organization, default=AccessGrant.edit), "edit", (), _SCOPES["write"]) is True
    dept_view = [grant(PrincipalType.department, outsider.department_id, AccessGrant.view)]
    assert can(outsider, custom, "view", dept_view, _SCOPES["read"]) is True
    assert can(outsider, custom, "edit", dept_view, _SCOPES["write"]) is False
    raised = [grant(PrincipalType.user, peer.id, AccessGrant.edit)]
    assert can(peer, resource(Visibility.department, default=AccessGrant.view), "edit", raised, _SCOPES["write"]) is True

    archived = resource(Visibility.department, status=DocumentStatus.archived)
    assert can(peer, archived, "view", edit_grant, _SCOPES["write"]) is False
    assert can(employee, archived, "manage", (), _SCOPES["write"]) is True
    assert can(manager, archived, "manage", (), _SCOPES["write"]) is True
    assert can(manager, resource(Visibility.private, status=DocumentStatus.archived), "view", (), _SCOPES["write"]) is False
    assert can(other_manager, archived, "view", (), _SCOPES["write"]) is False
    assert can(admin, archived, "manage", (), _SCOPES["read"]) is False
    assert can(admin, archived, "view", (), _SCOPES["read"]) is True
    assert can(admin, resource(Visibility.organization, deleted_at=object()), "view", (), _SCOPES["write"]) is False

    folder = SimpleNamespace(
        owner_id=owner_id,
        department_id=dept_a,
        visibility=Visibility.department,
        default_access=AccessGrant.view,
        deleted_at=None,
    )
    assert can(manager, folder, "manage", (), _SCOPES["write"]) is True
    folder.visibility = Visibility.private
    assert can(manager, folder, "view", (), _SCOPES["write"]) is False


def test_query_filters_match_can(db_session, org):
    category = add_category(db_session)
    owner = org.employee
    root = add_folder(db_session, name="Company", owner=org.admin, department=org.product, visibility=Visibility.organization)
    private_folder = add_folder(
        db_session,
        name="Secret",
        owner=owner,
        department=org.product,
        parent=root,
        visibility=Visibility.private,
    )
    shared_child = add_folder(
        db_session,
        name="Handbook",
        owner=owner,
        department=org.product,
        parent=private_folder,
        visibility=Visibility.organization,
    )
    custom_folder = add_folder(
        db_session,
        name="Deal",
        owner=owner,
        department=org.product,
        parent=root,
        visibility=Visibility.custom,
        grants=[(PrincipalType.user, org.sales_employee.id, AccessGrant.view)],
    )
    documents = []
    grants = {}
    for visibility in Visibility:
        for status in (DocumentStatus.active, DocumentStatus.archived):
            document = add_document(
                db_session,
                name=f"{visibility.value}-{status.value}",
                folder=root,
                owner=owner,
                department=org.product,
                category=category,
                visibility=visibility,
                status=status,
            )
            documents.append(document)
            grants[document.id] = []
        granted = add_document(
            db_session,
            name=f"{visibility.value}-user-grant",
            folder=root,
            owner=owner,
            department=org.product,
            category=category,
            visibility=visibility,
            grants=[(PrincipalType.user, org.sales_employee.id, AccessGrant.edit)],
        )
        documents.append(granted)
        grants[granted.id] = list(
            db_session.scalars(select(Document).where(Document.id == granted.id))
        ) and []
        from app.models import DocumentPermission

        grants[granted.id] = list(
            db_session.scalars(select(DocumentPermission).where(DocumentPermission.resource_id == granted.id))
        )
        department_granted = add_document(
            db_session,
            name=f"{visibility.value}-dept-grant",
            folder=shared_child,
            owner=owner,
            department=org.product,
            category=category,
            visibility=visibility,
            grants=[(PrincipalType.department, org.sales.id, AccessGrant.edit)],
        )
        documents.append(department_granted)
        grants[department_granted.id] = list(
            db_session.scalars(select(DocumentPermission).where(DocumentPermission.resource_id == department_granted.id))
        )
    deleted = add_document(
        db_session,
        name="deleted",
        folder=root,
        owner=owner,
        department=org.product,
        category=category,
        visibility=Visibility.organization,
        deleted=True,
    )
    documents.append(deleted)
    grants[deleted.id] = []
    for document in documents:
        grants.setdefault(document.id, [])

    users = [
        org.super_admin,
        org.admin,
        org.manager,
        org.sales_manager,
        owner,
        org.sales_employee,
        org.guest,
        org.deactivated,
    ]
    folders = [root, private_folder, shared_child, custom_folder]
    folder_grants = {folder.id: [] for folder in folders}
    from app.models import FolderPermission

    for row in db_session.scalars(select(FolderPermission)).all():
        folder_grants.setdefault(row.resource_id, []).append(row)

    for person in users:
        scopes = scopes_for_role(person.role)
        visible_ids = set(db_session.scalars(select(Document.id).where(accessible_documents_query(person, scopes))))
        for document in documents:
            expected = can(person, document, "view", grants[document.id], scopes)
            assert (document.id in visible_ids) is expected, f"{person.email} {document.name}"
        direct_ids = set(db_session.scalars(select(Folder.id).where(direct_folder_access_query(person, scopes))))
        for folder in folders:
            assert (folder.id in direct_ids) is can(person, folder, "view", folder_grants[folder.id], scopes), folder.name
        listed_ids = set(db_session.scalars(select(Folder.id).where(accessible_folders_query(person, scopes))))
        for folder in folders:
            assert (folder.id in listed_ids) is _folder_visible(person, folder, folders, documents, folder_grants, grants), folder.name
        assert set(db_session.scalars(select(Document.id).where(accessible_documents_query(person, frozenset())))) == set()

    assert deleted.id not in set(db_session.scalars(select(Document.id).where(accessible_documents_query(org.admin))))
    read_only = set(db_session.scalars(select(Document.id).where(accessible_documents_query(owner, _SCOPES["read"]))))
    write_only = set(db_session.scalars(select(Document.id).where(accessible_documents_query(owner, _SCOPES["write"]))))
    assert read_only == write_only
    assert private_folder.id not in set(
        db_session.scalars(select(Folder.id).where(direct_folder_access_query(org.sales_employee)))
    )
    assert private_folder.id in set(db_session.scalars(select(Folder.id).where(accessible_folders_query(org.sales_employee))))


def _folder_visible(person, folder, folders, documents, folder_grants, document_grants) -> bool:
    if folder.deleted_at is not None or not person.is_active:
        return False
    scopes = scopes_for_role(person.role)
    if not scopes:
        return False
    if can(person, folder, "view", folder_grants.get(folder.id, ()), scopes):
        return True
    for other in folders:
        if other.deleted_at is None and other.path.startswith(folder.path + "/"):
            if can(person, other, "view", folder_grants.get(other.id, ()), scopes):
                return True
    homes = {item.id: item for item in folders}
    for document in documents:
        home = homes.get(document.folder_id)
        if home is None or home.deleted_at is not None:
            continue
        inside = home.id == folder.id or home.path.startswith(folder.path + "/")
        if inside and can(person, document, "view", document_grants.get(document.id, ()), scopes):
            return True
    return False
