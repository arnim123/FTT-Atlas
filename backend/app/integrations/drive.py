"""Google Drive adapter.

`GoogleDriveClient` is the boundary. `ServiceAccountDriveClient` talks to Drive
with a service account. `FakeDriveClient` keeps files in memory when
`GOOGLE_MODE` is not `live`, so the app and the tests run without Google.

Every live call passes `supportsAllDrives=True`. Rate limits, HTTP 429, and 5xx
responses are retried with exponential backoff. A 403 that is not a rate limit
is not retried.
"""

import base64
import json
import re
import time
from dataclasses import dataclass, replace
from threading import Lock
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.enums import SourceType
from app.core.errors import ApiError

DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive",)
EXPORT_MIME = "text/plain"
DEFAULT_SERVICE_ACCOUNT_EMAIL = "atlas-drive@company.iam.gserviceaccount.com"
DEMO_SHARED_FILE_ID = "atlasDemoSharedDoc01"
MIME_DOCUMENT = "application/vnd.google-apps.document"
MIME_SPREADSHEET = "application/vnd.google-apps.spreadsheet"
MIME_PRESENTATION = "application/vnd.google-apps.presentation"

MIME_BY_SOURCE = {
    SourceType.google_doc: MIME_DOCUMENT,
    SourceType.google_sheet: MIME_SPREADSHEET,
    SourceType.google_slide: MIME_PRESENTATION,
}
SOURCE_BY_MIME = {mime: source for source, mime in MIME_BY_SOURCE.items()}
PATH_BY_SOURCE = {
    SourceType.google_doc: "document",
    SourceType.google_sheet: "spreadsheets",
    SourceType.google_slide: "presentation",
}
SOURCE_BY_PATH = {path: source for source, path in PATH_BY_SOURCE.items()}

FILE_FIELDS = "id,name,mimeType,webViewLink,modifiedTime,trashed,parents,owners(emailAddress)"
PERMISSION_FIELDS = "id,type,role,emailAddress,domain,deleted,permissionDetails(inherited)"
PERMISSION_LIST_FIELDS = f"nextPageToken,permissions({PERMISSION_FIELDS})"
_DRIVE = {"supportsAllDrives": True}
_RATE_REASONS = frozenset(
    {"rateLimitExceeded", "userRateLimitExceeded", "sharingRateLimitExceeded", "quotaExceeded"}
)
_URL = re.compile(
    r"^https://docs\.google\.com/"
    r"(document|spreadsheets|presentation)"
    r"(?:/u/\d+)?"
    r"/d/([A-Za-z0-9_-]{10,})"
    r"(?:/(?:edit|view|preview))?"
    r"/?"
    r"(?:[?#].*)?$",
    re.IGNORECASE,
)
_FILE_ID = re.compile(r"^[A-Za-z0-9_-]{10,}$")

_fake: "FakeDriveClient | None" = None
_fake_email: str | None = None
_live: "ServiceAccountDriveClient | None" = None


class InvalidGoogleUrl(ValueError):
    """The string is not a Docs, Sheets, or Slides URL or file id."""


class DriveError(Exception):
    def __init__(self, status_code: int, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.reason = reason


class DriveNotFound(DriveError):
    def __init__(self, file_id: str) -> None:
        super().__init__(404, "Google file not found.", reason="notFound")
        self.file_id = file_id


class DriveForbidden(DriveError):
    def __init__(self, message: str = "The service account cannot open this Google file.") -> None:
        super().__init__(403, message, reason="forbidden")


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    mime_type: str
    web_view_link: str | None
    modified_time: datetime | None
    trashed: bool
    parents: tuple[str, ...]
    owner_emails: tuple[str, ...]


@dataclass(frozen=True)
class DrivePermission:
    id: str
    type: str
    role: str
    email: str | None = None
    domain: str | None = None
    inherited: bool = False
    deleted: bool = False


@dataclass(frozen=True)
class ParsedGoogleUrl:
    file_id: str
    source_type: SourceType


@dataclass(frozen=True)
class GoogleUrls:
    preview_url: str
    edit_url: str
    open_url: str


class GoogleDriveClient(Protocol):
    service_account_email: str

    def get_file_metadata(self, file_id: str) -> DriveFile: ...

    def create_file(
        self, *, title: str, mime_type: str, folder_id: str, template_id: str | None = None
    ) -> DriveFile: ...

    def list_permissions(self, file_id: str) -> list[DrivePermission]: ...

    def create_permission(
        self,
        file_id: str,
        *,
        role: str,
        email: str | None = None,
        domain: str | None = None,
        permission_type: str = "user",
    ) -> DrivePermission: ...

    def update_permission(self, file_id: str, permission_id: str, *, role: str) -> DrivePermission: ...

    def delete_permission(self, file_id: str, permission_id: str) -> None: ...

    def export_text(self, file_id: str) -> str: ...

    def trash_file(self, file_id: str) -> None: ...


def parse_google_url(url: str) -> ParsedGoogleUrl:
    """Accept Docs, Sheets, and Slides links, including /u/0/, /edit, /view, and /preview."""
    match = _URL.match(url.strip())
    if match is None:
        raise InvalidGoogleUrl(url.strip())
    source = SOURCE_BY_PATH[match.group(1).lower()]
    return ParsedGoogleUrl(file_id=match.group(2), source_type=source)


def parse_google_file_reference(value: str) -> str:
    """A file id, or a Docs/Sheets/Slides URL."""
    text = value.strip()
    if "docs.google.com" in text.lower() or text.lower().startswith("http"):
        return parse_google_url(text).file_id
    if _FILE_ID.fullmatch(text):
        return text
    raise InvalidGoogleUrl(text)


def google_urls(source_type: SourceType, file_id: str) -> GoogleUrls:
    kind = PATH_BY_SOURCE[source_type]
    base = f"https://docs.google.com/{kind}/d/{file_id}"
    edit = f"{base}/edit"
    return GoogleUrls(preview_url=f"{base}/preview", edit_url=edit, open_url=edit)


def service_account_info(settings: Settings | None = None) -> dict:
    """JSON for the service account. The file wins when both settings are present."""
    settings = settings or get_settings()
    if settings.google_service_account_file.strip():
        path = Path(settings.google_service_account_file.strip())
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApiError(500, "MISCONFIGURED", "The Google service account file could not be read.") from exc
    elif settings.google_service_account_b64.strip():
        try:
            raw = base64.b64decode(settings.google_service_account_b64.strip(), validate=True)
            info = json.loads(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ApiError(500, "MISCONFIGURED", "GOOGLE_SERVICE_ACCOUNT_B64 is not valid base64 JSON.") from exc
    else:
        raise ApiError(500, "MISCONFIGURED", "Set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_B64.")
    if not isinstance(info, dict) or not isinstance(info.get("client_email"), str) or not info["client_email"].strip():
        raise ApiError(500, "MISCONFIGURED", "The service account JSON is missing client_email.")
    return info


def shared_drive_folder_id(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    folder_id = settings.google_shared_drive_folder_id.strip()
    if not folder_id:
        raise ApiError(500, "MISCONFIGURED", "Set GOOGLE_SHARED_DRIVE_FOLDER_ID to the Shared Drive folder.")
    return folder_id


class _StoredFile:
    def __init__(
        self,
        *,
        file_id: str,
        name: str,
        mime_type: str,
        text: str,
        modified_time: datetime,
        trashed: bool,
        parents: tuple[str, ...],
        owner_emails: tuple[str, ...],
        permissions: list[DrivePermission],
    ) -> None:
        self.id = file_id
        self.name = name
        self.mime_type = mime_type
        self.text = text
        self.modified_time = modified_time
        self.trashed = trashed
        self.parents = parents
        self.owner_emails = owner_emails
        self.permissions = permissions

    def snapshot(self) -> DriveFile:
        source = SOURCE_BY_MIME.get(self.mime_type, SourceType.google_doc)
        return DriveFile(
            id=self.id,
            name=self.name,
            mime_type=self.mime_type,
            web_view_link=google_urls(source, self.id).edit_url,
            modified_time=self.modified_time,
            trashed=self.trashed,
            parents=self.parents,
            owner_emails=self.owner_emails,
        )


class FakeDriveClient:
    """In-memory Drive. Seed files the service account can see; anything else is not shared."""

    def __init__(self, service_account_email: str = DEFAULT_SERVICE_ACCOUNT_EMAIL) -> None:
        self.service_account_email = service_account_email
        self.files: dict[str, _StoredFile] = {}
        self.hidden: set[str] = set()
        self._seq = 0

    def seed_file(
        self,
        file_id: str,
        *,
        name: str = "Notes",
        mime_type: str = MIME_DOCUMENT,
        text: str = "",
        modified_time: datetime | None = None,
        trashed: bool = False,
        parents: tuple[str, ...] = (),
        owners: tuple[str, ...] | None = None,
        permissions: list[DrivePermission] | None = None,
    ) -> _StoredFile:
        owner_emails = owners if owners is not None else (self.service_account_email.lower(),)
        stored = _StoredFile(
            file_id=file_id,
            name=name,
            mime_type=mime_type,
            text=text,
            modified_time=modified_time or datetime.now(UTC),
            trashed=trashed,
            parents=parents,
            owner_emails=tuple(email.lower() for email in owner_emails),
            permissions=list(permissions) if permissions is not None else self.default_permissions(file_id),
        )
        self.files[file_id] = stored
        return stored

    def default_permissions(self, file_id: str) -> list[DrivePermission]:
        """The service account owns the file. An inherited organizer stands in for a Shared Drive member."""
        return [
            DrivePermission(id=f"owner-{file_id}", type="user", role="owner", email=self.service_account_email.lower()),
            DrivePermission(
                id=f"member-{file_id}",
                type="user",
                role="organizer",
                email="shared-drive-member@company.com",
                inherited=True,
            ),
        ]

    def get_file_metadata(self, file_id: str) -> DriveFile:
        return self._require(file_id).snapshot()

    def create_file(
        self, *, title: str, mime_type: str, folder_id: str, template_id: str | None = None
    ) -> DriveFile:
        text = ""
        if template_id:
            source = self._require(template_id)
            mime_type = source.mime_type
            text = source.text
        file_id = uuid4().hex
        stored = self.seed_file(
            file_id,
            name=title,
            mime_type=mime_type,
            text=text,
            parents=(folder_id,),
        )
        return stored.snapshot()

    def list_permissions(self, file_id: str) -> list[DrivePermission]:
        return list(self._require(file_id).permissions)

    def create_permission(
        self,
        file_id: str,
        *,
        role: str,
        email: str | None = None,
        domain: str | None = None,
        permission_type: str = "user",
    ) -> DrivePermission:
        stored = self._require(file_id)
        if permission_type == "domain":
            if not domain:
                raise DriveError(400, "A domain permission needs a domain.")
        elif not email:
            raise DriveError(400, "A user permission needs an email.")
        self._seq += 1
        permission = DrivePermission(
            id=f"perm-{self._seq}",
            type=permission_type,
            role=role,
            email=email.lower() if email else None,
            domain=domain.lower() if domain else None,
        )
        stored.permissions.append(permission)
        return permission

    def update_permission(self, file_id: str, permission_id: str, *, role: str) -> DrivePermission:
        stored = self._require(file_id)
        updated: DrivePermission | None = None
        permissions: list[DrivePermission] = []
        for permission in stored.permissions:
            if permission.id == permission_id:
                updated = replace(permission, role=role)
                permissions.append(updated)
            else:
                permissions.append(permission)
        if updated is None:
            raise DriveNotFound(permission_id)
        stored.permissions = permissions
        return updated

    def delete_permission(self, file_id: str, permission_id: str) -> None:
        stored = self._require(file_id)
        remaining = [permission for permission in stored.permissions if permission.id != permission_id]
        if len(remaining) == len(stored.permissions):
            raise DriveNotFound(permission_id)
        stored.permissions = remaining

    def export_text(self, file_id: str) -> str:
        return self._require(file_id).text

    def trash_file(self, file_id: str) -> None:
        self._require(file_id).trashed = True

    def _require(self, file_id: str) -> _StoredFile:
        if file_id in self.hidden:
            raise DriveForbidden()
        stored = self.files.get(file_id)
        if stored is None:
            raise DriveNotFound(file_id)
        return stored


class ServiceAccountDriveClient:
    """Drive v3 via a service account. `service` is a discovery resource, injectable in tests."""

    def __init__(self, service, *, service_account_email: str, sleeper=time.sleep, max_attempts: int = 5) -> None:
        self._service = service
        self.service_account_email = service_account_email
        self._sleeper = sleeper
        self._max_attempts = max_attempts
        # One discovery client is shared by the request and the Drive sync thread.
        # httplib2 is not safe to call from both at once; a concurrent call aborts the process.
        self._call_lock = Lock()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "ServiceAccountDriveClient":
        settings = settings or get_settings()
        info = service_account_info(settings)
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)
            service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(500, "MISCONFIGURED", "The Google service account JSON could not be loaded.") from exc
        email = settings.google_service_account_email.strip() or str(info["client_email"])
        return cls(service, service_account_email=email)

    def get_file_metadata(self, file_id: str) -> DriveFile:
        def make():
            return self._service.files().get(fileId=file_id, fields=FILE_FIELDS, **_DRIVE)

        return _file_from_api(self._execute(make))

    def create_file(
        self, *, title: str, mime_type: str, folder_id: str, template_id: str | None = None
    ) -> DriveFile:
        if template_id:
            def make_copy(template_id=template_id):
                body = {"name": title, "parents": [folder_id]}
                return self._service.files().copy(fileId=template_id, body=body, fields=FILE_FIELDS, **_DRIVE)

            return _file_from_api(self._execute(make_copy))

        def make():
            body = {"name": title, "mimeType": mime_type, "parents": [folder_id]}
            return self._service.files().create(body=body, fields=FILE_FIELDS, **_DRIVE)

        return _file_from_api(self._execute(make))

    def list_permissions(self, file_id: str) -> list[DrivePermission]:
        permissions: list[DrivePermission] = []
        page_token: str | None = None
        for _ in range(50):
            token = page_token

            def make(token=token):
                arguments = {"fileId": file_id, "fields": PERMISSION_LIST_FIELDS, **_DRIVE}
                if token:
                    arguments["pageToken"] = token
                return self._service.permissions().list(**arguments)

            payload = self._execute(make)
            for item in payload.get("permissions") or []:
                permissions.append(_permission_from_api(item))
            page_token = payload.get("nextPageToken")
            if not page_token:
                return permissions
        return permissions

    def create_permission(
        self,
        file_id: str,
        *,
        role: str,
        email: str | None = None,
        domain: str | None = None,
        permission_type: str = "user",
    ) -> DrivePermission:
        body: dict[str, str] = {"type": permission_type, "role": role}
        if permission_type == "domain":
            if not domain:
                raise DriveError(400, "A domain permission needs a domain.")
            body["domain"] = domain
        else:
            if not email:
                raise DriveError(400, "A user permission needs an email.")
            body["emailAddress"] = email

        def make():
            arguments = {"fileId": file_id, "body": body, "fields": PERMISSION_FIELDS, **_DRIVE}
            if permission_type == "user":
                arguments["sendNotificationEmail"] = False
            return self._service.permissions().create(**arguments)

        return _permission_from_api(self._execute(make))

    def update_permission(self, file_id: str, permission_id: str, *, role: str) -> DrivePermission:
        def make():
            return self._service.permissions().update(
                fileId=file_id,
                permissionId=permission_id,
                body={"role": role},
                fields=PERMISSION_FIELDS,
                **_DRIVE,
            )

        return _permission_from_api(self._execute(make))

    def delete_permission(self, file_id: str, permission_id: str) -> None:
        def make():
            return self._service.permissions().delete(fileId=file_id, permissionId=permission_id, **_DRIVE)

        self._execute(make)

    def export_text(self, file_id: str) -> str:
        def make():
            return self._service.files().export(fileId=file_id, mimeType=EXPORT_MIME, **_DRIVE)

        payload = self._execute(make)
        if isinstance(payload, bytes):
            return payload.decode("utf-8", errors="replace")
        return str(payload)

    def trash_file(self, file_id: str) -> None:
        def make():
            return self._service.files().update(fileId=file_id, body={"trashed": True}, fields=FILE_FIELDS, **_DRIVE)

        self._execute(make)

    def _execute(self, make_request):
        with self._call_lock:
            return self._execute_locked(make_request)

    def _execute_locked(self, make_request):
        from googleapiclient.errors import HttpError

        delay = 0.5
        last_error: HttpError | None = None
        for attempt in range(self._max_attempts):
            try:
                return make_request().execute()
            except HttpError as exc:
                last_error = exc
                if attempt + 1 >= self._max_attempts or not _retryable(exc):
                    raise _translate(exc) from exc
                self._sleeper(delay)
                delay = min(delay * 2, 8.0)
        if last_error is not None:
            raise _translate(last_error)
        raise DriveError(503, "Google Drive did not respond.")


def build_drive_client() -> GoogleDriveClient:
    global _live
    settings = get_settings()
    if settings.google_mode.strip().lower() != "live":
        return _fake_for(settings)
    if _live is None:
        _live = ServiceAccountDriveClient.from_settings(settings)
    return _live


def reset_fake_drive_client() -> None:
    global _fake, _fake_email, _live
    _fake = None
    _fake_email = None
    _live = None


def _fake_for(settings: Settings) -> FakeDriveClient:
    global _fake, _fake_email
    email = settings.google_service_account_email.strip() or DEFAULT_SERVICE_ACCOUNT_EMAIL
    if _fake is None or _fake_email != email:
        _fake = FakeDriveClient(service_account_email=email)
        _fake.seed_file(
            DEMO_SHARED_FILE_ID,
            name="Shared inventory notes",
            mime_type=MIME_DOCUMENT,
            text="Inventory notes the service account can already open.",
        )
        _fake_email = email
    return _fake


def _file_from_api(data: dict) -> DriveFile:
    owners = tuple(
        owner["emailAddress"].strip().lower()
        for owner in data.get("owners") or []
        if isinstance(owner, dict) and isinstance(owner.get("emailAddress"), str) and owner["emailAddress"].strip()
    )
    return DriveFile(
        id=str(data["id"]),
        name=str(data.get("name") or ""),
        mime_type=str(data.get("mimeType") or ""),
        web_view_link=data.get("webViewLink"),
        modified_time=_parse_time(data.get("modifiedTime")),
        trashed=bool(data.get("trashed")),
        parents=tuple(str(parent) for parent in data.get("parents") or ()),
        owner_emails=owners,
    )


def _permission_from_api(item: dict) -> DrivePermission:
    details = item.get("permissionDetails") or []
    inherited = bool(details) and all(bool(detail.get("inherited")) for detail in details if isinstance(detail, dict))
    email = item.get("emailAddress")
    domain = item.get("domain")
    return DrivePermission(
        id=str(item["id"]),
        type=str(item.get("type") or "user"),
        role=str(item.get("role") or "reader"),
        email=email.strip() if isinstance(email, str) and email.strip() else None,
        domain=domain.strip() if isinstance(domain, str) and domain.strip() else None,
        inherited=inherited,
        deleted=bool(item.get("deleted")),
    )


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _retryable(exc) -> bool:
    status = _status_code(exc)
    if status == 429 or status >= 500:
        return True
    return status == 403 and _error_reason(exc) in _RATE_REASONS


def _status_code(exc) -> int:
    status = getattr(getattr(exc, "resp", None), "status", None)
    try:
        return int(status)
    except (TypeError, ValueError):
        return 0


def _error_reason(exc) -> str | None:
    content = getattr(exc, "content", b"") or b""
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return None
    errors = payload.get("error", {}).get("errors") if isinstance(payload, dict) else None
    if not errors:
        return None
    reason = errors[0].get("reason") if isinstance(errors[0], dict) else None
    return reason if isinstance(reason, str) else None


def _translate(exc) -> DriveError:
    status = _status_code(exc)
    reason = _error_reason(exc)
    if status == 404:
        return DriveNotFound("")
    if status == 403 and reason not in _RATE_REASONS:
        return DriveForbidden()
    if status == 429 or (status == 403 and reason in _RATE_REASONS):
        return DriveError(status or 429, "Google Drive rate limit exceeded.", reason=reason)
    if status >= 500:
        return DriveError(status, "Google Drive is temporarily unavailable.", reason=reason)
    return DriveError(status or 502, "Google Drive request failed.", reason=reason)
