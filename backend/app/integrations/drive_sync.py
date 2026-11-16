"""Share Google files so Drive matches this app.

The database decides who may open a file. Drive's permission list is what we
diff against, then we create, update, or delete until it matches.

Owner and admins are writers. Explicit grants and department visibility are
expanded to people. Organization visibility is one domain permission on the
company domain; guests are shared one by one. Private, archived, and
soft-deleted files keep only the owner and admins. Bots are never shared:
they read through this API.

The service account, the file owner, and Shared Drive members (inherited
permissions, plus organizer and fileOrganizer roles) are left alone.

Sync runs after the commit that changed access. Failures are stored on
`drive_sync_status` and retried by `reconcile_drive_sync`.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event, Thread
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal, current_request_session
from app.core.enums import (
    AccessGrant,
    DocumentStatus,
    DriveSyncStatus,
    PrincipalType,
    SourceType,
    UserRole,
    Visibility,
)
from app.core.events import (
    DOCUMENT_ARCHIVED,
    DOCUMENT_CREATED,
    DOCUMENT_DELETED,
    DOCUMENT_PERMISSIONS_CHANGED,
    DOCUMENT_RESTORED,
    DOCUMENT_UPDATED,
    USER_ACCESS_CHANGED,
    event_bus,
)
from app.integrations.drive import (
    DriveError,
    DrivePermission,
    GoogleDriveClient,
    build_drive_client,
)
from app.models.document import Document
from app.models.permission import DocumentPermission
from app.models.user import User
from app.services.grants import load_grants

READER = "reader"
WRITER = "writer"
GOOGLE_SOURCES = {SourceType.google_doc, SourceType.google_sheet, SourceType.google_slide}
_ADMIN_ROLES = {UserRole.super_admin, UserRole.admin}
_PROTECTED_ROLES = {"owner", "organizer", "fileOrganizer"}
_ROLE_RANK = {"reader": 1, "commenter": 1, "writer": 2, "fileOrganizer": 3, "organizer": 3, "owner": 3}

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="drive-sync")
_stop = Event()
_reconcile_started = False


@dataclass(frozen=True)
class DesiredPermissions:
    """People to share, plus at most one company-domain permission."""

    users: dict[str, str]
    domain: str | None = None
    domain_role: str | None = None


@dataclass(frozen=True)
class DriveChange:
    op: str
    permission_id: str | None = None
    role: str | None = None
    email: str | None = None
    domain: str | None = None
    permission_type: str = "user"


def compute_desired_permissions(session: Session, document: Document) -> DesiredPermissions:
    """Return the shares this document should have on Drive."""
    eligible = list(session.scalars(select(User).where(User.is_active.is_(True), User.is_bot.is_(False))))
    by_id = {user.id: user for user in eligible}
    users: dict[str, str] = {}

    def allow(user: User | None, role: str) -> None:
        if user is None or not user.is_active or user.is_bot:
            return
        email = user.email.strip().lower()
        if "@" not in email:
            return
        current = users.get(email)
        if current == WRITER:
            return
        if current is None or role == WRITER:
            users[email] = role

    allow(by_id.get(document.owner_id), WRITER)
    for user in eligible:
        if user.role in _ADMIN_ROLES:
            allow(user, WRITER)

    closed = (
        document.deleted_at is not None
        or document.status == DocumentStatus.archived
        or document.visibility == Visibility.private
    )
    if closed:
        return DesiredPermissions(users=users)

    for user in eligible:
        if user.role == UserRole.manager and user.department_id == document.department_id:
            allow(user, WRITER)

    for grant in load_grants(session, DocumentPermission, document.id):
        role = WRITER if grant.access == AccessGrant.edit else READER
        if grant.principal_type == PrincipalType.user:
            allow(by_id.get(grant.principal_id), role)
            continue
        if grant.principal_type != PrincipalType.department:
            continue
        for user in eligible:
            if user.department_id == grant.principal_id:
                allow(user, role)

    if document.visibility == Visibility.department:
        role = WRITER if document.default_access == AccessGrant.edit else READER
        for user in eligible:
            if user.department_id == document.department_id and user.role != UserRole.guest:
                allow(user, role)
        return DesiredPermissions(users=users)

    if document.visibility == Visibility.organization:
        role = WRITER if document.default_access == AccessGrant.edit else READER
        domain = get_settings().resolved_company_domain() or None
        return DesiredPermissions(users=users, domain=domain, domain_role=role)

    return DesiredPermissions(users=users)


def plan_drive_changes(
    desired: DesiredPermissions,
    actual: list[DrivePermission],
    *,
    service_account_email: str,
    owner_emails: set[str],
) -> list[DriveChange]:
    """Diff desired shares against Drive. Protected permissions are omitted."""
    service_email = service_account_email.strip().lower()
    owners = {email.strip().lower() for email in owner_emails if email and email.strip()}

    def protected(permission: DrivePermission) -> bool:
        email = (permission.email or "").strip().lower()
        if permission.inherited or permission.role in _PROTECTED_ROLES:
            return True
        if email and (email == service_email or email in owners):
            return True
        return False

    changes: list[DriveChange] = []
    manageable: dict[str, list[DrivePermission]] = {}
    protected_rank: dict[str, int] = {}
    domain_permissions: list[DrivePermission] = []

    for permission in actual:
        if permission.deleted and not protected(permission):
            changes.append(DriveChange(op="delete", permission_id=permission.id))
            continue
        if permission.type == "user" and permission.email:
            email = permission.email.strip().lower()
            if protected(permission):
                protected_rank[email] = max(protected_rank.get(email, 0), _ROLE_RANK.get(permission.role, 0))
            else:
                manageable.setdefault(email, []).append(permission)
            continue
        if permission.type == "domain" and permission.domain:
            domain_permissions.append(permission)
            continue
        if not protected(permission):
            changes.append(DriveChange(op="delete", permission_id=permission.id))

    desired_users = {
        email.strip().lower(): role
        for email, role in desired.users.items()
        if email and email.strip().lower() != service_email
    }
    for email, role in desired_users.items():
        existing = manageable.pop(email, [])
        if not existing:
            if protected_rank.get(email, 0) >= _ROLE_RANK.get(role, 1):
                continue
            changes.append(DriveChange(op="create", role=role, email=email, permission_type="user"))
            continue
        primary, *extra = existing
        if primary.role != role:
            changes.append(DriveChange(op="update", permission_id=primary.id, role=role, email=email))
        for permission in extra:
            changes.append(DriveChange(op="delete", permission_id=permission.id))

    for permissions in manageable.values():
        for permission in permissions:
            changes.append(DriveChange(op="delete", permission_id=permission.id))

    wanted_domain = desired.domain.strip().lower() if desired.domain and desired.domain_role else None
    wanted_role = desired.domain_role
    kept_direct = False
    protected_satisfies = False
    for permission in domain_permissions:
        domain = permission.domain.strip().lower() if permission.domain else ""
        is_target = wanted_domain is not None and domain == wanted_domain
        if protected(permission):
            if is_target and _ROLE_RANK.get(permission.role, 0) >= _ROLE_RANK.get(wanted_role or "", 1):
                protected_satisfies = True
            continue
        if is_target and not kept_direct:
            kept_direct = True
            if permission.role != wanted_role:
                changes.append(
                    DriveChange(
                        op="update",
                        permission_id=permission.id,
                        role=wanted_role,
                        domain=domain,
                        permission_type="domain",
                    )
                )
            continue
        changes.append(DriveChange(op="delete", permission_id=permission.id))

    if wanted_domain and wanted_role and not protected_satisfies and not kept_direct:
        changes.append(DriveChange(op="create", role=wanted_role, domain=wanted_domain, permission_type="domain"))
    return changes


def apply_drive_changes(client: GoogleDriveClient, file_id: str, changes: list[DriveChange]) -> None:
    order = {"delete": 0, "update": 1, "create": 2}
    for change in sorted(changes, key=lambda item: order.get(item.op, 9)):
        if change.op == "delete" and change.permission_id:
            client.delete_permission(file_id, change.permission_id)
        elif change.op == "update" and change.permission_id and change.role:
            client.update_permission(file_id, change.permission_id, role=change.role)
        elif change.op == "create" and change.role:
            client.create_permission(
                file_id,
                role=change.role,
                email=change.email,
                domain=change.domain,
                permission_type=change.permission_type,
            )


def sync_document_sharing(session: Session, document: Document, client: GoogleDriveClient | None = None) -> bool:
    """Push this document's shares to Drive. Returns True when the row was updated."""
    if document.google_file_id is None or document.source_type not in GOOGLE_SOURCES:
        return False
    client = client or build_drive_client()
    try:
        desired = compute_desired_permissions(session, document)
        if desired.domain_role and not desired.domain:
            _mark(document, DriveSyncStatus.failed, "Company domain is not configured.")
            session.flush()
            return True
        metadata = client.get_file_metadata(document.google_file_id)
        actual = client.list_permissions(document.google_file_id)
        changes = plan_drive_changes(
            desired,
            actual,
            service_account_email=client.service_account_email,
            owner_emails=set(metadata.owner_emails),
        )
        apply_drive_changes(client, document.google_file_id, changes)
        _mark(document, DriveSyncStatus.synced, None)
    except DriveError as exc:
        _mark(document, DriveSyncStatus.failed, exc.message[:500])
    session.flush()
    return True


def reconcile_drive_sync(session: Session, client: GoogleDriveClient | None = None) -> int:
    """Retry Google files whose last sync failed. Returns how many were attempted."""
    documents = list(
        session.scalars(
            select(Document).where(
                Document.google_file_id.is_not(None),
                Document.drive_sync_status == DriveSyncStatus.failed,
            )
        )
    )
    for document in documents:
        sync_document_sharing(session, document, client)
    return len(documents)


def register_drive_sync_handlers() -> None:
    event_bus.subscribe(DOCUMENT_CREATED, _on_document)
    event_bus.subscribe(DOCUMENT_PERMISSIONS_CHANGED, _on_document)
    event_bus.subscribe(DOCUMENT_UPDATED, _on_document_updated)
    event_bus.subscribe(DOCUMENT_ARCHIVED, _on_document)
    event_bus.subscribe(DOCUMENT_RESTORED, _on_document)
    event_bus.subscribe(DOCUMENT_DELETED, _on_document_deleted)
    event_bus.subscribe(USER_ACCESS_CHANGED, _on_user_access_changed)


def start_reconcile_scheduler() -> None:
    """Hourly retry while the API runs in live mode. Tests and fake mode stay quiet."""
    global _reconcile_started
    if get_settings().google_mode.strip().lower() != "live" or _reconcile_started:
        return
    _reconcile_started = True
    _stop.clear()
    Thread(target=_reconcile_loop, name="drive-reconcile", daemon=True).start()


def stop_reconcile_scheduler() -> None:
    _stop.set()


def run_reconcile_once() -> int:
    """One pass for cron: `python -m app.integrations.drive_sync`."""
    session = SessionLocal()
    try:
        count = reconcile_drive_sync(session)
        session.commit()
        return count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _on_document(payload: dict) -> None:
    document_id = payload.get("document_id")
    if not document_id:
        return
    _dispatch(lambda session: _sync_id(session, document_id), document_id)


def _on_document_updated(payload: dict) -> None:
    fields = payload.get("fields")
    if isinstance(fields, list) and "department" not in fields:
        return
    _on_document(payload)


def _on_document_deleted(payload: dict) -> None:
    if payload.get("permanent"):
        return
    _on_document(payload)


def _on_user_access_changed(payload: dict) -> None:
    def work(session: Session) -> bool:
        identifiers = list(session.scalars(select(Document.id).where(Document.google_file_id.is_not(None))))
        if not identifiers:
            return False
        for document_id in identifiers:
            document = session.get(Document, document_id)
            if document is not None:
                sync_document_sharing(session, document)
        return True

    _dispatch(work, payload.get("user_id"))


def _sync_id(session: Session, document_id: object) -> bool:
    try:
        identifier = UUID(str(document_id))
    except ValueError:
        return False
    document = session.get(Document, identifier)
    if document is None:
        return False
    return sync_document_sharing(session, document)


def _dispatch(work: Callable[[Session], bool], document_id: object | None = None) -> None:
    if get_settings().drive_sync_runs_inline():
        bound = current_request_session()
        if bound is None:
            return
        changed = False
        try:
            changed = work(bound)
        except Exception:
            if document_id is not None:
                changed = _fail_quietly(bound, document_id)
        if changed:
            try:
                bound.commit()
            except Exception:
                bound.rollback()
        return
    _executor.submit(_background, work)


def _background(work: Callable[[Session], bool]) -> None:
    session = SessionLocal()
    try:
        if work(session):
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
    finally:
        session.close()


def _fail_quietly(session: Session, document_id: object) -> bool:
    try:
        identifier = UUID(str(document_id))
    except ValueError:
        return False
    document = session.get(Document, identifier)
    if document is None or document.google_file_id is None:
        return False
    _mark(document, DriveSyncStatus.failed, "Drive sync failed.")
    session.flush()
    return True


def _mark(document: Document, status: DriveSyncStatus, error: str | None) -> None:
    document.drive_sync_status = status
    document.drive_sync_error = error


def _reconcile_loop() -> None:
    while not _stop.wait(3600):
        session = SessionLocal()
        try:
            reconcile_drive_sync(session)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()


if __name__ == "__main__":
    run_reconcile_once()
