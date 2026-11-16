from collections.abc import Iterator

from starlette.responses import StreamingResponse

from app.core.errors import ApiError
from app.integrations.storage import StorageBackend, StorageError, content_disposition
from app.services.documents import FileDownload


def stream_download(storage: StorageBackend, download: FileDownload) -> StreamingResponse:
    try:
        handle = storage.open(download.storage_key)
    except StorageError as exc:
        raise ApiError(exc.status_code, exc.code, exc.message) from exc

    def chunks() -> Iterator[bytes]:
        try:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                yield block
        finally:
            handle.close()

    headers = {
        "Content-Disposition": content_disposition(download.inline, download.filename),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if download.size_bytes is not None:
        headers["Content-Length"] = str(download.size_bytes)
    return StreamingResponse(chunks(), media_type=download.mime_type, headers=headers)
