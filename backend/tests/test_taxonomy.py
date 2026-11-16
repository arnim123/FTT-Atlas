from uuid import UUID

import pytest

from app.core.enums import AccessGrant, PrincipalType, SourceType, Visibility
from app.models import Document, DocumentTag, Folder, FolderPermission
from tests.helpers import CSRF, assert_error, login


@pytest.mark.parametrize("path", ["/api/v1/departments", "/api/v1/categories", "/api/v1/tags"])
def test_every_authenticated_role_can_read_taxonomy(api, org, path):
    assert_error(api.get(path), 401, "UNAUTHENTICATED")
    for email in (org.guest.email, org.employee.email, org.manager.email, org.admin.email, org.super_admin.email):
        login(api, email)
        response = api.get(path)
        assert response.status_code == 200, response.text
        api.cookies.clear()


def test_only_admins_can_change_taxonomy(api, org):
    for email in (org.guest.email, org.employee.email, org.manager.email):
        login(api, email)
        assert_error(_create_department(api, "Legal", "legal"), 403, "FORBIDDEN")
        assert_error(api.post("/api/v1/categories", json={"name": "Notes"}, headers=CSRF), 403, "FORBIDDEN")
        assert_error(api.post("/api/v1/tags", json={"name": "Draft"}, headers=CSRF), 403, "FORBIDDEN")
        api.cookies.clear()


def test_department_crud_and_conflicts(api, org):
    login(api, org.admin.email)
    created = _create_department(api, " Legal ", "Legal", " Counsel ")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Legal"
    assert body["code"] == "legal"
    assert body["description"] == "Counsel"

    fetched = api.get(f"/api/v1/departments/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["code"] == "legal"

    updated = api.patch(f"/api/v1/departments/{body['id']}", json={"description": ""}, headers=CSRF)
    assert updated.status_code == 200, updated.text
    assert updated.json()["description"] is None

    assert_error(_create_department(api, "product", "other"), 409, "NAME_EXISTS")
    assert_error(_create_department(api, "Other", "product"), 409, "CODE_EXISTS")
    assert api.delete(f"/api/v1/departments/{body['id']}", headers=CSRF).status_code == 204
    assert_error(api.get(f"/api/v1/departments/{body['id']}"), 404, "NOT_FOUND")


def test_deleting_a_department_in_use_reports_counts(api, org, db_session):
    login(api, org.admin.email)
    response = api.delete(f"/api/v1/departments/{org.product.id}", headers=CSRF)
    detail = assert_error(response, 409, "IN_USE")
    assert detail["usage"]["users"] >= 1
    assert "documents" not in detail["usage"]

    empty = _create_department(api, "Legal", "legal")
    assert empty.status_code == 201, empty.text
    folder = Folder(
        name="Notes",
        path=f"/notes-{org.product.id}",
        depth=0,
        department_id=org.product.id,
        owner_id=org.admin.id,
        visibility=Visibility.organization,
        default_access=AccessGrant.view,
    )
    db_session.add(folder)
    db_session.flush()
    db_session.add(
        FolderPermission(
            resource_id=folder.id,
            principal_type=PrincipalType.department,
            principal_id=UUID(empty.json()["id"]),
            access=AccessGrant.view,
            created_by=org.admin.id,
        )
    )
    db_session.flush()
    blocked = api.delete(f"/api/v1/departments/{empty.json()['id']}", headers=CSRF)
    usage = assert_error(blocked, 409, "IN_USE")["usage"]
    assert usage == {"permissions": 1}


def test_category_and_tag_crud_block_rows_in_use(api, org, db_session):
    login(api, org.super_admin.email)
    category = api.post("/api/v1/categories", json={"name": " Notes ", "description": "Scratch"}, headers=CSRF)
    assert category.status_code == 201, category.text
    assert category.json()["name"] == "Notes"
    tag = api.post("/api/v1/tags", json={"name": "Draft"}, headers=CSRF)
    assert tag.status_code == 201, tag.text

    renamed = api.patch(f"/api/v1/categories/{category.json()['id']}", json={"name": "Scratch"}, headers=CSRF)
    assert renamed.status_code == 200, renamed.text
    duplicate = api.post("/api/v1/categories", json={"name": "scratch"}, headers=CSRF)
    assert_error(duplicate, 409, "NAME_EXISTS")

    folder = Folder(
        name="Notes",
        path=f"/notes-{org.product.id}",
        depth=0,
        department_id=org.product.id,
        owner_id=org.admin.id,
        visibility=Visibility.organization,
        default_access=AccessGrant.view,
    )
    db_session.add(folder)
    db_session.flush()
    document = Document(
        name="Notes",
        folder_id=folder.id,
        category_id=UUID(category.json()["id"]),
        department_id=org.product.id,
        owner_id=org.admin.id,
        source_type=SourceType.txt,
        visibility=Visibility.organization,
        default_access=AccessGrant.view,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(DocumentTag(document_id=document.id, tag_id=UUID(tag.json()["id"])))
    db_session.flush()

    category_block = api.delete(f"/api/v1/categories/{category.json()['id']}", headers=CSRF)
    assert assert_error(category_block, 409, "IN_USE")["usage"] == {"documents": 1}
    tag_block = api.delete(f"/api/v1/tags/{tag.json()['id']}", headers=CSRF)
    assert assert_error(tag_block, 409, "IN_USE")["usage"] == {"documents": 1}

    free = api.post("/api/v1/tags", json={"name": "Unused"}, headers=CSRF)
    assert free.status_code == 201, free.text
    assert api.delete(f"/api/v1/tags/{free.json()['id']}", headers=CSRF).status_code == 204
    assert_error(api.get(f"/api/v1/tags/{free.json()['id']}"), 404, "NOT_FOUND")

    login(api, org.guest.email)
    assert api.get(f"/api/v1/categories/{category.json()['id']}").status_code == 200
    assert api.get("/api/v1/tags").json()[0]["name"]


def _create_department(api, name: str, code: str, description: str | None = None):
    body = {"name": name, "code": code}
    if description is not None:
        body["description"] = description
    return api.post("/api/v1/departments", json=body, headers=CSRF)
