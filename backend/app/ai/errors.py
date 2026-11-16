"""Errors for providers that Phase 1 deliberately does not configure."""


class NotConfigured(Exception):
    """Raised when an AI or OCR provider is called while it is not configured."""

    def __init__(self, message: str = "This feature is not configured.") -> None:
        super().__init__(message)
        self.message = message
