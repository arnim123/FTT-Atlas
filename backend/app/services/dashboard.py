"""Workspace dashboard.

Every document total, department bar, recent upload, and viewed document comes
from `accessible_documents_query`. Archived and soft-deleted rows are excluded.
Active people and agent-call totals are not document figures: admins see the
whole organization, department managers see their department, and everyone else
receives only a count.
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import DocumentStatus, EventType, UserRole
from app.core.principal import Principal
from app.models.access import ApiAuditLog
from app.models.base import utcnow
from app.models.department import Department
from app.models.document import Document
from app.models.event import DocumentEvent
from app.models.user import User
from app.permissions.engine import accessible_documents_query
from app.services.folders import folder_display_paths

RECENT_LIMIT = 10
VIEWED_LIMIT = 10
ACTIVITY_WINDOW = timedelta(days=30)
_ADMIN_ROLES = frozenset({UserRole.super_admin, UserRole.admin})
_ROSTER_ROLES = frozenset({UserRole.super_admin, UserRole.admin, UserRole.manager})


@dataclass(frozen=True)
class DepartmentCount:
    id: UUID
    name: str
    code: str
    count: int


@dataclass
class DashboardDocument:
    document: Document
    department_name: str
    folder_path: str
    view_count: int | None


@dataclass(frozen=True)
class ActiveUser:
    id: UUID
    name: str
    department_id: UUID


@dataclass
class ActiveUsers:
    count: int
    users: list[ActiveUser] | None


@dataclass(frozen=True)
class AiQuestions:
    enabled: bool
    count: int | None


@dataclass
class DashboardResult:
    total_documents: int
    added_this_month: int
    by_department: list[DepartmentCount]
    recent_uploads: list[DashboardDocument]
    most_viewed: list[DashboardDocument]
    active_users: ActiveUsers
    ai_questions_asked: AiQuestions
    ai_agent_calls_30d: int | None


def get_dashboard(session: Session, principal: Principal) -> DashboardResult:
    user = principal.user
    visible = [
        accessible_documents_query(user, principal.scopes),
        Document.status == DocumentStatus.active,
    ]
    now = utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    window_start = now - ACTIVITY_WINDOW
    total = session.scalar(select(func.count()).select_from(Document).where(*visible)) or 0
    added = (
        session.scalar(select(func.count()).select_from(Document).where(*visible, Document.created_at >= month_start)) or 0
    )
    return DashboardResult(
        total_documents=total,
        added_this_month=added,
        by_department=_by_department(session, visible),
        recent_uploads=_recent(session, visible),
        most_viewed=_most_viewed(session, visible, window_start),
        active_users=_active_users(session, user, window_start),
        ai_questions_asked=AiQuestions(enabled=bool(get_settings().ai_enabled), count=None),
        ai_agent_calls_30d=_agent_calls(session, user, window_start),
    )


def _by_department(session: Session, visible: list) -> list[DepartmentCount]:
    counts = (
        select(Document.department_id, func.count(Document.id).label("count"))
        .where(*visible)
        .group_by(Document.department_id)
        .subquery()
    )
    rows = session.execute(
        select(Department.id, Department.name, Department.code, func.coalesce(counts.c.count, 0))
        .outerjoin(counts, counts.c.department_id == Department.id)
        .order_by(Department.name.asc())
    ).all()
    return [DepartmentCount(id=row[0], name=row[1], code=row[2], count=int(row[3])) for row in rows]


def _recent(session: Session, visible: list) -> list[DashboardDocument]:
    documents = list(
        session.scalars(select(Document).where(*visible).order_by(Document.created_at.desc(), Document.id.asc()).limit(RECENT_LIMIT))
    )
    return _cards(session, documents, view_counts=None)


def _most_viewed(session: Session, visible: list, window_start) -> list[DashboardDocument]:
    views = (
        select(DocumentEvent.document_id, func.count().label("view_count"))
        .where(DocumentEvent.event_type == EventType.view, DocumentEvent.created_at >= window_start)
        .group_by(DocumentEvent.document_id)
        .subquery()
    )
    rows = session.execute(
        select(Document, views.c.view_count)
        .join(views, views.c.document_id == Document.id)
        .where(*visible)
        .order_by(views.c.view_count.desc(), Document.name.asc(), Document.id.asc())
        .limit(VIEWED_LIMIT)
    ).all()
    documents = [row[0] for row in rows]
    view_counts = {row[0].id: int(row[1]) for row in rows}
    return _cards(session, documents, view_counts)


def _cards(session: Session, documents: list[Document], view_counts: dict[UUID, int] | None) -> list[DashboardDocument]:
    if not documents:
        return []
    names = dict(session.execute(select(Department.id, Department.name).where(Department.id.in_({item.department_id for item in documents}))).all())
    paths = folder_display_paths(session, {item.folder_id for item in documents})
    cards: list[DashboardDocument] = []
    for document in documents:
        count = None if view_counts is None else view_counts.get(document.id, 0)
        cards.append(
            DashboardDocument(
                document=document,
                department_name=names.get(document.department_id, ""),
                folder_path=paths.get(document.folder_id, ""),
                view_count=count,
            )
        )
    return cards


def _active_users(session: Session, user: User, window_start) -> ActiveUsers:
    criteria = [
        User.is_active.is_(True),
        User.is_bot.is_(False),
        User.last_seen_at.is_not(None),
        User.last_seen_at >= window_start,
    ]
    if user.role not in _ADMIN_ROLES:
        criteria.append(User.department_id == user.department_id)
    count = session.scalar(select(func.count()).select_from(User).where(*criteria)) or 0
    if user.role not in _ROSTER_ROLES:
        return ActiveUsers(count=count, users=None)
    rows = session.scalars(select(User).where(*criteria).order_by(User.name.asc(), User.id.asc())).all()
    return ActiveUsers(
        count=count,
        users=[ActiveUser(id=row.id, name=row.name, department_id=row.department_id) for row in rows],
    )


def _agent_calls(session: Session, user: User, window_start) -> int | None:
    if user.role not in _ADMIN_ROLES:
        return None
    return session.scalar(select(func.count()).select_from(ApiAuditLog).where(ApiAuditLog.created_at >= window_start)) or 0
