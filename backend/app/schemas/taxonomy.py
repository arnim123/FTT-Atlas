import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_CODE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def _strip(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def _blank_to_none(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return _strip(value)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if not _CODE.fullmatch(cleaned):
                raise ValueError("Use a short lowercase code.")
            return cleaned
        return value

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return _blank_to_none(value)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return _strip(value)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if not _CODE.fullmatch(cleaned):
                raise ValueError("Use a short lowercase code.")
            return cleaned
        return value

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def at_least_one(self) -> "DepartmentUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide a field to update.")
        return self


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class TaxonomyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return _strip(value)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return _blank_to_none(value)


class TaxonomyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return _strip(value)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def at_least_one(self) -> "TaxonomyUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide a field to update.")
        return self


class TaxonomyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
