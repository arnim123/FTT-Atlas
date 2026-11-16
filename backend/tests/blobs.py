import io
import zipfile


def pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def png_bytes() -> bytes:
    return bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 24


def jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 16


def webp_bytes() -> bytes:
    return b"RIFF" + (24).to_bytes(4, "little") + b"WEBP" + b"VP8 " + b"\x00" * 8


def text_bytes(text: str = "Quarterly update\n") -> bytes:
    return text.encode("utf-8")


def office_bytes(kind: str) -> bytes:
    names = {"docx": "word/document.xml", "xlsx": "xl/workbook.xml", "pptx": "ppt/presentation.xml"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr(names[kind], "<root/>")
    return buffer.getvalue()
