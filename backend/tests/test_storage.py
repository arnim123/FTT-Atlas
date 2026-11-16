import io
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.enums import SourceType
from app.integrations.storage import (
    EmptyFile,
    FileTooLarge,
    LocalDiskStorage,
    UnsupportedFile,
    detect_file,
    filename_for,
    read_bounded,
    sanitize_filename,
)
from tests.blobs import jpeg_bytes, office_bytes, pdf_bytes, png_bytes, text_bytes, webp_bytes


def test_upload_limit_defaults_to_50_megabytes():
    assert Settings.model_fields["max_upload_mb"].default == 50


def test_sniff_allowlist_ignores_the_filename():
    detected = {
        "pdf": detect_file(pdf_bytes()),
        "png": detect_file(png_bytes()),
        "jpg": detect_file(jpeg_bytes()),
        "webp": detect_file(webp_bytes()),
        "txt": detect_file(text_bytes()),
        "docx": detect_file(office_bytes("docx")),
        "xlsx": detect_file(office_bytes("xlsx")),
        "pptx": detect_file(office_bytes("pptx")),
    }
    assert detected["pdf"].source_type is SourceType.pdf
    assert detected["docx"].source_type is SourceType.docx
    assert detected["pptx"].source_type is SourceType.ppt
    assert detected["xlsx"].source_type is SourceType.xlsx
    assert detected["png"].source_type is SourceType.image
    assert detected["pdf"].inline is True
    assert detected["docx"].inline is False
    assert detect_file(pdf_bytes()).extension == "pdf"


def test_disguised_and_unknown_bytes_are_rejected():
    assert detect_file(b"%PDF not really a text file").extension == "pdf"
    with pytest.raises(UnsupportedFile):
        detect_file(b"\x00\x01\x02\x03")
    with pytest.raises(UnsupportedFile):
        detect_file(office_bytes("docx")[:8] + b"not-a-zip")
    with pytest.raises(EmptyFile):
        detect_file(b"")


def test_zip_without_an_office_document_is_rejected():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "hello")
    with pytest.raises(UnsupportedFile):
        detect_file(buffer.getvalue())


def test_read_bounded_enforces_the_limit():
    assert read_bounded(io.BytesIO(b"abc"), 3) == b"abc"
    with pytest.raises(FileTooLarge):
        read_bounded(io.BytesIO(b"abcd"), 3)
    with pytest.raises(EmptyFile):
        read_bounded(io.BytesIO(b""), 10)


def test_filenames_are_sanitized_and_keys_are_random(tmp_path: Path):
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("notes.txt") == "notes.txt"
    assert sanitize_filename("a/b.pdf") == "b.pdf"
    assert sanitize_filename("bad\x00name.txt") == "badname.txt"
    assert sanitize_filename("") == "file"
    assert filename_for("report.txt", detect_file(pdf_bytes())).endswith(".pdf")
    assert filename_for("photo.jpeg", detect_file(jpeg_bytes())) == "photo.jpeg"

    storage = LocalDiskStorage(tmp_path)
    key = storage.save(b"hello")
    assert len(key) == 32
    assert "notes" not in key
    assert storage.exists(key) is True
    assert storage.read(key) == b"hello"
    stored = list(tmp_path.rglob(key))
    assert stored and stored[0].name == key
    storage.delete(key)
    assert storage.exists(key) is False
    assert storage.exists("../secrets") is False
