import enum

from sqlalchemy import Enum


def _values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(enum_cls, name=name, native_enum=True, values_callable=_values)


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    manager = "manager"
    employee = "employee"
    guest = "guest"


class Visibility(str, enum.Enum):
    private = "private"
    department = "department"
    organization = "organization"
    custom = "custom"


class AccessGrant(str, enum.Enum):
    view = "view"
    edit = "edit"


class SourceType(str, enum.Enum):
    google_doc = "google_doc"
    google_sheet = "google_sheet"
    google_slide = "google_slide"
    pdf = "pdf"
    docx = "docx"
    xlsx = "xlsx"
    ppt = "ppt"
    txt = "txt"
    image = "image"


class DocumentStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class DriveSyncStatus(str, enum.Enum):
    pending = "pending"
    synced = "synced"
    failed = "failed"
    not_applicable = "not_applicable"


class ExtractionStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    skipped = "skipped"
    failed = "failed"


class PrincipalType(str, enum.Enum):
    user = "user"
    department = "department"


class EventType(str, enum.Enum):
    view = "view"
    download = "download"
    create = "create"
    update = "update"
    move = "move"
    archive = "archive"
    restore = "restore"
    delete = "delete"
    share = "share"
    read_content = "read_content"


class ActorChannel(str, enum.Enum):
    web = "web"
    rest = "rest"
    mcp = "mcp"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class ConversationScope(str, enum.Enum):
    organization = "organization"
    document = "document"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class AuditChannel(str, enum.Enum):
    rest = "rest"
    mcp = "mcp"


user_role_enum = pg_enum(UserRole, "user_role")
visibility_enum = pg_enum(Visibility, "visibility")
access_grant_enum = pg_enum(AccessGrant, "access_grant")
source_type_enum = pg_enum(SourceType, "source_type")
document_status_enum = pg_enum(DocumentStatus, "document_status")
drive_sync_status_enum = pg_enum(DriveSyncStatus, "drive_sync_status")
extraction_status_enum = pg_enum(ExtractionStatus, "extraction_status")
principal_type_enum = pg_enum(PrincipalType, "principal_type")
event_type_enum = pg_enum(EventType, "event_type")
actor_channel_enum = pg_enum(ActorChannel, "actor_channel")
job_status_enum = pg_enum(JobStatus, "job_status")
conversation_scope_enum = pg_enum(ConversationScope, "conversation_scope")
message_role_enum = pg_enum(MessageRole, "message_role")
audit_channel_enum = pg_enum(AuditChannel, "audit_channel")
