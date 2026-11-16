from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.drive import DEFAULT_SERVICE_ACCOUNT_EMAIL, DEMO_SHARED_FILE_ID
from app.schemas.config import PublicConfig
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return HealthResponse(status="ok")


@router.get("/config", response_model=PublicConfig)
def public_config() -> PublicConfig:
    """Browser configuration. The service-account email is not a credential."""
    settings = get_settings()
    email = settings.google_service_account_email.strip() or DEFAULT_SERVICE_ACCOUNT_EMAIL
    fake = settings.google_mode.strip().lower() != "live"
    return PublicConfig(
        public_base_url=settings.public_base_url.rstrip("/"),
        public_app_url=settings.public_app_url.rstrip("/"),
        google_client_id=settings.google_client_id,
        max_upload_mb=settings.max_upload_mb,
        service_account_email=email,
        google_mode="live" if not fake else "fake",
        demo_google_url=f"https://docs.google.com/document/d/{DEMO_SHARED_FILE_ID}/edit" if fake else None,
    )
