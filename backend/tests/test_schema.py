import re

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import (
    AccessGrant,
    ActorChannel,
    AuditChannel,
    ConversationScope,
    EventType,
    ExtractionStatus,
    JobStatus,
    MessageRole,
    PrincipalType,
    SourceType,
    UserRole,
    Visibility,
)
from app.core.security import hash_token
from app.models import (
    AiConversation,
    AiMessage,
    ApiAuditLog,
    ApiToken,
    Category,
    Department,
    Document,
    DocumentChunk,
    DocumentEvent,
    DocumentTag,
    DocumentVersion,
    Folder,
    FolderPermission,
    IngestionJob,
    OrgSettings,
    Tag,
    User,
)
from app.seed_ids import seed_id

REQUIRED_INDEXES = {
    "ix_documents_search_vector",
    "ix_documents_name_trgm",
    "ix_documents_original_filename_trgm",
    "ix_search_logs_user_id_created_at",
    "ix_folders_path_pattern",
    "ix_documents_folder_id",
    "ix_documents_owner_id",
    "ix_document_events_document_id_created_at",
    "ix_api_audit_logs_created_at",
    "ix_api_audit_logs_user_id_created_at",
    "ix_api_tokens_token_prefix",
    "uq_document_versions_document_version",
}


def test_extensions_and_indexes(engine):
    with engine.connect() as connection:
        extensions = set(connection.scalars(text("SELECT extname FROM pg_extension")))
        indexes = set(connection.scalars(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")))
        version = connection.scalar(text("SELECT version_num FROM alembic_version"))
        definition = connection.scalar(text("SELECT pg_get_functiondef('refresh_search_vector(uuid)'::regprocedure)"))
    assert {"pg_trgm", "vector", "pgcrypto"} <= extensions
    assert REQUIRED_INDEXES <= indexes
    assert version == "0003_oauth"
    for weight in ("'A'", "'B'", "'C'", "'D'"):
        assert weight in definition


def test_org_settings_is_a_single_default_row(engine, db_session):
    with Session(engine) as session:
        row = session.scalar(select(OrgSettings))
        assert row is not None
        assert row.external_ai_enabled is True
        assert row.allow_write_scopes is False
        assert row.max_token_days == 365
        assert session.scalar(select(func.count()).select_from(OrgSettings)) == 1

    db_session.add(OrgSettings())
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_search_vector_weights(db_session):
    department = db_session.get(Department, seed_id("department:product"))
    if department is None:
        department = Department(code="lab", name="Lab", description="Lab")
        db_session.add(department)
        db_session.flush()
    owner = User(
        email="weight@company.com",
        name="Weight Tester",
        role=UserRole.employee,
        department_id=department.id,
        is_active=True,
        is_bot=False,
    )
    db_session.add(owner)
    db_session.flush()
    folder = Folder(
        name="Lab",
        path=f"/lab-{department.id}",
        depth=0,
        department_id=department.id,
        owner_id=owner.id,
        visibility=Visibility.organization,
        default_access=AccessGrant.view,
    )
    category = Category(name="qxgamma", description="weight probe")
    tag = Tag(name="qxbeta", description="weight probe")
    db_session.add_all([folder, category, tag])
    db_session.flush()
    document = Document(
        name="qxalpha",
        description="qxdelta",
        folder_id=folder.id,
        category_id=category.id,
        department_id=department.id,
        owner_id=owner.id,
        source_type=SourceType.txt,
        visibility=Visibility.organization,
        default_access=AccessGrant.view,
        content_text="qxepsilon",
        extraction_status=ExtractionStatus.done,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(DocumentTag(document_id=document.id, tag_id=tag.id))
    db_session.flush()
    db_session.execute(text("SELECT refresh_search_vector(CAST(:document_id AS uuid))"), {"document_id": document.id})
    vector = db_session.execute(
        text("SELECT search_vector::text FROM documents WHERE id = :document_id"),
        {"document_id": document.id},
    ).scalar_one()
    weights = _lexeme_weights(vector)
    assert weights.get("qxalpha") == {"A"}, vector
    assert weights.get("qxbeta") == {"B"}, vector
    assert weights.get("qxgamma") == {"B"}, vector
    assert weights.get("qxdelta") == {"C"}, vector
    assert weights.get("qxepsilon") == {"D"}, vector


def test_remaining_tables_accept_a_row(seeded_session):
    user = seeded_session.scalar(select(User).where(User.is_bot.is_(True)))
    document = seeded_session.scalar(select(Document).limit(1))
    folder = seeded_session.scalar(select(Folder).limit(1))
    seeded_session.add(
        DocumentChunk(
            document_id=document.id,
            version_number=1,
            chunk_index=0,
            text="A passage with no embedding column.",
            token_count=6,
            heading_path="Overview",
            content_hash="abc",
        )
    )
    seeded_session.add(IngestionJob(document_id=document.id, job_type="extract", status=JobStatus.pending))
    conversation = AiConversation(user_id=user.id, scope=ConversationScope.organization, title="Unused in phase 1")
    seeded_session.add(conversation)
    seeded_session.flush()
    seeded_session.add(AiMessage(conversation_id=conversation.id, role=MessageRole.user, content="Hello", sources=[]))
    token = ApiToken(
        user_id=user.id,
        name="pytest",
        token_prefix="dms_pat_test",
        token_hash=hash_token("dms_pat_test_secret"),
        scopes=["docs:read"],
        created_by=user.id,
    )
    seeded_session.add(token)
    seeded_session.flush()
    seeded_session.add(
        ApiAuditLog(
            token_id=token.id,
            user_id=user.id,
            channel=AuditChannel.rest,
            operation="GET /api/v1/health",
            status_code=200,
            duration_ms=12,
            request_summary={"path": "/api/v1/health"},
        )
    )
    seeded_session.add(
        DocumentEvent(
            document_id=document.id,
            user_id=user.id,
            event_type=EventType.view,
            actor_channel=ActorChannel.mcp,
            token_id=token.id,
            client_name="pytest",
            event_metadata={"source": "test"},
        )
    )
    seeded_session.add(
        FolderPermission(
            resource_id=folder.id,
            principal_type=PrincipalType.department,
            principal_id=user.department_id,
            access=AccessGrant.view,
            created_by=user.id,
        )
    )
    seeded_session.flush()
    assert seeded_session.scalar(select(func.count()).select_from(DocumentChunk)) == 1
    assert seeded_session.scalar(select(func.count()).select_from(AiMessage)) == 1
    assert "embedding" not in DocumentChunk.__table__.c.keys()


def test_duplicate_version_is_rejected(seeded_session):
    existing = seeded_session.scalars(select(DocumentVersion)).first()
    assert existing is not None
    seeded_session.add(
        DocumentVersion(
            document_id=existing.document_id,
            version_number=existing.version_number,
            change_note="duplicate",
        )
    )
    with pytest.raises(IntegrityError):
        seeded_session.flush()
    seeded_session.rollback()


def _lexeme_weights(vector: str) -> dict[str, set[str]]:
    """Parse a tsvector literal. PostgreSQL omits the letter for the default weight D."""
    found: dict[str, set[str]] = {}
    for lexeme, positions in re.findall(r"'([^']+)':([0-9A-D,]+)", vector):
        letters = set(re.findall(r"[A-D]", positions))
        found[lexeme] = letters or {"D"}
    return found
