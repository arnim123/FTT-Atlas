from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.dialects import postgresql

from app.core.enums import ActorChannel, DocumentStatus, EventType, Visibility
from app.core.principal import AuthMethod, Principal, scopes_for_role
from app.models import Category, Department, Document, DocumentEvent, DocumentTag, Folder, SearchLog, Tag, User
from app.models.base import utcnow
from app.permissions.engine import accessible_documents_query
from app.seed_ids import seed_id
from app.services.search import PAGE_SIZE_CAP, SearchParams, SearchService, refresh_search_vector
from tests.helpers import login
from tests.library import add_document

INVENTORY = {"ERP Lens Inventory Manual", "Inventory SOP", "Warehouse Process Guide"}
SECRET = "zxsecret ledger"


def test_inventory_search_returns_the_three_seed_documents(api, seeded_session):
    login(api, "alex.morgan@company.com")
    response = api.get("/api/v1/search", params={"q": "Inventory"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 20
    names = [item["name"] for item in body["items"]]
    assert set(names) == INVENTORY
    scores = {item["name"]: item["score"] for item in body["items"]}
    assert scores["Warehouse Process Guide"] < scores["Inventory SOP"]
    assert scores["Warehouse Process Guide"] < scores["ERP Lens Inventory Manual"]

    manual = next(item for item in body["items"] if item["name"] == "ERP Lens Inventory Manual")
    sop = next(item for item in body["items"] if item["name"] == "Inventory SOP")
    warehouse = next(item for item in body["items"] if item["name"] == "Warehouse Process Guide")
    assert manual["folder_path"] == "Company Knowledge / Products / ERP Lens / User Manual"
    assert sop["folder_path"] == "Company Knowledge / Operations / Processes"
    assert "name" in sop["matched_in"]
    assert "tag" in sop["matched_in"]
    assert "name" not in warehouse["matched_in"]
    assert "tag" in warehouse["matched_in"]
    assert "content" in warehouse["matched_in"]
    assert manual["web_url"].endswith(f"/documents/{manual['id']}")
    assert manual["google_url"] is None
    assert manual["snippet"]
    assert "cycle counts" in warehouse["snippet"].lower() or "inventory" in warehouse["snippet"].lower()

    departments = {bucket["name"]: bucket["count"] for bucket in body["facets"]["department"]}
    assert departments == {"Operations": 2, "Product": 1}
    tags = {bucket["name"]: bucket["count"] for bucket in body["facets"]["tags"]}
    assert tags["Inventory"] == 3
    assert sum(bucket["count"] for bucket in body["facets"]["department"]) == 3

    log = seeded_session.scalar(select(SearchLog).where(SearchLog.query == "Inventory"))
    admin = seeded_session.scalar(select(User).where(User.email == "alex.morgan@company.com"))
    assert log.user_id == admin.id
    assert log.result_count == 3
    assert log.channel == ActorChannel.web
    assert log.created_at is not None


def test_partial_name_uses_trigram_similarity(api, seeded_session):
    login(api, "alex.morgan@company.com")
    response = api.get("/api/v1/search", params={"q": "inven"})
    assert response.status_code == 200, response.text
    names = {item["name"] for item in response.json()["items"]}
    assert "Inventory SOP" in names
    assert "ERP Lens Inventory Manual" in names

    suggestions = api.get("/api/v1/search/suggest", params={"q": "inven"})
    assert suggestions.status_code == 200, suggestions.text
    suggested = [item["name"] for item in suggestions.json()["items"]]
    assert suggested
    assert len(suggested) <= 8
    assert "Inventory SOP" in suggested
    assert "ERP Lens Inventory Manual" in suggested
    assert "Warehouse Process Guide" not in suggested


def test_filters_narrow_the_same_permission_set(api, seeded_session):
    login(api, "alex.morgan@company.com")
    operations = seed_id("department:operations")
    james = seed_id("user:u3")
    process = seed_id("tag:Process")
    narrowed = api.get("/api/v1/search", params={"q": "Inventory", "department": str(operations)})
    assert {item["name"] for item in narrowed.json()["items"]} == {"Inventory SOP", "Warehouse Process Guide"}

    owned = api.get("/api/v1/search", params={"q": "Inventory", "owner": str(james)})
    assert {item["name"] for item in owned.json()["items"]} == {"ERP Lens Inventory Manual", "Inventory SOP"}

    tagged = api.get("/api/v1/search", params={"q": "Inventory", "tags": str(process)})
    assert {item["name"] for item in tagged.json()["items"]} == {"Inventory SOP", "Warehouse Process Guide"}

    dated = api.get("/api/v1/search", params={"q": "Inventory", "from": "2026-11-15", "to": "2026-11-15"})
    assert [item["name"] for item in dated.json()["items"]] == ["ERP Lens Inventory Manual"]

    typed = api.get("/api/v1/search", params={"q": "Inventory", "type": "pdf"})
    assert [item["name"] for item in typed.json()["items"]] == ["Warehouse Process Guide"]


def test_archived_documents_stay_hidden_until_requested(api, seeded_session):
    sop = seeded_session.scalar(select(Document).where(Document.name == "Inventory SOP"))
    sop.status = DocumentStatus.archived
    sop.archived_at = utcnow()
    seeded_session.flush()

    login(api, "alex.morgan@company.com")
    hidden = api.get("/api/v1/search", params={"q": "Inventory"})
    assert {item["name"] for item in hidden.json()["items"]} == {"ERP Lens Inventory Manual", "Warehouse Process Guide"}
    shown = api.get("/api/v1/search", params={"q": "Inventory", "include_archived": "true"})
    assert {item["name"] for item in shown.json()["items"]} == INVENTORY

    login(api, "emma.davis@company.com")
    employee = api.get("/api/v1/search", params={"q": "Inventory", "include_archived": "true"})
    assert "Inventory SOP" not in {item["name"] for item in employee.json()["items"]}


def test_guest_never_sees_organization_inventory_documents(api, seeded_session):
    login(api, "noah@partner.co")
    response = api.get("/api/v1/search", params={"q": "Inventory"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["facets"]["department"] == []
    assert body["facets"]["tags"] == []
    payload = response.text.lower()
    assert "inventory sop" not in payload
    assert "cycle counts" not in payload
    suggestions = api.get("/api/v1/search/suggest", params={"q": "Inventory"})
    assert suggestions.json()["items"] == []


def test_private_document_does_not_leak_through_search_or_dashboard(api, seeded_session):
    admin = seeded_session.scalar(select(User).where(User.email == "alex.morgan@company.com"))
    employee = seeded_session.scalar(select(User).where(User.email == "emma.davis@company.com"))
    folder = seeded_session.scalar(select(Folder).where(Folder.name == "Policies"))
    category = seeded_session.scalar(select(Category).where(Category.name == "Policies"))
    department = seeded_session.get(Department, admin.department_id)
    secret = add_document(
        seeded_session,
        name=SECRET,
        folder=folder,
        owner=admin,
        department=department,
        category=category,
        visibility=Visibility.private,
    )
    secret.description = "zxsecret ledger details"
    secret.content_text = "zxsecret ledger body with a private balance"
    secret.original_filename = "zxsecret-ledger.txt"
    secret.created_at = utcnow()
    tag = Tag(name="zxsecret", description="hidden")
    seeded_session.add(tag)
    seeded_session.flush()
    seeded_session.add(DocumentTag(document_id=secret.id, tag_id=tag.id))
    seeded_session.flush()
    refresh_search_vector(seeded_session, secret.id)
    handbook = seeded_session.scalar(select(Document).where(Document.name == "Employee Handbook 2026"))
    seeded_session.add(_view(secret.id, admin.id, utcnow()))
    seeded_session.add(_view(secret.id, admin.id, utcnow()))
    seeded_session.add(_view(handbook.id, employee.id, utcnow()))
    seeded_session.flush()

    login(api, "emma.davis@company.com")
    found = api.get("/api/v1/search", params={"q": "zxsecret"})
    assert found.status_code == 200, found.text
    assert found.json()["total"] == 0
    assert found.json()["items"] == []
    for facet in ("department", "category", "type", "tags"):
        assert found.json()["facets"][facet] == []
    assert "zxsecret" not in found.text.lower()
    assert api.get("/api/v1/search/suggest", params={"q": "zxsecret"}).json()["items"] == []
    broad = api.get("/api/v1/search", params={"q": ""})
    assert "zxsecret" not in broad.text.lower()
    assert all(bucket["name"] != "zxsecret" for bucket in broad.json()["facets"]["tags"])

    dashboard = api.get("/api/v1/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    dash = dashboard.json()
    assert "zxsecret" not in dashboard.text.lower()
    assert all(item["id"] != str(secret.id) for item in dash["recent_uploads"])
    assert all(item["id"] != str(secret.id) for item in dash["most_viewed"])
    assert dash["total_documents"] == _visible_count(seeded_session, employee)
    assert dash["most_viewed"][0]["name"] == "Employee Handbook 2026"

    login(api, "alex.morgan@company.com")
    admin_search = api.get("/api/v1/search", params={"q": "zxsecret"})
    admin_body = admin_search.json()
    assert admin_body["total"] == 1
    hit = admin_body["items"][0]
    assert hit["name"] == SECRET
    assert "zxsecret" in hit["snippet"].lower()
    assert {field for field in hit["matched_in"]} >= {"name", "tag", "description", "content"}
    assert any(bucket["name"] == "zxsecret" and bucket["count"] == 1 for bucket in admin_body["facets"]["tags"])
    admin_dash = api.get("/api/v1/dashboard").json()
    assert admin_dash["recent_uploads"][0]["id"] == str(secret.id)
    assert admin_dash["most_viewed"][0]["id"] == str(secret.id)
    assert admin_dash["most_viewed"][0]["view_count"] == 2
    assert admin_dash["total_documents"] == _visible_count(seeded_session, admin)
    assert admin_dash["total_documents"] > dash["total_documents"]


def test_empty_scopes_hide_every_document(seeded_session):
    admin = seeded_session.scalar(select(User).where(User.email == "alex.morgan@company.com"))
    blind = Principal(user=admin, auth_method=AuthMethod.session, scopes=frozenset())
    result = SearchService(seeded_session).search(blind, SearchParams(q="Inventory"))
    assert result.total == 0
    assert result.items == []
    assert result.facets.tags == []
    assert SearchService(seeded_session).suggest(blind, "Inventory") == []


def test_agent_channel_is_recorded_on_the_shared_service(seeded_session):
    admin = seeded_session.scalar(select(User).where(User.email == "alex.morgan@company.com"))
    principal = Principal(
        user=admin,
        auth_method=AuthMethod.bearer,
        scopes=scopes_for_role(admin.role),
        client_name="agent",
    )
    result = SearchService(seeded_session).search(principal, SearchParams(q="Inventory"))
    assert {item.document.name for item in result.items} == INVENTORY
    log = seeded_session.scalar(select(SearchLog).where(SearchLog.query == "Inventory"))
    assert log.channel == ActorChannel.rest
    assert log.result_count == 3
    assert log.user_id == admin.id


def test_page_size_is_capped_at_fifty(api, seeded_session):
    admin = seeded_session.scalar(select(User).where(User.email == "alex.morgan@company.com"))
    principal = Principal(user=admin, auth_method=AuthMethod.session, scopes=scopes_for_role(admin.role))
    result = SearchService(seeded_session).search(principal, SearchParams(q="", page_size=500))
    assert result.page_size == PAGE_SIZE_CAP
    assert len(result.items) <= PAGE_SIZE_CAP

    login(api, "alex.morgan@company.com")
    rejected = api.get("/api/v1/search", params={"q": "Inventory", "page_size": 51})
    assert rejected.status_code == 422


def test_suggestions_return_at_most_eight_names(seeded_session):
    admin = seeded_session.scalar(select(User).where(User.email == "alex.morgan@company.com"))
    employee = seeded_session.scalar(select(User).where(User.email == "emma.davis@company.com"))
    folder = seeded_session.scalar(select(Folder).limit(1))
    category = seeded_session.scalar(select(Category).limit(1))
    department = seeded_session.get(Department, admin.department_id)
    for index in range(9):
        add_document(
            seeded_session,
            name=f"zzpalette {index}",
            folder=folder,
            owner=admin,
            department=department,
            category=category,
            visibility=Visibility.organization,
        )
    hidden = add_document(
        seeded_session,
        name="zzpalette secret",
        folder=folder,
        owner=admin,
        department=department,
        category=category,
        visibility=Visibility.private,
    )
    seeded_session.flush()
    principal = Principal(user=employee, auth_method=AuthMethod.session, scopes=scopes_for_role(employee.role))
    names = [item.name for item in SearchService(seeded_session).suggest(principal, "zzpalette")]
    assert len(names) == 8
    assert hidden.name not in names
    admin_principal = Principal(user=admin, auth_method=AuthMethod.session, scopes=scopes_for_role(admin.role))
    admin_names = SearchService(seeded_session).suggest(admin_principal, "zzpalette")
    assert len(admin_names) == 8


def test_search_plan_uses_the_text_indexes(seeded_session):
    admin = seeded_session.scalar(select(User).where(User.email == "alex.morgan@company.com"))
    principal = Principal(user=admin, auth_method=AuthMethod.session, scopes=scopes_for_role(admin.role))
    statement = SearchService(seeded_session).match_statement(principal, SearchParams(q="Inventory"))
    seeded_session.execute(text("SET LOCAL enable_seqscan = off"))
    compiled = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    plan = "\n".join(row[0] for row in seeded_session.connection().exec_driver_sql(f"EXPLAIN {compiled}"))
    assert "ix_documents_search_vector" in plan
    assert "ix_documents_name_trgm" in plan
    assert "ix_documents_original_filename_trgm" in plan
    assert "Bitmap Index Scan" in plan or "Index Scan" in plan


def _visible_count(session, user) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Document)
        .where(
            accessible_documents_query(user, scopes_for_role(user.role)),
            Document.status == DocumentStatus.active,
        )
    )


def _view(document_id, user_id, when: datetime):
    return DocumentEvent(
        document_id=document_id,
        user_id=user_id,
        event_type=EventType.view,
        actor_channel=ActorChannel.web,
        event_metadata={},
        created_at=when,
    )
