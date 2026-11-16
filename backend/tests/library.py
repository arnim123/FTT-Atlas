from uuid import uuid4

from app.core.enums import AccessGrant, DocumentStatus, SourceType, Visibility
from app.models import Category, Document, DocumentPermission, Folder, FolderPermission
from app.models.base import utcnow


def add_category(session, name="Guides"):
    row = Category(name=name, description=None)
    session.add(row)
    session.flush()
    return row


def add_tag(session, name="Inventory"):
    from app.models import Tag

    row = Tag(name=name, description=None)
    session.add(row)
    session.flush()
    return row


def add_folder(
    session,
    *,
    name,
    owner,
    department,
    parent=None,
    visibility=Visibility.organization,
    default_access=AccessGrant.view,
    grants=(),
):
    folder_id = uuid4()
    folder = Folder(
        id=folder_id,
        name=name,
        parent_id=None if parent is None else parent.id,
        path=f"/{folder_id}" if parent is None else f"{parent.path}/{folder_id}",
        depth=0 if parent is None else parent.depth + 1,
        department_id=department.id,
        owner_id=owner.id,
        visibility=visibility,
        default_access=default_access,
        sort_order=0,
    )
    session.add(folder)
    session.flush()
    for principal_type, principal_id, access in grants:
        session.add(
            FolderPermission(
                resource_id=folder.id,
                principal_type=principal_type,
                principal_id=principal_id,
                access=access,
                created_by=owner.id,
            )
        )
    session.flush()
    return folder


def add_document(
    session,
    *,
    name,
    folder,
    owner,
    department,
    category,
    visibility,
    default_access=AccessGrant.view,
    status=DocumentStatus.active,
    source_type=SourceType.txt,
    grants=(),
    deleted=False,
):
    document = Document(
        name=name,
        description=name,
        folder_id=folder.id,
        category_id=category.id,
        department_id=department.id,
        owner_id=owner.id,
        source_type=source_type,
        visibility=visibility,
        default_access=default_access,
        status=status,
        archived_at=utcnow() if status == DocumentStatus.archived else None,
        deleted_at=utcnow() if deleted else None,
        last_modified_at=utcnow(),
    )
    session.add(document)
    session.flush()
    for principal_type, principal_id, access in grants:
        session.add(
            DocumentPermission(
                resource_id=document.id,
                principal_type=principal_type,
                principal_id=principal_id,
                access=access,
                created_by=owner.id,
            )
        )
    session.flush()
    return document
