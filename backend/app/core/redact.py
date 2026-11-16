"""Keep tokens and document text out of process logs."""

import logging
import re

_SECRET = re.compile(
    r"(?i)(authorization|bearer|id_token|client_secret|refresh_token|access_token|dms_pat_[A-Za-z0-9]{8}_)([\"':=\s]+)([A-Za-z0-9._~+/=-]{8,})"
)


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            return True
        cleaned = _SECRET.sub(r"\1\2[redacted]", rendered)
        if cleaned != rendered:
            record.msg = cleaned
            record.args = ()
        return True


def install_redaction() -> None:
    redact = RedactFilter()
    logging.getLogger().addFilter(redact)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).addFilter(redact)
