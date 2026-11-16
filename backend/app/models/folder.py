from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AccessGrant, Visibility, access_grant_enum, visibility_enum
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Folder(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "folders"
    __table_args__ = (
        CheckConstraint("depth >= 0", name="depth_nonnegative"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="parent_not_self"),
        Index("ix_folders_path_pattern", "path", postgresql_ops={"path": "text_pattern_ops"}),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("folders.id", ondelete="RESTRICT"), index=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    department_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    visibility: Mapped[Visibility] = mapped_column(visibility_enum, nullable=False)
    default_access: Mapped[AccessGrant] = mapped_column(access_grant_enum, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
