from datetime import timedelta

from sqlalchemy import func, select

from app.core.enums import AuditChannel, DocumentStatus
from app.core.principal import scopes_for_role
from app.models import ApiAuditLog, Document, User
from app.models.base import utcnow
from app.permissions.engine import accessible_documents_query
from tests.helpers import login

PRIVATE_NAME = "Recruitment Interview Kit"


def test_admin_dashboard_counts_the_seed_catalog(api, seeded_session):
    login(api, "alex.morgan@company.com")
    response = api.get("/api/v1/dashboard")
    assert response.status_code == 200, response.text
    body = response.json()
    admin = seeded_session.scalar(select(User).where(User.email == "alex.morgan@company.com"))
    assert body["total_documents"] == 25
    assert body["total_documents"] == _visible(seeded_session, admin)
    assert body["added_this_month"] == 16
    assert sum(row["count"] for row in body["by_department"]) == 25
    assert len(body["recent_uploads"]) == 10
    assert body["most_viewed"] == []
    assert body["ai_questions_asked"] == {"enabled": False, "count": None}
    assert body["ai_agent_calls_30d"] == 0
    assert body["active_users"]["count"] == 5
    assert {user["name"] for user in body["active_users"]["users"]} == {
        "Alex Morgan",
        "Sarah Chen",
        "James Wilson",
        "Emma Davis",
        "Noah Williams",
    }
    assert all(row["folder_path"] and row["web_url"] for row in body["recent_uploads"])


def test_document_counts_follow_the_caller(api, seeded_session):
    login(api, "emma.davis@company.com")
    employee_body = api.get("/api/v1/dashboard").json()
    employee = seeded_session.scalar(select(User).where(User.email == "emma.davis@company.com"))
    assert employee_body["total_documents"] == _visible(seeded_session, employee)
    assert employee_body["total_documents"] < 25
    assert employee_body["added_this_month"] == _added_this_month(seeded_session, employee)
    assert PRIVATE_NAME not in api.get("/api/v1/dashboard").text
    assert employee_body["ai_agent_calls_30d"] is None
    assert employee_body["active_users"]["users"] is None

    login(api, "alex.morgan@company.com")
    admin_body = api.get("/api/v1/dashboard").json()
    emma_sales = _code_count(employee_body, "sales")
    admin_sales = _code_count(admin_body, "sales")
    assert emma_sales < admin_sales
    assert sum(row["count"] for row in employee_body["by_department"]) == employee_body["total_documents"]


def test_active_users_are_scoped_and_agent_calls_are_admin_only(api, seeded_session):
    now = utcnow()
    users = {user.email: user for user in seeded_session.scalars(select(User))}
    for user in users.values():
        user.last_seen_at = now
    users["sarah.chen@company.com"].last_seen_at = now - timedelta(days=40)
    users["atlas.indexer@company.com"].last_seen_at = now
    seeded_session.add(
        ApiAuditLog(
            user_id=users["alex.morgan@company.com"].id,
            channel=AuditChannel.rest,
            operation="GET /api/v1/search",
            status_code=200,
            duration_ms=4,
            request_summary={"path": "/api/v1/search"},
            created_at=now,
        )
    )
    seeded_session.add(
        ApiAuditLog(
            user_id=users["alex.morgan@company.com"].id,
            channel=AuditChannel.mcp,
            operation="search",
            status_code=200,
            duration_ms=4,
            request_summary={},
            created_at=now - timedelta(days=40),
        )
    )
    seeded_session.flush()

    login(api, "alex.morgan@company.com")
    admin = api.get("/api/v1/dashboard").json()
    assert admin["ai_agent_calls_30d"] == 1
    assert admin["active_users"]["count"] == 4
    assert "Sarah Chen" not in {user["name"] for user in admin["active_users"]["users"]}
    assert "Atlas Indexer" not in {user["name"] for user in admin["active_users"]["users"]}

    login(api, "james.wilson@company.com")
    manager = api.get("/api/v1/dashboard").json()
    assert manager["ai_agent_calls_30d"] is None
    assert manager["active_users"]["count"] == 3
    assert {user["name"] for user in manager["active_users"]["users"]} == {"Alex Morgan", "James Wilson", "Emma Davis"}

    login(api, "emma.davis@company.com")
    employee = api.get("/api/v1/dashboard").json()
    assert employee["active_users"] == {"count": 3, "users": None}
    assert employee["ai_agent_calls_30d"] is None

    login(api, "noah@partner.co")
    guest = api.get("/api/v1/dashboard").json()
    assert guest["active_users"] == {"count": 1, "users": None}
    assert guest["total_documents"] == _visible(seeded_session, users["noah@partner.co"])
    assert PRIVATE_NAME not in api.get("/api/v1/dashboard").text


def _visible(session, user) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Document)
        .where(
            accessible_documents_query(user, scopes_for_role(user.role)),
            Document.status == DocumentStatus.active,
        )
    )


def _added_this_month(session, user) -> int:
    month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return session.scalar(
        select(func.count())
        .select_from(Document)
        .where(
            accessible_documents_query(user, scopes_for_role(user.role)),
            Document.status == DocumentStatus.active,
            Document.created_at >= month_start,
        )
    )


def _code_count(body, code: str) -> int:
    return next(row["count"] for row in body["by_department"] if row["code"] == code)
