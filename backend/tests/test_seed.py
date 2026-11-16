from sqlalchemy import func, select

from app.core.enums import DriveSyncStatus, SourceType, UserRole, Visibility
from app.models import Department, Document, DocumentPermission, DocumentVersion, Folder, User
from app.seed import load_seed
from app.seed_data import CATEGORIES, DEPARTMENTS, DOCUMENTS, FOLDERS, TAG_NAMES, USERS
from app.models import Category, Tag


def test_seed_matches_the_reduced_catalog(seeded_session):
    assert seeded_session.scalar(select(func.count()).select_from(Department)) == len(DEPARTMENTS)
    assert seeded_session.scalar(select(func.count()).select_from(User)) == len(USERS)
    assert seeded_session.scalar(select(func.count()).select_from(Folder)) == len(FOLDERS)
    assert seeded_session.scalar(select(func.count()).select_from(Document)) == len(DOCUMENTS) == 25
    assert seeded_session.scalar(select(func.count()).select_from(Category)) == len(CATEGORIES)
    assert seeded_session.scalar(select(func.count()).select_from(Tag)) == len(TAG_NAMES)

    roles = set(seeded_session.scalars(select(User.role)))
    assert roles == set(UserRole)
    assert seeded_session.scalar(select(func.count()).select_from(User).where(User.is_bot.is_(True))) == 1

    visibilities = set(seeded_session.scalars(select(Document.visibility)))
    assert visibilities == {Visibility.private, Visibility.department, Visibility.organization, Visibility.custom}


def test_folder_tree_materializes_paths(seeded_session):
    policies = seeded_session.scalar(select(Folder).where(Folder.name == "Policies"))
    troubleshooting = seeded_session.scalar(select(Folder).where(Folder.name == "Troubleshooting"))
    root = seeded_session.scalar(select(Folder).where(Folder.parent_id.is_(None)))
    assert root.name == "Company Knowledge"
    assert root.path == "/root"
    assert root.depth == 0
    assert policies.path == "/root/hr/policies"
    assert policies.depth == 2
    assert troubleshooting.path == "/root/products/chatbot/chatbot-troubleshooting"
    assert troubleshooting.depth == 3
    assert policies.visibility == Visibility.organization
    pricing = seeded_session.scalar(select(Folder).where(Folder.name == "Pricing"))
    assert pricing.visibility == Visibility.department


def test_owners_are_remapped_onto_the_seeded_roster(seeded_session):
    playbook = seeded_session.scalar(select(Document).where(Document.name == "Q4 Sales Playbook"))
    noah = seeded_session.scalar(select(User).where(User.email == "noah@partner.co"))
    guide = seeded_session.scalar(select(Document).where(Document.name == "AI Chatbot Integration Guide"))
    bot = seeded_session.scalar(select(User).where(User.is_bot.is_(True)))
    manual = seeded_session.scalar(select(Document).where(Document.name == "ERP Lens Inventory Manual"))
    james = seeded_session.scalar(select(User).where(User.email == "james.wilson@company.com"))
    assert playbook.owner_id == noah.id
    assert guide.owner_id == bot.id
    assert manual.owner_id == james.id
    assert guide.visibility == Visibility.department
    assert manual.source_type == SourceType.google_doc
    assert manual.created_at.isoformat() == "2026-11-01T09:00:00+00:00"
    assert manual.last_modified_at.isoformat() == "2026-11-15T10:30:00+00:00"


def test_skip_google_leaves_drive_unlinked(seeded_session):
    documents = seeded_session.scalars(select(Document)).all()
    assert documents
    assert all(document.google_file_id is None for document in documents)
    assert all(document.google_web_url is None for document in documents)
    assert all(document.drive_sync_status == DriveSyncStatus.not_applicable for document in documents)
    assert all(document.search_vector is not None for document in documents)
    assert all(document.ai_summary is None for document in documents)


def test_google_ids_when_skip_is_disabled(db_session):
    assert load_seed(db_session, skip_google=False) is True
    manual = db_session.scalar(select(Document).where(Document.name == "ERP Lens Inventory Manual"))
    handbook = db_session.scalar(select(Document).where(Document.name == "Employee Handbook 2026"))
    proposal = db_session.scalar(select(Document).where(Document.name == "Customer Proposal Template"))
    assert manual.google_file_id == "atlas-demo-1"
    assert manual.google_web_url == "https://docs.google.com/document/d/atlas-demo-1/edit"
    assert manual.drive_sync_status == DriveSyncStatus.synced
    assert handbook.google_file_id is None
    assert handbook.source_type == SourceType.pdf
    assert proposal.drive_sync_status == DriveSyncStatus.failed
    assert proposal.drive_sync_error
    versions = db_session.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id == handbook.id).order_by(DocumentVersion.version_number)
    ).all()
    assert [version.version_number for version in versions] == [1, 2]
    assert versions[0].change_note == "Initial upload"
    assert versions[1].change_note == "Updated document"


def test_custom_documents_carry_grants(seeded_session):
    deck = seeded_session.scalar(select(Document).where(Document.name == "Company Overview Deck"))
    assert deck.visibility == Visibility.custom
    grants = seeded_session.scalars(select(DocumentPermission).where(DocumentPermission.resource_id == deck.id)).all()
    assert len(grants) == 2
    interview = seeded_session.scalar(select(Document).where(Document.name == "Recruitment Interview Kit"))
    assert interview.visibility == Visibility.private


def test_seed_is_idempotent(db_session):
    assert load_seed(db_session) is True
    assert load_seed(db_session) is False
    assert db_session.scalar(select(func.count()).select_from(Department)) == len(DEPARTMENTS)
