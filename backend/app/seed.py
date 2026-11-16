"""Load the UI mock catalog.

Run after migrations:

    python -m app.seed

SEED_SKIP_GOOGLE=true (the default) leaves google_file_id, google_mime_type, and google_web_url
empty and sets drive_sync_status to not_applicable. Set it to false to store the demo file ids.
"""

from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.enums import (
    AccessGrant,
    ActorChannel,
    DocumentStatus,
    DriveSyncStatus,
    EventType,
    ExtractionStatus,
    PrincipalType,
    SourceType,
    UserRole,
    Visibility,
)
from app.models import (
    Category,
    Department,
    Document,
    DocumentEvent,
    DocumentPermission,
    DocumentTag,
    DocumentVersion,
    Folder,
    OrgSettings,
    Tag,
    User,
)
from app.seed_data import (
    CATEGORIES,
    DEPARTMENT_FOLDERS,
    DEPARTMENTS,
    DOCUMENTS,
    FOLDER_OWNER_BY_DEPARTMENT,
    FOLDERS,
    OWNER_REMAP,
    TAG_NAMES,
    USERS,
)
from app.seed_ids import seed_id

SOURCE_TYPES = {
    "google-doc": SourceType.google_doc,
    "google-sheet": SourceType.google_sheet,
    "google-slide": SourceType.google_slide,
    "pdf": SourceType.pdf,
    "docx": SourceType.docx,
    "xlsx": SourceType.xlsx,
    "ppt": SourceType.ppt,
    "txt": SourceType.txt,
    "image": SourceType.image,
}

MIME_TYPES = {
    SourceType.google_doc: "application/vnd.google-apps.document",
    SourceType.google_sheet: "application/vnd.google-apps.spreadsheet",
    SourceType.google_slide: "application/vnd.google-apps.presentation",
    SourceType.pdf: "application/pdf",
    SourceType.docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    SourceType.xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    SourceType.ppt: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    SourceType.txt: "text/plain",
    SourceType.image: "image/svg+xml",
}

FILE_EXTENSIONS = {
    SourceType.pdf: "pdf",
    SourceType.docx: "docx",
    SourceType.xlsx: "xlsx",
    SourceType.ppt: "pptx",
    SourceType.txt: "txt",
    SourceType.image: "svg",
}

GOOGLE_URLS = {
    SourceType.google_doc: "https://docs.google.com/document/d/{file_id}/edit",
    SourceType.google_sheet: "https://docs.google.com/spreadsheets/d/{file_id}/edit",
    SourceType.google_slide: "https://docs.google.com/presentation/d/{file_id}/edit",
}

GOOGLE_SOURCES = {SourceType.google_doc, SourceType.google_sheet, SourceType.google_slide}


def load_seed(session: Session, *, skip_google: bool | None = None) -> bool:
    """Insert the catalog. Returns False when departments already exist."""
    if skip_google is None:
        skip_google = get_settings().seed_skip_google
    if session.scalar(select(func.count()).select_from(Department)):
        return False

    for code, name, description in DEPARTMENTS:
        session.add(Department(id=seed_id(f"department:{code}"), code=code, name=name, description=description))
    session.flush()

    for key, name, email, role, department_code, is_bot, last_seen in USERS:
        seen = _parse_time(last_seen)
        session.add(
            User(
                id=seed_id(f"user:{key}"),
                email=email,
                name=name,
                role=UserRole(role),
                department_id=seed_id(f"department:{department_code}"),
                is_active=True,
                is_bot=is_bot,
                last_login_at=seen,
                last_seen_at=seen,
                invited_by=None if key == "u1" else seed_id("user:u1"),
                created_at=seen,
                updated_at=seen,
            )
        )
        # The inviter row has to exist before the self-FK is checked.
        if key == "u1":
            session.flush()
    session.flush()

    for key, name, description in CATEGORIES:
        session.add(Category(id=seed_id(f"category:{key}"), name=name, description=description))
    for name in TAG_NAMES:
        session.add(Tag(id=seed_id(f"tag:{name}"), name=name, description=f"Documents related to {name.lower()}"))
    session.flush()

    child_counts: dict[str | None, int] = {}
    for key, name, parent_key, department_code in FOLDERS:
        sort_order = child_counts.get(parent_key, 0)
        child_counts[parent_key] = sort_order + 1
        path, depth = _folder_path(key)
        owner_key = OWNER_REMAP[FOLDER_OWNER_BY_DEPARTMENT[department_code]]
        session.add(
            Folder(
                id=seed_id(f"folder:{key}"),
                name=name,
                parent_id=None if parent_key is None else seed_id(f"folder:{parent_key}"),
                path=path,
                depth=depth,
                department_id=seed_id(f"department:{department_code}"),
                owner_id=seed_id(f"user:{owner_key}"),
                visibility=Visibility.department if key in DEPARTMENT_FOLDERS else Visibility.organization,
                default_access=AccessGrant.edit,
                sort_order=sort_order,
            )
        )
        session.flush()

    if session.scalar(select(func.count()).select_from(OrgSettings)) == 0:
        session.add(OrgSettings())
        session.flush()

    document_ids: list = []
    for index, (name, ui_type, folder_key, department_code, owner_key, category_key, tags) in enumerate(DOCUMENTS):
        document_id = _insert_document(
            session,
            index=index,
            name=name,
            ui_type=ui_type,
            folder_key=folder_key,
            department_code=department_code,
            owner_key=OWNER_REMAP[owner_key],
            category_key=category_key,
            tags=tags,
            skip_google=skip_google,
        )
        document_ids.append(document_id)

    for document_id in document_ids:
        session.execute(
            text("SELECT refresh_search_vector(CAST(:document_id AS uuid))"),
            {"document_id": document_id},
        )
    session.expire_all()
    return True


def _insert_document(
    session: Session,
    *,
    index: int,
    name: str,
    ui_type: str,
    folder_key: str,
    department_code: str,
    owner_key: str,
    category_key: str,
    tags: list[str],
    skip_google: bool,
) -> object:
    source = SOURCE_TYPES[ui_type]
    created_at = _created_at(index)
    modified_at = _modified_at(index)
    description = _description(index, name, department_code)
    content = _content(name, description, department_code, tags)
    version = 1 + index % 4
    size = 128000 + index * 58000
    extension = FILE_EXTENSIONS.get(source)
    document_id = seed_id(f"document:{index + 1}")
    owner_id = seed_id(f"user:{owner_key}")
    filename = f"{name}.{extension}" if extension else None
    storage_key = f"documents/{document_id}/v{version}/{filename}" if filename else None
    drive = _drive_fields(index, source, skip_google)

    session.add(
        Document(
            id=document_id,
            name=name,
            description=description,
            folder_id=seed_id(f"folder:{folder_key}"),
            category_id=seed_id(f"category:{category_key}"),
            department_id=seed_id(f"department:{department_code}"),
            owner_id=owner_id,
            source_type=source,
            storage_key=storage_key,
            original_filename=filename,
            mime_type=MIME_TYPES[source],
            size_bytes=size,
            current_version_number=version,
            visibility=_visibility(index),
            default_access=AccessGrant.view,
            status=DocumentStatus.active,
            last_modified_at=modified_at,
            content_text=content,
            content_hash=sha256(content.encode("utf-8")).hexdigest(),
            extraction_status=ExtractionStatus.done,
            extracted_at=modified_at,
            created_at=created_at,
            updated_at=modified_at,
            **drive,
        )
    )
    session.flush()

    for tag_name in tags:
        session.add(DocumentTag(document_id=document_id, tag_id=seed_id(f"tag:{tag_name}")))

    if filename:
        for number in range(1, version + 1):
            age = version - number
            stamped = modified_at - timedelta(days=7 * age)
            session.add(
                DocumentVersion(
                    id=seed_id(f"version:{index + 1}:{number}"),
                    document_id=document_id,
                    version_number=number,
                    storage_key=f"documents/{document_id}/v{number}/{filename}",
                    original_filename=filename,
                    mime_type=MIME_TYPES[source],
                    size_bytes=size - age * 10000,
                    uploaded_by=owner_id,
                    change_note="Initial upload" if number == 1 else "Updated document",
                    created_at=stamped,
                    updated_at=stamped,
                )
            )

    if _visibility(index) is Visibility.custom:
        session.add(
            DocumentPermission(
                id=seed_id(f"permission:{index + 1}:user"),
                resource_id=document_id,
                principal_type=PrincipalType.user,
                principal_id=seed_id("user:u5"),
                access=AccessGrant.view,
                created_by=owner_id,
            )
        )
        session.add(
            DocumentPermission(
                id=seed_id(f"permission:{index + 1}:department"),
                resource_id=document_id,
                principal_type=PrincipalType.department,
                principal_id=seed_id("department:sales"),
                access=AccessGrant.edit,
                created_by=owner_id,
            )
        )

    session.add(
        DocumentEvent(
            id=seed_id(f"event:create:{index + 1}"),
            document_id=document_id,
            user_id=owner_id,
            event_type=EventType.create,
            actor_channel=ActorChannel.web,
            client_name="Atlas web",
            event_metadata={"source": "seed"},
            created_at=created_at,
        )
    )
    session.flush()
    return document_id


def _drive_fields(index: int, source: SourceType, skip_google: bool) -> dict:
    if skip_google:
        return {
            "google_file_id": None,
            "google_mime_type": None,
            "google_web_url": None,
            "drive_sync_status": DriveSyncStatus.not_applicable,
            "drive_sync_error": None,
        }
    status = DriveSyncStatus.synced
    error = None
    if index == 18:
        status = DriveSyncStatus.failed
        error = "Google could not confirm this file is shared with the service account."
    elif index == 35:
        status = DriveSyncStatus.pending
    linked = source in GOOGLE_SOURCES
    file_id = f"atlas-demo-{index + 1}" if linked else None
    return {
        "google_file_id": file_id,
        "google_mime_type": MIME_TYPES[source] if linked else None,
        "google_web_url": GOOGLE_URLS[source].format(file_id=file_id) if linked and file_id else None,
        "drive_sync_status": status,
        "drive_sync_error": error,
    }


def _visibility(index: int) -> Visibility:
    if index in {16, 18, 35, 49}:
        return Visibility.custom
    if index in {23, 39, 44}:
        return Visibility.private
    if index % 7 == 3 or index in {17, 27}:
        return Visibility.department
    return Visibility.organization


def _description(index: int, name: str, department_code: str) -> str:
    if index == 0:
        return "Your complete guide to inventory management in ERP Lens."
    if index == 5:
        return "Standard operating procedures for managing inventory across locations."
    if index == 6:
        return "A practical guide to warehouse operations, stock handling, and inventory."
    team = "people" if department_code == "hr" else department_code
    return f"{name.split(' · ')[0]} — a shared resource for the {team} team."


def _content(name: str, description: str, department_code: str, tags: list[str]) -> str:
    team = "People & Culture" if department_code == "hr" else department_code
    inventory = ""
    if "Inventory" in tags:
        inventory = (
            "Inventory management\n"
            "Keep stock levels accurate with regular cycle counts. Use the ERP Lens dashboard to track receipts, "
            "transfers, and warehouse stock. Reconcile inventory weekly and report discrepancies to Operations.\n\n"
        )
    return (
        f"{name}\n\n"
        f"Overview\n{description}\n\n"
        "This document brings together the information, workflows, and best practices you need to work with confidence. "
        f"It is maintained by our {team} team and reviewed regularly.\n\n"
        "Getting started\n"
        "1. Review the prerequisites and make sure you have the right access.\n"
        "2. Follow the setup steps with your team lead.\n"
        "3. Use the checklist to verify your work before sharing it.\n\n"
        f"{inventory}"
        "Best practices\n"
        "Keep your information up to date. Document decisions where your team can find them. "
        "When something changes, update the source document and let the relevant owners know.\n\n"
        "Need a hand?\n"
        "Reach out to the document owner or your department manager for help."
    )


def _created_at(index: int) -> datetime:
    if index < 16:
        return datetime(2026, 11, 1 + (index % 14), 9, tzinfo=UTC)
    return datetime(2026, 10, 5 + (index % 20), 9, tzinfo=UTC)


def _modified_at(index: int) -> datetime:
    return datetime(2026, 11, 15 - (index // 3), 10 - (index % 3), 30, tzinfo=UTC)


def _folder_path(key: str) -> tuple[str, int]:
    parents = {item[0]: item[2] for item in FOLDERS}
    parts: list[str] = []
    current: str | None = key
    while current is not None:
        parts.append(current)
        current = parents[current]
    parts.reverse()
    return "/" + "/".join(parts), len(parts) - 1


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    session = SessionLocal()
    try:
        inserted = load_seed(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print("Seed complete." if inserted else "Database already seeded; skipping.")


if __name__ == "__main__":
    main()
