"""Turn one document into stored text and chunks.

The document hash is the SHA-256 of the extracted text. When that hash already
matches and the stored text is unchanged, chunk rows are left alone. Otherwise
the chunks for the current version are replaced. `refresh_search_vector` runs
after a successful extraction so the text is searchable in this request.

This module does not call an embedding model or a language model.
"""

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ai.errors import NotConfigured
from app.core.config import get_settings
from app.core.enums import ExtractionStatus, SourceType
from app.ingestion.chunker import chunk_text
from app.ingestion.extractors import (
    GOOGLE_SOURCES,
    SKIPPED_REASONS,
    DocxExtractor,
    ExtractInput,
    GoogleExportExtractor,
    OCRExtractor,
    PdfExtractor,
    PermanentExtractionError,
    PlainTextExtractor,
    SkippedExtraction,
    TextExtractor,
    content_hash,
    read_upload,
)
from app.integrations.drive import GoogleDriveClient, build_drive_client
from app.integrations.storage import LocalDiskStorage, StorageBackend
from app.models.base import utcnow
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.services.search import refresh_search_vector

_BYTE_EXTRACTORS: dict[SourceType, TextExtractor] = {
    SourceType.pdf: PdfExtractor(),
    SourceType.docx: DocxExtractor(),
    SourceType.txt: PlainTextExtractor(),
}


class ExtractionPipeline:
    def __init__(self, storage: StorageBackend | None = None, drive: GoogleDriveClient | None = None) -> None:
        self._storage = storage
        self._drive = drive

    def run(self, session: Session, document_id: UUID) -> None:
        document = session.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            return
        extracted = self._extract(document)
        if isinstance(extracted, SkippedExtraction):
            _mark_skipped(session, document, extracted.reason)
            return
        digest = content_hash(extracted)
        if document.content_hash == digest and document.content_text == extracted:
            document.extraction_status = ExtractionStatus.done
            document.extraction_error = None
            document.extracted_at = utcnow()
            session.flush()
            refresh_search_vector(session, document.id)
            return
        document.content_text = extracted
        document.content_hash = digest
        document.extraction_status = ExtractionStatus.done
        document.extraction_error = None
        document.extracted_at = utcnow()
        _replace_chunks(session, document, extracted)
        session.flush()
        refresh_search_vector(session, document.id)

    def _extract(self, document: Document) -> str | SkippedExtraction:
        if document.source_type is SourceType.image:
            try:
                return OCRExtractor().extract(ExtractInput())
            except NotConfigured:
                return SkippedExtraction("Image files need OCR, which is not configured.")
        if document.source_type in SKIPPED_REASONS:
            return SkippedExtraction(SKIPPED_REASONS[document.source_type])
        if document.source_type in GOOGLE_SOURCES:
            if not document.google_file_id:
                return SkippedExtraction("This Google file has no id.")
            return GoogleExportExtractor(self._drive_client()).extract(ExtractInput(google_file_id=document.google_file_id))
        extractor = _BYTE_EXTRACTORS.get(document.source_type)
        if extractor is None:
            raise PermanentExtractionError(f"{document.source_type.value} files cannot be extracted.")
        if not document.storage_key:
            return SkippedExtraction("No file is attached to this document yet.")
        return extractor.extract(ExtractInput(data=read_upload(self._storage_backend(), document.storage_key)))

    def _storage_backend(self) -> StorageBackend:
        if self._storage is not None:
            return self._storage
        return LocalDiskStorage(get_settings().storage_root)

    def _drive_client(self) -> GoogleDriveClient:
        if self._drive is not None:
            return self._drive
        return build_drive_client()


def process_document(
    session: Session,
    document_id: UUID,
    *,
    storage: StorageBackend | None = None,
    drive: GoogleDriveClient | None = None,
) -> None:
    ExtractionPipeline(storage=storage, drive=drive).run(session, document_id)


def _mark_skipped(session: Session, document: Document, reason: str) -> None:
    document.content_text = None
    document.content_hash = None
    document.extraction_status = ExtractionStatus.skipped
    document.extraction_error = reason
    document.extracted_at = utcnow()
    _delete_version_chunks(session, document)
    session.flush()
    refresh_search_vector(session, document.id)


def _replace_chunks(session: Session, document: Document, text: str) -> None:
    _delete_version_chunks(session, document)
    session.flush()
    for chunk in chunk_text(text):
        session.add(
            DocumentChunk(
                document_id=document.id,
                version_number=document.current_version_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                token_count=chunk.token_count,
                heading_path=chunk.heading_path,
                content_hash=chunk.content_hash,
            )
        )


def _delete_version_chunks(session: Session, document: Document) -> None:
    session.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == document.id,
            DocumentChunk.version_number == document.current_version_number,
        )
    )

