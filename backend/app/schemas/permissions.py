from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import AccessGrant, DriveSyncStatus, PrincipalType, Visibility

AccessName = Literal["none", "view", "edit", "manage"]

_GRANT_EXAMPLE = {
    "principal_type": "user",
    "principal_id": "5b0c1a22-7e3d-4f1a-9c2b-1d6e8f0a4b21",
    "access": "edit",
}


class GrantInput(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [_GRANT_EXAMPLE]})

    principal_type: PrincipalType
    principal_id: UUID
    access: AccessGrant


class GrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    principal_type: PrincipalType
    principal_id: UUID
    access: AccessGrant


class PermissionsUpdate(BaseModel):
    """Replaces visibility, the default audience, and every explicit grant."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "visibility": "custom",
                    "default_access": "view",
                    "grants": [_GRANT_EXAMPLE, {"principal_type": "department", "principal_id": "9c1e6b40-2a55-4d8e-8f10-6a3b2c1d0e77", "access": "view"}],
                }
            ]
        }
    )

    visibility: Visibility
    default_access: AccessGrant = AccessGrant.view
    grants: list[GrantInput] = Field(default_factory=list)


class PermissionsRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "visibility": "department",
                    "default_access": "view",
                    "grants": [],
                    "my_access": "manage",
                }
            ]
        }
    )

    visibility: Visibility
    default_access: AccessGrant
    grants: list[GrantRead]
    my_access: AccessName
    drive_sync_status: DriveSyncStatus | None = None
    drive_sync_error: str | None = None
