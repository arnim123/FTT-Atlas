"""Create the empty workspace pieces a live sign-in needs. This does not load the demo catalog."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.enums import AccessGrant, Visibility
from app.models.department import Department
from app.models.folder import Folder
from app.models.user import User


def ensure_default_department(session: Session) -> Department:
    settings = get_settings()
    code = settings.default_department_code.strip()
    department = session.scalar(select(Department).where(Department.code == code))
    if department is not None:
        return department
    name = code.replace("_", " ").replace("-", " ").strip().title() or "General"
    department = Department(code=code, name=name, description=None)
    session.add(department)
    session.commit()
    session.refresh(department)
    return department


def ensure_root_folder(session: Session, user: User) -> None:
    existing = session.scalar(select(Folder.id).where(Folder.parent_id.is_(None), Folder.deleted_at.is_(None)).limit(1))
    if existing is not None:
        return
    folder_id = uuid4()
    session.add(
        Folder(
            id=folder_id,
            name="Company Knowledge",
            parent_id=None,
            path=f"/{folder_id}",
            depth=0,
            department_id=user.department_id,
            owner_id=user.id,
            visibility=Visibility.organization,
            default_access=AccessGrant.view,
            description=None,
            sort_order=0,
        )
    )
    session.commit()


def main() -> None:
    with SessionLocal() as session:
        ensure_default_department(session)


if __name__ == "__main__":
    main()
