from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.principal import Principal, get_principal, require_roles
from app.schemas.taxonomy import DepartmentCreate, DepartmentRead, DepartmentUpdate, TaxonomyCreate, TaxonomyRead, TaxonomyUpdate
from app.services import taxonomy as taxonomy_service

departments_router = APIRouter()
categories_router = APIRouter()
tags_router = APIRouter()

ADMINS = Depends(require_roles(UserRole.super_admin, UserRole.admin))


@departments_router.get("", response_model=list[DepartmentRead])
def list_departments(principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> list:
    return taxonomy_service.list_departments(session, principal)


@departments_router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    body: DepartmentCreate,
    principal: Principal = ADMINS,
    session: Session = Depends(get_db),
) -> DepartmentRead:
    return taxonomy_service.create_department(session, principal, body)


@departments_router.get("/{department_id}", response_model=DepartmentRead)
def get_department(
    department_id: UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> DepartmentRead:
    return taxonomy_service.get_department(session, principal, department_id)


@departments_router.patch("/{department_id}", response_model=DepartmentRead)
def update_department(
    department_id: UUID,
    body: DepartmentUpdate,
    principal: Principal = ADMINS,
    session: Session = Depends(get_db),
) -> DepartmentRead:
    return taxonomy_service.update_department(session, principal, department_id, body)


@departments_router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: UUID,
    principal: Principal = ADMINS,
    session: Session = Depends(get_db),
) -> None:
    taxonomy_service.delete_department(session, principal, department_id)


@categories_router.get("", response_model=list[TaxonomyRead])
def list_categories(principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> list:
    return taxonomy_service.list_categories(session, principal)


@categories_router.post("", response_model=TaxonomyRead, status_code=status.HTTP_201_CREATED)
def create_category(body: TaxonomyCreate, principal: Principal = ADMINS, session: Session = Depends(get_db)) -> TaxonomyRead:
    return taxonomy_service.create_category(session, principal, body)


@categories_router.get("/{category_id}", response_model=TaxonomyRead)
def get_category(category_id: UUID, principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> TaxonomyRead:
    return taxonomy_service.get_category(session, principal, category_id)


@categories_router.patch("/{category_id}", response_model=TaxonomyRead)
def update_category(
    category_id: UUID,
    body: TaxonomyUpdate,
    principal: Principal = ADMINS,
    session: Session = Depends(get_db),
) -> TaxonomyRead:
    return taxonomy_service.update_category(session, principal, category_id, body)


@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: UUID, principal: Principal = ADMINS, session: Session = Depends(get_db)) -> None:
    taxonomy_service.delete_category(session, principal, category_id)


@tags_router.get("", response_model=list[TaxonomyRead])
def list_tags(principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> list:
    return taxonomy_service.list_tags(session, principal)


@tags_router.post("", response_model=TaxonomyRead, status_code=status.HTTP_201_CREATED)
def create_tag(body: TaxonomyCreate, principal: Principal = ADMINS, session: Session = Depends(get_db)) -> TaxonomyRead:
    return taxonomy_service.create_tag(session, principal, body)


@tags_router.get("/{tag_id}", response_model=TaxonomyRead)
def get_tag(tag_id: UUID, principal: Principal = Depends(get_principal), session: Session = Depends(get_db)) -> TaxonomyRead:
    return taxonomy_service.get_tag(session, principal, tag_id)


@tags_router.patch("/{tag_id}", response_model=TaxonomyRead)
def update_tag(tag_id: UUID, body: TaxonomyUpdate, principal: Principal = ADMINS, session: Session = Depends(get_db)) -> TaxonomyRead:
    return taxonomy_service.update_tag(session, principal, tag_id, body)


@tags_router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: UUID, principal: Principal = ADMINS, session: Session = Depends(get_db)) -> None:
    taxonomy_service.delete_tag(session, principal, tag_id)
