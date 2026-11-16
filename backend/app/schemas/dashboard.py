from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import SourceType
from app.schemas.documents import document_web_url


class DepartmentCountRead(BaseModel):
    id: UUID
    name: str
    code: str
    count: int


class DashboardDocumentRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    source_type: SourceType
    department_id: UUID
    department_name: str
    folder_id: UUID
    folder_path: str
    owner_id: UUID
    web_url: str
    google_url: str | None
    created_at: datetime
    last_modified_at: datetime | None
    view_count: int | None = None


class ActiveUserRead(BaseModel):
    id: UUID
    name: str
    department_id: UUID


class ActiveUsersRead(BaseModel):
    """count is always present. users is omitted for employees and guests."""

    count: int
    users: list[ActiveUserRead] | None = None


class AiQuestionsRead(BaseModel):
    enabled: bool
    count: int | None


class DashboardResponse(BaseModel):
    total_documents: int
    added_this_month: int
    by_department: list[DepartmentCountRead]
    recent_uploads: list[DashboardDocumentRead] = Field(max_length=10)
    most_viewed: list[DashboardDocumentRead] = Field(max_length=10)
    active_users: ActiveUsersRead
    ai_questions_asked: AiQuestionsRead
    ai_agent_calls_30d: int | None


def to_dashboard_response(result) -> DashboardResponse:
    users = result.active_users.users
    return DashboardResponse(
        total_documents=result.total_documents,
        added_this_month=result.added_this_month,
        by_department=[
            DepartmentCountRead(id=row.id, name=row.name, code=row.code, count=row.count) for row in result.by_department
        ],
        recent_uploads=[_document(item) for item in result.recent_uploads],
        most_viewed=[_document(item) for item in result.most_viewed],
        active_users=ActiveUsersRead(
            count=result.active_users.count,
            users=None
            if users is None
            else [ActiveUserRead(id=user.id, name=user.name, department_id=user.department_id) for user in users],
        ),
        ai_questions_asked=AiQuestionsRead(enabled=result.ai_questions_asked.enabled, count=result.ai_questions_asked.count),
        ai_agent_calls_30d=result.ai_agent_calls_30d,
    )


def _document(item) -> DashboardDocumentRead:
    document = item.document
    return DashboardDocumentRead(
        id=document.id,
        name=document.name,
        description=document.description,
        source_type=document.source_type,
        department_id=document.department_id,
        department_name=item.department_name,
        folder_id=document.folder_id,
        folder_path=item.folder_path,
        owner_id=document.owner_id,
        web_url=document_web_url(document.id),
        google_url=document.google_web_url,
        created_at=document.created_at,
        last_modified_at=document.last_modified_at,
        view_count=item.view_count,
    )
