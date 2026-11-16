"""In-process event bus.

Drive sync subscribes to document and `user_access_changed` events.
Deactivating a user revokes that user's API tokens on `user_access_changed`.
Handlers run after the database commit that caused the change.
"""

from collections import defaultdict
from collections.abc import Callable
from typing import Any

Handler = Callable[[dict[str, Any]], None]

USER_ACCESS_CHANGED = "user_access_changed"
DOCUMENT_CREATED = "document_created"
DOCUMENT_UPDATED = "document_updated"
DOCUMENT_PERMISSIONS_CHANGED = "document_permissions_changed"
DOCUMENT_ARCHIVED = "document_archived"
DOCUMENT_RESTORED = "document_restored"
DOCUMENT_DELETED = "document_deleted"
DOCUMENT_VERSION_ADDED = "document_version_added"
GOOGLE_MODIFIED = "google_modified"


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        handlers = self._handlers[event]
        if handler not in handlers:
            handlers.append(handler)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        handlers = self._handlers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event: str, **payload: Any) -> None:
        for handler in list(self._handlers.get(event, ())):
            handler(payload)

    def clear(self) -> None:
        self._handlers.clear()


event_bus = EventBus()
