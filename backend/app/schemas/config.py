from pydantic import BaseModel


class PublicConfig(BaseModel):
    """Values the browser needs. No secrets."""

    public_base_url: str
    public_app_url: str
    google_client_id: str
    max_upload_mb: int
    service_account_email: str
    google_mode: str
    demo_google_url: str | None = None
