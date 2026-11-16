from uuid import UUID

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AccessGrant, PrincipalType, access_grant_enum, principal_type_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentPermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_permissions"
    __table_args__ = (
        UniqueConstraint("resource_id", "principal_type", "principal_id", name="uq_document_permissions_principal"),
    )

    resource_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    principal_type: Mapped[PrincipalType] = mapped_column(principal_type_enum, nullable=False)
    principal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    access: Mapped[AccessGrant] = mapped_column(access_grant_enum, nullable=False)
    google_permission_id: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class FolderPermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "folder_permissions"
    __table_args__ = (
        UniqueConstraint("resource_id", "principal_type", "principal_id", name="uq_folder_permissions_principal"),
    )

    resource_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=False
    )
    principal_type: Mapped[PrincipalType] = mapped_column(principal_type_enum, nullable=False)
    principal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    access: Mapped[AccessGrant] = mapped_column(access_grant_enum, nullable=False)
    google_permission_id: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
