from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Extracted passage. Embedding storage is intentionally absent until a later phase."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", "chunk_index", name="uq_document_chunks_position"),
        CheckConstraint("version_number >= 1", name="version_positive"),
        CheckConstraint("chunk_index >= 0", name="chunk_index_nonnegative"),
        CheckConstraint("token_count IS NULL OR token_count >= 0", name="token_count_nonnegative"),
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    heading_path: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
