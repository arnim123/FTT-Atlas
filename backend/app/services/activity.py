"""Document audit rows and the in-process bus.

Event rows copy actor_channel, token_id, and client_name from the principal.
Session calls are web, bearer tokens are rest, and OAuth calls are mcp.
The bus runs only after the database commit that recorded the change.
"""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import ActorChannel, EventType
from app.core.errors import ApiError
from app.core.events import event_bus
from app.core.principal import AuthMethod, Principal
from app.models.event import DocumentEvent


def channel_for(principal: Principal) -> ActorChannel:
    if principal.auth_method is AuthMethod.session:
        return ActorChannel.web
    if principal.auth_method is AuthMethod.oauth:
        return ActorChannel.mcp
    return ActorChannel.rest


def record_document_event(
    session: Session,
    principal: Principal,
    document_id: UUID,
    event_type: EventType,
    metadata: dict | None = None,
) -> None:
    session.add(
        DocumentEvent(
            document_id=document_id,
            user_id=principal.user.id,
            event_type=event_type,
            actor_channel=channel_for(principal),
            token_id=principal.token_id,
            client_name=principal.client_name,
            event_metadata=metadata or {},
        )
    )


def commit_and_emit(session: Session, event: str | None = None, **payload: object) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(409, "CONFLICT", "The change conflicts with an existing record.") from exc
    if event is not None:
        emit_with_session(session, event, **payload)


def emit_with_session(session: Session, event: str, **payload: object) -> None:
    """Run handlers against the session that just committed, including in a worker thread."""
    from app.core.database import bind_request_session, reset_request_session

    token = bind_request_session(session)
    try:
        event_bus.emit(event, **payload)
    finally:
        reset_request_session(token)
