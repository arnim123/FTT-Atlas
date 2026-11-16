from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import UserRole
from app.models.department import Department
from app.models.user import User

AccountStatus = Literal["active", "invited", "deactivated"]


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)


class TestLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned:
            raise ValueError("Enter a valid email address.")
        return cleaned


class InviteUser(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: UserRole
    department_id: UUID
    is_bot: bool = False

    @field_validator("email")
    @classmethod
    def normalize(cls, value: str) -> str:
        cleaned = value.strip().lower()
        local, _, domain = cleaned.partition("@")
        if not local or "." not in domain or " " in cleaned:
            raise ValueError("Enter a valid email address.")
        return cleaned


class UpdateUser(BaseModel):
    role: UserRole | None = None
    department_id: UUID | None = None
    name: str | None = Field(default=None, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def at_least_one(self) -> "UpdateUser":
        if not self.model_fields_set:
            raise ValueError("Provide a role, department, or name.")
        if "name" in self.model_fields_set and not self.name:
            raise ValueError("Name cannot be empty.")
        return self


class DepartmentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: str | None = None


class UserRead(BaseModel):
    id: UUID
    email: str
    name: str
    avatar_url: str | None
    role: UserRole
    department_id: UUID
    department: DepartmentBrief
    is_active: bool
    is_bot: bool
    status: AccountStatus
    last_login_at: datetime | None
    last_seen_at: datetime | None
    invited_by: UUID | None
    created_at: datetime


class UserPage(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    page_size: int


def account_status(user: User) -> AccountStatus:
    if not user.is_active:
        return "deactivated"
    if user.is_bot or user.last_login_at is not None:
        return "active"
    return "invited"


def to_user_read(user: User, department: Department) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        role=user.role,
        department_id=user.department_id,
        department=DepartmentBrief.model_validate(department),
        is_active=user.is_active,
        is_bot=user.is_bot,
        status=account_status(user),
        last_login_at=user.last_login_at,
        last_seen_at=user.last_seen_at,
        invited_by=user.invited_by,
        created_at=user.created_at,
    )
