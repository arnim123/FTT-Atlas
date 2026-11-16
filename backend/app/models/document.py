from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    AccessGrant,
    DocumentStatus,
    DriveSyncStatus,
    ExtractionStatus,
    SourceType,
    Visibility,
    access_grant_enum,
    document_status_enum,
    drive_sync_status_enum,
    extraction_status_enum,
    source_type_enum,
    visibility_enum,
)
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("current_version_number >= 1", name="version_positive"),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="size_nonnegative"),
        Index("ix_documents_folder_id", "folder_id"),
        Index("ix_documents_owner_id", "owner_id"),
        Index("ix_documents_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_documents_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_documents_original_filename_trgm",
            "original_filename",
            postgresql_using="gin",
            postgresql_ops={"original_filename": "gin_trgm_ops"},
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    folder_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("folders.id", ondelete="RESTRICT"), nullable=False)
    category_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(source_type_enum, nullable=False)
    google_file_id: Mapped[str | None] = mapped_column(Text, unique=True)
    google_mime_type: Mapped[str | None] = mapped_column(Text)
    google_web_url: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    current_version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    visibility: Mapped[Visibility] = mapped_column(visibility_enum, nullable=False)
    default_access: Mapped[AccessGrant] = mapped_column(access_grant_enum, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        document_status_enum,
        nullable=False,
        default=DocumentStatus.active,
        server_default=text("'active'::document_status"),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    drive_sync_status: Mapped[DriveSyncStatus] = mapped_column(
        drive_sync_status_enum,
        nullable=False,
        default=DriveSyncStatus.not_applicable,
        server_default=text("'not_applicable'::drive_sync_status"),
    )
    drive_sync_error: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        extraction_status_enum,
        nullable=False,
        default=ExtractionStatus.pending,
        server_default=text("'pending'::extraction_status"),
    )
    extraction_error: Mapped[str | None] = mapped_column(Text)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_key_takeaways: Mapped[list[str] | None] = mapped_column(JSONB)
    ai_keywords: Mapped[list[str] | None] = mapped_column(JSONB)
    ai_topics: Mapped[list[str] | None] = mapped_column(JSONB)
    ai_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_vector: Mapped[Any | None] = mapped_column(
        TSVECTOR,
        comment="Weighted tsvector maintained by refresh_search_vector(). Name A, tags and category B, description C, content D.",
    )


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        CheckConstraint("version_number >= 1", name="version_positive"),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="size_nonnegative"),
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version"),
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    uploaded_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    change_note: Mapped[str | None] = mapped_column(Text)
