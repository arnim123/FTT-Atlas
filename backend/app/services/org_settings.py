"""The single organization policy row that gates external AI access."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.access import OrgSettings


def get_org_settings(session: Session) -> OrgSettings:
    row = session.scalar(select(OrgSettings).limit(1))
    if row is None:
        row = OrgSettings()
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def update_org_settings(
    session: Session,
    *,
    external_ai_enabled: bool | None = None,
    allow_write_scopes: bool | None = None,
    max_token_days: int | None = None,
) -> OrgSettings:
    row = get_org_settings(session)
    if external_ai_enabled is not None:
        row.external_ai_enabled = external_ai_enabled
    if allow_write_scopes is not None:
        row.allow_write_scopes = allow_write_scopes
    if max_token_days is not None:
        if max_token_days < 1:
            raise ApiError(422, "INVALID_TOKEN_DAYS", "Maximum token lifetime must be at least 1 day.")
        row.max_token_days = max_token_days
    session.commit()
    session.refresh(row)
    return row
