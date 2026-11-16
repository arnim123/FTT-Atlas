"""File storage. Keys are random ids; the original filename is never part of the path."""

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.parse import quote
from uuid import uuid4

from app.core.enums import SourceType

_KEY = re.compile(r"^[0-9a-f]{32}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_PNG = b"\x89PNG\r\n\x1a\n"

_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
}
_SOURCE = {
    "pdf": SourceType.pdf,
    "docx": SourceType.docx,
    "pptx": SourceType.ppt,
    "xlsx": SourceType.xlsx,
    "txt": SourceType.txt,
    "png": SourceType.image,
    "jpg": SourceType.image,
    "webp": SourceType.image,
}
_INLINE = {"pdf", "txt", "png", "jpg", "webp"}
_OFFICE_PREFIX = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}
_EXTENSION_ALIASES = {
    "jpg": {".jpg", ".jpeg"},
    "jpeg": {".jpg", ".jpeg"},
    "txt": {".txt", ".text"},
}


class StorageError(Exception):
    status_code = 400
    code = "STORAGE_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class FileTooLarge(StorageError):
    status_code = 413
    code = "FILE_TOO_LARGE"

    def __init__(self, max_bytes: int) -> None:
        megabytes = max(1, max_bytes // (1024 * 1024))
        super().__init__(f"Files must be {megabytes} MB or smaller.")


class EmptyFile(StorageError):
    status_code = 422
    code = "EMPTY_FILE"

    def __init__(self) -> None:
        super().__init__("This file is empty.")


class UnsupportedFile(StorageError):
    status_code = 415
    code = "UNSUPPORTED_FILE_TYPE"

    def __init__(self) -> None:
        super().__init__("Upload a PDF, Word, PowerPoint, Excel, text, or image file.")


class MissingFile(StorageError):
    status_code = 404
    code = "NO_FILE"

    def __init__(self) -> None:
        super().__init__("This document has no uploaded file.")


@dataclass(frozen=True)
class DetectedFile:
    extension: str
    mime_type: str
    source_type: SourceType
    inline: bool


class StorageBackend(Protocol):
    def save(self, content: bytes) -> str: ...

    def open(self, key: str) -> BinaryIO: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...


class LocalDiskStorage:
    """Stores bytes under STORAGE_ROOT/{key[:2]}/{key}. The key is a uuid hex."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save(self, content: bytes) -> str:
        key = uuid4().hex
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.partial")
        temporary.write_bytes(content)
        temporary.replace(path)
        return key

    def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        if not path.is_file():
            raise MissingFile()
        return path.open("rb")

    def read(self, key: str) -> bytes:
        with self.open(key) as handle:
            return handle.read()

    def delete(self, key: str) -> None:
        try:
            path = self._path(key)
        except StorageError:
            return
        if path.is_file():
            path.unlink()

    def exists(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except StorageError:
            return False

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise StorageError("Invalid storage key.")
        root = self.root.resolve()
        path = (root / key[:2] / key).resolve()
        if not path.is_relative_to(root):
            raise StorageError("Invalid storage key.")
        return path


def read_bounded(stream: BinaryIO, max_bytes: int) -> bytes:
    """Read an upload, rejecting empty files and anything past the size limit."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLarge(max_bytes)
        chunks.append(chunk)
    if total == 0:
        raise EmptyFile()
    return b"".join(chunks)


def detect_file(content: bytes) -> DetectedFile:
    """Classify an upload from its bytes. The client filename is not consulted."""
    if not content:
        raise EmptyFile()
    if content.startswith(b"%PDF"):
        return _detected("pdf")
    if content.startswith(_PNG):
        return _detected("png")
    if content.startswith(b"\xff\xd8\xff"):
        return _detected("jpg")
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return _detected("webp")
    if content.startswith(b"PK\x03\x04"):
        kind = _office_kind(content)
        if kind is None:
            raise UnsupportedFile()
        return _detected(kind)
    if _is_text(content):
        return _detected("txt")
    raise UnsupportedFile()


def sanitize_filename(name: str | None) -> str:
    """Drop paths and control characters. The result is a display name, never a storage key."""
    raw = (name or "").replace("\\", "/").split("/")[-1]
    cleaned = _CONTROL.sub("", raw).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned in {"", ".", ".."}:
        return "file"
    return cleaned[:180]


def filename_for(original: str | None, detected: DetectedFile) -> str:
    """Keep the sanitized name when its extension matches the sniffed type."""
    cleaned = sanitize_filename(original)
    suffix = f".{detected.extension}"
    allowed = _EXTENSION_ALIASES.get(detected.extension, {suffix})
    if any(cleaned.lower().endswith(ext) for ext in allowed):
        return cleaned
    stem = cleaned.rsplit(".", 1)[0] if "." in cleaned else cleaned
    stem = stem or "file"
    return f"{stem}{suffix}"[:180]


def content_disposition(inline: bool, filename: str) -> str:
    disposition = "inline" if inline else "attachment"
    cleaned = filename.replace("\r", "").replace("\n", "").replace('"', "")
    ascii_name = cleaned.encode("ascii", "ignore").decode().strip() or "file"
    encoded = quote(cleaned, safe="")
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def _detected(extension: str) -> DetectedFile:
    return DetectedFile(
        extension=extension,
        mime_type=_MIME[extension],
        source_type=_SOURCE[extension],
        inline=extension in _INLINE,
    )


def _office_kind(content: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name.lower() for name in archive.namelist()]
    except zipfile.BadZipFile:
        return None
    found = [kind for kind, prefix in _OFFICE_PREFIX.items() if any(name.startswith(prefix) for name in names)]
    if len(found) != 1:
        return None
    return found[0]


def _is_text(content: bytes) -> bool:
    if b"\x00" in content:
        return False
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return not any(ord(character) < 32 and character not in "\n\r\t" for character in text)
