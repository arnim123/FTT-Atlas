from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator

from app.core.enums import AccessGrant, Visibility
from app.schemas.permissions import AccessName

_EXAMPLE_ID = "11111111-1111-4111-8111-111111111111"
_PARENT_ID = "22222222-2222-4222-8222-222222222222"
_DEPARTMENT_ID = "33333333-3333-4333-8333-333333333333"


def _strip(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class FolderCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Policies",
                    "parent_id": _PARENT_ID,
                    "department_id": _DEPARTMENT_ID,
                    "description": "Department policies",
                    "visibility": "department",
                    "default_access": "view",
                }
            ]
        }
    )

    name: str = Field(min_length=1, max_length=200, examples=["Policies"])
    parent_id: UUID | None = None
    department_id: UUID
    description: str | None = Field(default=None, max_length=2000)
    visibility: Visibility = Visibility.department
    default_access: AccessGrant = AccessGrant.view

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return _strip(value)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return _blank_to_none(value)


class FolderUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "Policies and handbooks"}]})

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return _strip(value)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def at_least_one(self) -> "FolderUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide a field to update.")
        return self


class FolderMove(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"parent_id": _PARENT_ID}]})

    parent_id: UUID | None = Field(description="Destination folder. Null moves the folder to the top level.")


class FolderRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": _EXAMPLE_ID,
                    "name": "Policies",
                    "parent_id": _PARENT_ID,
                    "path": f"/{_PARENT_ID}/{_EXAMPLE_ID}",
                    "depth": 1,
                    "department_id": _DEPARTMENT_ID,
                    "owner_id": "44444444-4444-4444-8444-444444444444",
                    "visibility": "department",
                    "default_access": "view",
                    "description": "Department policies",
                    "sort_order": 0,
                    "my_access": "manage",
                    "created_at": "2026-11-16T09:00:00Z",
                    "updated_at": "2026-11-16T09:00:00Z",
                }
            ]
        }
    )

    id: UUID
    name: str
    parent_id: UUID | None
    path: str
    depth: int
    department_id: UUID
    owner_id: UUID
    visibility: Visibility
    default_access: AccessGrant
    description: str | None
    sort_order: int
    my_access: AccessName
    created_at: datetime
    updated_at: datetime


class FolderNode(BaseModel):
    """One folder in the tree. Path-only ancestors keep their name and drop every other detail."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": _PARENT_ID,
                    "name": "Company",
                    "parent_id": None,
                    "path_only": False,
                    "document_count": 2,
                    "my_access": "view",
                    "children": [
                        {
                            "id": _EXAMPLE_ID,
                            "name": "Policies",
                            "parent_id": _PARENT_ID,
                            "path_only": True,
                            "document_count": 1,
                            "my_access": "none",
                            "children": [],
                        }
                    ],
                }
            ]
        }
    )

    id: UUID
    name: str
    parent_id: UUID | None = None
    path_only: bool
    document_count: int
    my_access: AccessName
    children: list["FolderNode"] = Field(default_factory=list)
    description: str | None = None
    department_id: UUID | None = None
    owner_id: UUID | None = None
    visibility: Visibility | None = None
    default_access: AccessGrant | None = None
    depth: int | None = None
    sort_order: int | None = None
    path: str | None = None

    @model_serializer(mode="wrap")
    def strip_path_only_details(self, handler, info):
        data = handler(self)
        if self.path_only:
            for key in (
                "description",
                "department_id",
                "owner_id",
                "visibility",
                "default_access",
                "depth",
                "sort_order",
                "path",
            ):
                data.pop(key, None)
        return data


FolderNode.model_rebuild()


def to_folder_read(folder, my_access: AccessName) -> FolderRead:
    return FolderRead(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        path=folder.path,
        depth=folder.depth,
        department_id=folder.department_id,
        owner_id=folder.owner_id,
        visibility=folder.visibility,
        default_access=folder.default_access,
        description=folder.description,
        sort_order=folder.sort_order,
        my_access=my_access,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )
