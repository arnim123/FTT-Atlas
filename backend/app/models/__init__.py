"""ORM models. Importing this package registers every table on Base.metadata."""

from app.models.access import ApiAuditLog, ApiToken, OrgSettings
from app.models.oauth import OAuthAuthorizationCode, OAuthClient, OAuthGrant, OAuthToken
from app.models.base import Base
from app.models.chunk import DocumentChunk
from app.models.conversation import AiConversation, AiMessage
from app.models.department import Department
from app.models.document import Document, DocumentVersion
from app.models.event import DocumentEvent
from app.models.folder import Folder
from app.models.ingestion import IngestionJob
from app.models.permission import DocumentPermission, FolderPermission
from app.models.search import SearchLog
from app.models.taxonomy import Category, DocumentTag, Tag
from app.models.user import User

__all__ = [
    "AiConversation",
    "AiMessage",
    "ApiAuditLog",
    "ApiToken",
    "Base",
    "Category",
    "Department",
    "Document",
    "DocumentChunk",
    "DocumentEvent",
    "DocumentPermission",
    "DocumentTag",
    "DocumentVersion",
    "Folder",
    "FolderPermission",
    "IngestionJob",
    "OAuthAuthorizationCode",
    "OAuthClient",
    "OAuthGrant",
    "OAuthToken",
    "OrgSettings",
    "SearchLog",
    "Tag",
    "User",
]
