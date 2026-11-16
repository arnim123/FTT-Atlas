"""Recent document access for the viewer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import ActorChannel, EventType


class DocumentEventRead(BaseModel):
    id: UUID
    document_id: UUID
    user_id: UUID
    event_type: EventType
    channel: ActorChannel
    client_name: str | None
    created_at: datetime


class DocumentEventPage(BaseModel):
    items: list[DocumentEventRead]
