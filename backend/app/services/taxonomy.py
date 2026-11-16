"""Departments, categories, and tags.

Reads are available to every authenticated principal. Writes are admin and above,
and the routers enforce that before these functions run. Deletes of rows that are
still referenced return 409 with the counts that block them.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import PrincipalType
from app.core.errors import ApiError
from app.core.principal import Principal
from app.models.department import Department
from app.models.document import Document
from app.models.folder import Folder
from app.models.permission import DocumentPermission, FolderPermission
from app.models.taxonomy import Category, DocumentTag, Tag
from app.models.user import User
from app.schemas.taxonomy import DepartmentCreate, DepartmentUpdate, TaxonomyCreate, TaxonomyUpdate


def list_departments(session: Session, principal: Principal) -> list[Department]:
    _authenticated(principal)
    return list(session.scalars(select(Department).order_by(Department.name, Department.id)))


def get_department(session: Session, principal: Principal, department_id: UUID) -> Department:
    _authenticated(principal)
    return _department(session, department_id)


def create_department(session: Session, principal: Principal, payload: DepartmentCreate) -> Department:
    _authenticated(principal)
    _name_available(session, Department, payload.name, label="department")
    _code_available(session, payload.code)
    department = Department(name=payload.name, code=payload.code, description=payload.description)
    return _save(session, department, "A department with this name or code already exists.")


def update_department(session: Session, principal: Principal, department_id: UUID, payload: DepartmentUpdate) -> Department:
    _authenticated(principal)
    department = _department(session, department_id)
    if "name" in payload.model_fields_set and payload.name is not None:
        _name_available(session, Department, payload.name, label="department", exclude_id=department.id)
        department.name = payload.name
    if "code" in payload.model_fields_set and payload.code is not None:
        _code_available(session, payload.code, exclude_id=department.id)
        department.code = payload.code
    if "description" in payload.model_fields_set:
        department.description = payload.description
    return _save(session, department, "A department with this name or code already exists.")


def delete_department(session: Session, principal: Principal, department_id: UUID) -> None:
    _authenticated(principal)
    department = _department(session, department_id)
    usage = {
        "users": _count(session, User, User.department_id == department.id),
        "folders": _count(session, Folder, Folder.department_id == department.id),
        "documents": _count(session, Document, Document.department_id == department.id),
        "permissions": _permission_count(session, department.id),
    }
    _reject_in_use(usage, "Department is still in use.")
    _delete(session, department, "Department is still in use.")


def list_categories(session: Session, principal: Principal) -> list[Category]:
    _authenticated(principal)
    return list(session.scalars(select(Category).order_by(Category.name, Category.id)))


def get_category(session: Session, principal: Principal, category_id: UUID) -> Category:
    _authenticated(principal)
    return _category(session, category_id)


def create_category(session: Session, principal: Principal, payload: TaxonomyCreate) -> Category:
    _authenticated(principal)
    _name_available(session, Category, payload.name, label="category")
    return _save(session, Category(name=payload.name, description=payload.description), "A category with this name already exists.")


def update_category(session: Session, principal: Principal, category_id: UUID, payload: TaxonomyUpdate) -> Category:
    _authenticated(principal)
    category = _category(session, category_id)
    _apply_taxonomy(session, Category, category, payload, "category", "A category with this name already exists.")
    return category


def delete_category(session: Session, principal: Principal, category_id: UUID) -> None:
    _authenticated(principal)
    category = _category(session, category_id)
    usage = {"documents": _count(session, Document, Document.category_id == category.id)}
    _reject_in_use(usage, "Category is still in use.")
    _delete(session, category, "Category is still in use.")


def list_tags(session: Session, principal: Principal) -> list[Tag]:
    _authenticated(principal)
    return list(session.scalars(select(Tag).order_by(Tag.name, Tag.id)))


def get_tag(session: Session, principal: Principal, tag_id: UUID) -> Tag:
    _authenticated(principal)
    return _tag(session, tag_id)


def create_tag(session: Session, principal: Principal, payload: TaxonomyCreate) -> Tag:
    _authenticated(principal)
    _name_available(session, Tag, payload.name, label="tag")
    return _save(session, Tag(name=payload.name, description=payload.description), "A tag with this name already exists.")


def update_tag(session: Session, principal: Principal, tag_id: UUID, payload: TaxonomyUpdate) -> Tag:
    _authenticated(principal)
    tag = _tag(session, tag_id)
    _apply_taxonomy(session, Tag, tag, payload, "tag", "A tag with this name already exists.")
    return tag


def delete_tag(session: Session, principal: Principal, tag_id: UUID) -> None:
    _authenticated(principal)
    tag = _tag(session, tag_id)
    usage = {"documents": _count(session, DocumentTag, DocumentTag.tag_id == tag.id)}
    _reject_in_use(usage, "Tag is still in use.")
    _delete(session, tag, "Tag is still in use.")


def _apply_taxonomy(session: Session, model, row, payload: TaxonomyUpdate, label: str, conflict: str) -> None:
    if "name" in payload.model_fields_set and payload.name is not None:
        _name_available(session, model, payload.name, label=label, exclude_id=row.id)
        row.name = payload.name
    if "description" in payload.model_fields_set:
        row.description = payload.description
    _save(session, row, conflict)


def _authenticated(principal: Principal) -> None:
    if principal.user.id is None:
        raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.")


def _department(session: Session, department_id: UUID) -> Department:
    department = session.get(Department, department_id)
    if department is None:
        raise ApiError(404, "NOT_FOUND", "Department not found.")
    return department


def _category(session: Session, category_id: UUID) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise ApiError(404, "NOT_FOUND", "Category not found.")
    return category


def _tag(session: Session, tag_id: UUID) -> Tag:
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise ApiError(404, "NOT_FOUND", "Tag not found.")
    return tag


def _name_available(session: Session, model, name: str, *, label: str, exclude_id: UUID | None = None) -> None:
    statement = select(model.id).where(func.lower(model.name) == name.lower())
    if exclude_id is not None:
        statement = statement.where(model.id != exclude_id)
    if session.scalar(statement):
        raise ApiError(409, "NAME_EXISTS", f"A {label} with this name already exists.")


def _code_available(session: Session, code: str, exclude_id: UUID | None = None) -> None:
    statement = select(Department.id).where(Department.code == code)
    if exclude_id is not None:
        statement = statement.where(Department.id != exclude_id)
    if session.scalar(statement):
        raise ApiError(409, "CODE_EXISTS", "A department with this code already exists.")


def _count(session: Session, model, *criteria) -> int:
    return session.scalar(select(func.count()).select_from(model).where(*criteria)) or 0


def _permission_count(session: Session, department_id: UUID) -> int:
    documents = _count(
        session,
        DocumentPermission,
        DocumentPermission.principal_type == PrincipalType.department,
        DocumentPermission.principal_id == department_id,
    )
    folders = _count(
        session,
        FolderPermission,
        FolderPermission.principal_type == PrincipalType.department,
        FolderPermission.principal_id == department_id,
    )
    return documents + folders


def _reject_in_use(usage: dict[str, int], message: str) -> None:
    blocking = {key: count for key, count in usage.items() if count}
    if blocking:
        raise ApiError(409, "IN_USE", message, usage=blocking)


def _save(session: Session, row, conflict: str):
    session.add(row)
    _commit(session, 409, "CONFLICT", conflict)
    session.refresh(row)
    return row


def _delete(session: Session, row, message: str) -> None:
    session.delete(row)
    _commit(session, 409, "IN_USE", message)


def _commit(session: Session, status_code: int, code: str, message: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(status_code, code, message) from exc
