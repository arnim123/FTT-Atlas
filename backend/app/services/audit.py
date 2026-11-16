"""Audit rows for bearer and MCP calls. The summary never includes document text."""

from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AuditChannel
from app.core.principal import AuthMethod, Principal
from app.models.access import ApiAuditLog
from app.models.base import utcnow

_actor: ContextVar[dict | None] = ContextVar("external_audit_actor", default=None)
_scope_ref: ContextVar[dict | None] = ContextVar("external_audit_scope", default=None)

_REDACTED = frozenset(
    {
        "q",
        "query",
        "question",
        "description",
        "content",
        "text",
        "name",
        "title",
        "url",
        "document_content",
        "body",
        "prompt",
    }
)


def bind_audit_scope(scope: dict):
    """Share this request's scope with sync endpoints running on a worker thread."""
    return _scope_ref.set(scope)


def reset_audit_scope(token) -> None:
    _scope_ref.reset(token)


def remember_actor(principal: Principal, *, oauth_client_id: UUID | None = None, rate_id: UUID | None = None) -> None:
    """Keep ids for the audit middleware. Session calls are not recorded.

    Sync routes run on a worker thread, so the context var set there does not
    come back to the middleware. The scope dict is shared, and the middleware
    publishes it before the route runs. OAuth rows are not api_tokens, so
    token_id stays empty and oauth_client_id is stored instead.
    """
    if principal.auth_method is AuthMethod.session:
        return
    payload = {
        "user_id": principal.user.id,
        "token_id": principal.token_id if principal.auth_method is AuthMethod.bearer else None,
        "oauth_client_id": oauth_client_id,
        "rate_id": rate_id if rate_id is not None else principal.token_id,
        "auth_method": principal.auth_method.value,
    }
    _actor.set(payload)
    scope = _scope_ref.get()
    if scope is not None:
        scope["external_actor"] = payload


def current_actor() -> dict | None:
    return _actor.get()


def reset_actor(token) -> None:
    _actor.reset(token)


def push_actor():
    return _actor.set(None)


def summarize_query(query: dict[str, str]) -> dict[str, object]:
    """Keep identifiers. Replace free text with its length so content is not stored."""
    safe: dict[str, object] = {}
    for key, value in query.items():
        if key.lower() in _REDACTED or "dms_pat_" in value:
            safe[key] = {"present": bool(value), "length": len(value)}
        else:
            safe[key] = value[:120]
    return safe


def write_audit(
    session: Session,
    *,
    token_id: UUID | None,
    user_id: UUID,
    channel: AuditChannel,
    operation: str,
    status_code: int,
    duration_ms: int,
    ip: str | None,
    user_agent: str | None,
    request_summary: dict,
    oauth_client_id: UUID | None = None,
) -> None:
    session.add(
        ApiAuditLog(
            token_id=token_id,
            oauth_client_id=oauth_client_id,
            user_id=user_id,
            channel=channel,
            operation=operation[:300],
            status_code=status_code,
            duration_ms=max(0, duration_ms),
            ip=(ip or None),
            user_agent=(user_agent or None)[:300] if user_agent else None,
            request_summary=request_summary,
            created_at=utcnow(),
        )
    )
    session.commit()


def list_audit(
    session: Session,
    *,
    user_id: UUID | None = None,
    token_id: UUID | None = None,
    channel: AuditChannel | None = None,
    operation: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ApiAuditLog], int]:
    from sqlalchemy import func

    criteria = []
    if user_id is not None:
        criteria.append(ApiAuditLog.user_id == user_id)
    if token_id is not None:
        criteria.append(ApiAuditLog.token_id == token_id)
    if channel is not None:
        criteria.append(ApiAuditLog.channel == channel)
    if operation:
        criteria.append(ApiAuditLog.operation == operation)
    total = session.scalar(select(func.count()).select_from(ApiAuditLog).where(*criteria)) or 0
    rows = list(
        session.scalars(
            select(ApiAuditLog)
            .where(*criteria)
            .order_by(ApiAuditLog.created_at.desc(), ApiAuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return rows, int(total)


def audit_page(limit: int, cursor: str | None) -> tuple[int, int]:
    from app.services.agent import decode_cursor

    page = decode_cursor(cursor)
    bounded = min(max(limit, 1), 100)
    return bounded, (page - 1) * bounded


def next_audit_cursor(page_size: int, offset: int, total: int) -> str | None:
    from app.services.agent import encode_cursor

    if offset + page_size >= total:
        return None
    return encode_cursor((offset // page_size) + 2)
