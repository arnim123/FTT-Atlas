from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://atlas:atlas@localhost:5432/atlas"
    seed_skip_google: bool = True
    app_name: str = "Atlas"
    app_env: str = "development"
    google_client_id: str = ""
    allowed_email_domains: str = ""
    auto_provision: bool = False
    super_admin_emails: str = ""
    jwt_secret: str = ""
    default_department_code: str = "product"
    session_cookie_name: str = "atlas_session"
    auth_rate_limit: int = Field(default=10, ge=1)
    auth_rate_limit_window_seconds: int = Field(default=60, ge=1)
    storage_root: str = "storage"
    max_upload_mb: int = Field(default=50, ge=1, le=1024)
    public_app_url: str = "http://localhost:5173"
    frontend_dist: str = ""
    google_mode: str = "fake"
    google_service_account_file: str = ""
    google_service_account_b64: str = ""
    google_service_account_email: str = ""
    google_shared_drive_folder_id: str = ""
    company_domain: str = ""
    google_sync_inline: bool = False
    ai_enabled: bool = False
    public_base_url: str = "http://127.0.0.1:8000"
    token_read_rate_limit: int = Field(default=60, ge=1)
    token_write_rate_limit: int = Field(default=20, ge=1)
    token_rate_window_seconds: int = Field(default=60, ge=1)
    ingestion_worker_enabled: bool = True
    ingestion_max_attempts: int = Field(default=5, ge=1, le=25)
    ingestion_backoff_seconds: int = Field(default=30, ge=1, le=3600)
    ingestion_poll_seconds: float = Field(default=2.0, ge=0.2, le=60)
    oauth_register_rate_limit: int = Field(default=60, ge=1)
    oauth_register_window_seconds: int = Field(default=3600, ge=1)
    oauth_clients_per_ip: int = Field(default=50, ge=1)
    oauth_cleanup_enabled: bool = True
    allow_test_login: bool = False

    @property
    def allowed_domain_set(self) -> set[str]:
        return _split_csv(self.allowed_email_domains)

    def resolved_company_domain(self) -> str:
        """Workspace domain used for an organization-wide Drive share."""
        if self.company_domain.strip():
            return self.company_domain.strip().lower()
        for item in self.allowed_email_domains.split(","):
            domain = item.strip().lower()
            if domain:
                return domain
        return ""

    def drive_sync_runs_inline(self) -> bool:
        """Fake mode stays on the request thread so tests can see the result."""
        if self.google_mode.strip().lower() != "live":
            return True
        return self.google_sync_inline

    @property
    def super_admin_email_set(self) -> set[str]:
        return _split_csv(self.super_admin_emails)

    @property
    def session_cookie_secure(self) -> bool:
        return self.app_env == "production"


def get_settings() -> Settings:
    return Settings()
