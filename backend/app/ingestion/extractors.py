"""Text extractors.

`TextExtractor` is the boundary. Google files are exported through
`GoogleDriveClient`. Uploaded PDF, Word, and plain text are read from bytes.
Images go through `OCRExtractor`, which raises `NotConfigured` until a later
phase. PowerPoint and Excel are not extracted in Phase 1.

None of these implementations call an AI provider.
"""

import io
import zipfile
from dataclasses import dataclass
from typing import Protocol

from app.ai.errors import NotConfigured
from app.core.enums import SourceType
from app.ingestion.chunker import text_hash
from app.integrations.drive import (
    DriveError,
    DriveForbidden,
    DriveNotFound,
    GoogleDriveClient,
)
from app.integrations.storage import MissingFile, StorageBackend, StorageError

GOOGLE_SOURCES = {SourceType.google_doc, SourceType.google_sheet, SourceType.google_slide}
SKIPPED_REASONS = {
    SourceType.ppt: "PowerPoint files are not extracted in this phase.",
    SourceType.xlsx: "Excel files are not extracted in this phase.",
}


class ExtractionError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PermanentExtractionError(ExtractionError):
    """The file will not succeed on another attempt."""


class TransientExtractionError(ExtractionError):
    """A later attempt may succeed. The queue retries these."""


@dataclass(frozen=True)
class ExtractInput:
    data: bytes | None = None
    google_file_id: str | None = None


@dataclass(frozen=True)
class SkippedExtraction:
    reason: str


class TextExtractor(Protocol):
    def extract(self, source: ExtractInput) -> str: ...


class PlainTextExtractor:
    def extract(self, source: ExtractInput) -> str:
        if not source.data:
            return ""
        return _clean(source.data.decode("utf-8-sig", errors="replace"))


class PdfExtractor:
    def extract(self, source: ExtractInput) -> str:
        if not source.data:
            raise PermanentExtractionError("This PDF could not be read.")
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(source.data))
            pages = [page.extract_text() or "" for page in reader.pages]
        except PermanentExtractionError:
            raise
        except Exception as exc:
            raise PermanentExtractionError("This PDF could not be read.") from exc
        return _clean("\n\n".join(pages))


class DocxExtractor:
    def extract(self, source: ExtractInput) -> str:
        if not source.data:
            raise PermanentExtractionError("This Word file could not be read.")
        try:
            from docx import Document

            document = Document(io.BytesIO(source.data))
        except (zipfile.BadZipFile, ValueError) as exc:
            raise PermanentExtractionError("This Word file could not be read.") from exc
        except Exception as exc:
            raise PermanentExtractionError("This Word file could not be read.") from exc
        lines: list[str] = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if not text:
                lines.append("")
                continue
            level = _heading_level(paragraph.style.name if paragraph.style is not None else "")
            lines.append(f"{'#' * level} {text}" if level else text)
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    lines.append(" | ".join(cells))
        return _clean("\n".join(lines))


class GoogleExportExtractor:
    """Exports a Docs, Sheets, or Slides file as plain text through Drive."""

    def __init__(self, client: GoogleDriveClient) -> None:
        self.client = client

    def extract(self, source: ExtractInput) -> str:
        if not source.google_file_id:
            raise PermanentExtractionError("This Google file has no id.")
        try:
            exported = self.client.export_text(source.google_file_id)
        except (DriveNotFound, DriveForbidden) as exc:
            raise PermanentExtractionError("The Google file could not be exported.") from exc
        except DriveError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise TransientExtractionError("Google Drive is temporarily unavailable.") from exc
            raise PermanentExtractionError("The Google file could not be exported.") from exc
        return _clean(exported or "")


class OCRExtractor:
    """Reserved for a later phase. Calling it is an explicit configuration error."""

    def extract(self, source: ExtractInput) -> str:
        raise NotConfigured("OCR is not configured.")


def content_hash(value: str) -> str:
    return text_hash(value)


def read_upload(storage: StorageBackend, key: str) -> bytes:
    try:
        return storage.read(key)
    except MissingFile as exc:
        raise PermanentExtractionError("This document has no uploaded file.") from exc
    except StorageError as exc:
        raise TransientExtractionError("The file could not be read.") from exc


def _heading_level(style_name: str) -> int | None:
    name = style_name.strip().lower()
    if name == "title":
        return 1
    if not name.startswith("heading"):
        return None
    digits = "".join(character for character in name if character.isdigit())
    if not digits:
        return 1
    return min(6, max(1, int(digits)))


def _clean(value: str) -> str:
    return value.replace("\x00", "").strip()
