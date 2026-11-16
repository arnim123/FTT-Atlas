from uuid import uuid4

import pytest

from app.core.principal import SCOPE_DOCS_READ, SCOPE_DOCS_WRITE
from app.models import Folder
from tests.helpers import CSRF, acting_as, assert_error, login
from tests.library import add_category, add_document

pytestmark = pytest.mark.usefixtures("org")


def _folder_body(org, name, parent_id=None, department=None, visibility="department", default_access="view"):
    return {
        "name": name,
        "parent_id": str(parent_id) if parent_id else None,
        "department_id": str((department or org.product).id),
        "visibility": visibility,
        "default_access": default_access,
    }


def test_folder_routes_require_auth_and_scopes(api, org):
    missing = uuid4()
    assert_error(api.get("/api/v1/folders/tree"), 401, "UNAUTHENTICATED")
    assert_error(api.post("/api/v1/folders", json=_folder_body(org, "Root")), 401, "UNAUTHENTICATED")
    assert_error(api.patch(f"/api/v1/folders/{missing}", json={"name": "X"}), 401, "UNAUTHENTICATED")
    assert_error(api.post(f"/api/v1/folders/{missing}/move", json={"parent_id": None}), 401, "UNAUTHENTICATED")
    assert_error(api.delete(f"/api/v1/folders/{missing}"), 401, "UNAUTHENTICATED")
    assert_error(api.get(f"/api/v1/folders/{missing}/permissions"), 401, "UNAUTHENTICATED")
    assert_error(api.put(f"/api/v1/folders/{missing}/permissions", json={"visibility": "private", "default_access": "view", "grants": []}), 401, "UNAUTHENTICATED")

    with acting_as(org.employee, {SCOPE_DOCS_READ}):
        assert_error(api.post("/api/v1/folders", json=_folder_body(org, "Root")), 403, "MISSING_SCOPE")
    with acting_as(org.employee, {SCOPE_DOCS_WRITE}):
        assert_error(api.get("/api/v1/folders/tree"), 403, "MISSING_SCOPE")


def test_create_rename_move_delete_and_hidden_folders(api, org, db_session):
    login(api, org.admin.email)
    root = api.post("/api/v1/folders", json=_folder_body(org, "Company", visibility="organization", default_access="edit"), headers=CSRF)
    assert root.status_code == 201, root.text
    root_id = root.json()["id"]
    assert root.json()["my_access"] == "manage"
    assert root.json()["depth"] == 0
    root_path = root.json()["path"]

    login(api, org.sales_employee.email)
    assert_error(api.post("/api/v1/folders", json=_folder_body(org, "Sales root", department=org.sales), headers=CSRF), 403, "FORBIDDEN")

    login(api, org.manager.email)
    managed = api.post("/api/v1/folders", json=_folder_body(org, "Plans"), headers=CSRF)
    assert managed.status_code == 201, managed.text

    login(api, org.employee.email)
    child = api.post(
        "/api/v1/folders",
        json=_folder_body(org, "Notes", parent_id=root_id, visibility="private"),
        headers=CSRF,
    )
    assert child.status_code == 201, child.text
    child_id = child.json()["id"]
    assert child.json()["path"].startswith(root_path + "/")
    assert child.json()["department_id"] == str(org.product.id)

    mismatch = api.post(
        "/api/v1/folders",
        json=_folder_body(org, "Wrong", parent_id=root_id, department=org.sales),
        headers=CSRF,
    )
    assert_error(mismatch, 422, "DEPARTMENT_MISMATCH")
    duplicate = api.post("/api/v1/folders", json=_folder_body(org, "notes", parent_id=root_id), headers=CSRF)
    assert_error(duplicate, 409, "NAME_EXISTS")

    login(api, org.sales_employee.email)
    assert_error(api.patch(f"/api/v1/folders/{child_id}", json={"name": "Stolen"}, headers=CSRF), 404, "NOT_FOUND")
    assert_error(api.get(f"/api/v1/folders/{child_id}/permissions"), 404, "NOT_FOUND")
    assert_error(api.delete(f"/api/v1/folders/{child_id}", headers=CSRF), 404, "NOT_FOUND")

    login(api, org.employee.email)
    renamed = api.patch(f"/api/v1/folders/{child_id}", json={"name": "Field notes"}, headers=CSRF)
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["path"] == child.json()["path"]

    login(api, org.admin.email)
    visible = api.post(
        "/api/v1/folders",
        json=_folder_body(org, "Shared", parent_id=root_id, visibility="organization", default_access="edit"),
        headers=CSRF,
    )
    assert visible.status_code == 201, visible.text
    shared_id = visible.json()["id"]

    login(api, org.employee.email)
    nested = api.post("/api/v1/folders", json=_folder_body(org, "Nested", parent_id=child_id, visibility="department"), headers=CSRF)
    assert nested.status_code == 201, nested.text
    nested_id = nested.json()["id"]
    cycle = api.post(f"/api/v1/folders/{child_id}/move", json={"parent_id": nested_id}, headers=CSRF)
    assert_error(cycle, 409, "CYCLE")
    db_session.expire_all()
    assert str(db_session.get(Folder, child_id).parent_id) == root_id

    moved = api.post(f"/api/v1/folders/{child_id}/move", json={"parent_id": shared_id}, headers=CSRF)
    assert moved.status_code == 200, moved.text
    db_session.expire_all()
    child_row = db_session.get(Folder, child_id)
    nested_row = db_session.get(Folder, nested_id)
    shared_row = db_session.get(Folder, shared_id)
    assert child_row.path == f"{shared_row.path}/{child_row.id}"
    assert nested_row.path == f"{child_row.path}/{nested_row.id}"
    assert nested_row.depth == shared_row.depth + 2

    category = add_category(db_session, "Folder guides")
    add_document(
        db_session,
        name="Kept",
        folder=nested_row,
        owner=org.employee,
        department=org.product,
        category=category,
        visibility=Visibility_department(),
    )
    blocked = api.delete(f"/api/v1/folders/{child_id}", headers=CSRF)
    assert_error(blocked, 409, "FOLDER_NOT_EMPTY")
    assert db_session.get(Folder, child_id).deleted_at is None

    empty = api.post("/api/v1/folders", json=_folder_body(org, "Empty", parent_id=shared_id), headers=CSRF)
    assert empty.status_code == 201, empty.text
    removed = api.delete(f"/api/v1/folders/{empty.json()['id']}", headers=CSRF)
    assert removed.status_code == 204, removed.text
    assert_error(api.get(f"/api/v1/folders/{empty.json()['id']}/permissions"), 404, "NOT_FOUND")


def Visibility_department():
    from app.core.enums import Visibility

    return Visibility.department


def test_view_without_edit_is_forbidden_and_guests_are_hidden(api, org):
    login(api, org.admin.email)
    created = api.post(
        "/api/v1/folders",
        json=_folder_body(org, "Published", visibility="organization", default_access="view"),
        headers=CSRF,
    )
    folder_id = created.json()["id"]
    login(api, org.sales_employee.email)
    listing = api.get(f"/api/v1/folders/{folder_id}/permissions")
    assert listing.status_code == 200, listing.text
    assert listing.json()["my_access"] == "view"
    assert_error(api.patch(f"/api/v1/folders/{folder_id}", json={"name": "Renamed"}, headers=CSRF), 403, "FORBIDDEN")
    login(api, org.guest.email)
    assert_error(api.get(f"/api/v1/folders/{folder_id}/permissions"), 404, "NOT_FOUND")
    assert_error(api.patch(f"/api/v1/folders/{folder_id}", json={"name": "Renamed"}, headers=CSRF), 403, "MISSING_SCOPE")


def test_tree_is_filtered_and_ancestors_are_name_only(api, org, db_session):
    login(api, org.admin.email)
    root = api.post(
        "/api/v1/folders",
        json=_folder_body(org, "Company", visibility="organization", default_access="view"),
        headers=CSRF,
    ).json()
    secret = api.post(
        "/api/v1/folders",
        json=_folder_body(org, "Secret", parent_id=root["id"], visibility="private"),
        headers=CSRF,
    ).json()
    category = add_category(db_session, "Tree guides")
    add_document(
        db_session,
        name="Public brief",
        folder=db_session.get(Folder, secret["id"]),
        owner=org.admin,
        department=org.product,
        category=category,
        visibility=Visibility_organization(),
    )

    login(api, org.sales_employee.email)
    tree = api.get("/api/v1/folders/tree")
    assert tree.status_code == 200, tree.text
    company = _find(tree.json(), root["id"])
    hidden = _find(tree.json(), secret["id"])
    assert company["path_only"] is False
    assert company["document_count"] >= 1
    assert hidden["path_only"] is True
    assert hidden["my_access"] == "none"
    assert hidden["name"] == "Secret"
    assert "visibility" not in hidden
    assert "owner_id" not in hidden
    assert_error(api.get(f"/api/v1/folders/{secret['id']}/permissions"), 404, "NOT_FOUND")

    login(api, org.guest.email)
    guest_tree = api.get("/api/v1/folders/tree").json()
    assert _find(guest_tree, secret["id"]) is None

    login(api, org.manager.email)
    assert_error(api.get(f"/api/v1/folders/{secret['id']}/permissions"), 404, "NOT_FOUND")


def Visibility_organization():
    from app.core.enums import Visibility

    return Visibility.organization


def test_folder_permissions_replace_atomically(api, org):
    login(api, org.employee.email)
    login(api, org.admin.email)
    created = api.post(
        "/api/v1/folders",
        json=_folder_body(org, "Shared deals", visibility="department", default_access="view"),
        headers=CSRF,
    )
    folder_id = created.json()["id"]
    original = {"visibility": "custom", "default_access": "view", "grants": [
        {"principal_type": "user", "principal_id": str(org.sales_employee.id), "access": "view"}
    ]}
    saved = api.put(f"/api/v1/folders/{folder_id}/permissions", json=original, headers=CSRF)
    assert saved.status_code == 200, saved.text
    assert saved.json()["grants"][0]["access"] == "view"

    rejected = api.put(
        f"/api/v1/folders/{folder_id}/permissions",
        json={"visibility": "private", "default_access": "edit", "grants": [
            {"principal_type": "user", "principal_id": str(uuid4()), "access": "edit"}
        ]},
        headers=CSRF,
    )
    assert_error(rejected, 422, "UNKNOWN_PRINCIPAL")
    current = api.get(f"/api/v1/folders/{folder_id}/permissions").json()
    assert current["visibility"] == "custom"
    assert current["grants"][0]["principal_id"] == str(org.sales_employee.id)

    login(api, org.sales_employee.email)
    assert api.get(f"/api/v1/folders/{folder_id}/permissions").status_code == 200
    assert_error(
        api.put(
            f"/api/v1/folders/{folder_id}/permissions",
            json={"visibility": "organization", "default_access": "edit", "grants": []},
            headers=CSRF,
        ),
        403,
        "FORBIDDEN",
    )


def test_folders_have_no_depth_cap(api, org):
    login(api, org.admin.email)
    parent = None
    last = None
    for index in range(8):
        response = api.post(
            "/api/v1/folders",
            json=_folder_body(org, f"Level {index}", parent_id=parent, visibility="organization", default_access="edit"),
            headers=CSRF,
        )
        assert response.status_code == 201, response.text
        last = response.json()
        parent = last["id"]
    assert last["depth"] == 7


def test_list_filter_is_the_only_folder_source(api, org, monkeypatch):
    from sqlalchemy import false as sql_false

    login(api, org.admin.email)
    api.post("/api/v1/folders", json=_folder_body(org, "Visible"), headers=CSRF)
    monkeypatch.setattr("app.services.folders.accessible_folders_query", lambda *args, **kwargs: sql_false())
    assert api.get("/api/v1/folders/tree").json() == []


def _find(nodes, folder_id):
    for node in nodes:
        if node["id"] == str(folder_id):
            return node
        found = _find(node["children"], folder_id)
        if found:
            return found
    return None
