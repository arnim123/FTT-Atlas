import os
import re
import time
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.database import get_db
from app.main import app
from app.seed import load_seed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _wait_for_postgres(url: str) -> None:
    admin = create_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    last_error: Exception | None = None
    try:
        for _ in range(30):
            try:
                with admin.connect() as connection:
                    connection.execute(text("SELECT 1"))
                return
            except OperationalError as exc:
                last_error = exc
                time.sleep(1)
    finally:
        admin.dispose()
    raise RuntimeError("Postgres is not accepting connections. Start it with docker compose up.") from last_error


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    base = make_url(os.environ.get("DATABASE_URL", Settings().database_url))
    admin_url = base.set(database="postgres")
    _wait_for_postgres(admin_url.render_as_string(hide_password=False))
    name = f"atlas_test_{uuid.uuid4().hex[:12]}"
    if not re.fullmatch(r"atlas_test_[0-9a-f]{12}", name):
        raise RuntimeError(f"Unexpected test database name: {name}")

    admin = create_engine(admin_url.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT", poolclass=NullPool)
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()

    test_url = base.set(database=name).render_as_string(hide_password=False)
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url
    try:
        config = Config(os.path.join(ROOT, "alembic.ini"))
        command.upgrade(config, "head")
        yield test_url
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        admin = create_engine(admin_url.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT", poolclass=NullPool)
        try:
            with admin.connect() as connection:
                connection.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name AND pid <> pg_backend_pid()"),
                    {"name": name},
                )
                connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        finally:
            admin.dispose()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    test_engine = create_engine(database_url, poolclass=NullPool)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def seeded_session(db_session: Session) -> Session:
    """Load the UI catalog into the open transaction. The rows roll back after the test."""
    assert load_seed(db_session) is True
    return db_session


@pytest.fixture
def client(engine: Engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def api(db_session, monkeypatch):
    """HTTP client bound to the rolled-back test transaction, with a test login enabled."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-atlas-sessions")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "company.com")
    monkeypatch.setenv("AUTO_PROVISION", "false")
    monkeypatch.setenv("SUPER_ADMIN_EMAILS", "")
    monkeypatch.setenv("DEFAULT_DEPARTMENT_CODE", "product")
    monkeypatch.setenv("AUTH_RATE_LIMIT", "1000")
    monkeypatch.setenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("SESSION_COOKIE_NAME", "atlas_session")
    monkeypatch.setenv("GOOGLE_MODE", "fake")
    monkeypatch.setenv("COMPANY_DOMAIN", "company.com")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", "atlas-drive@company.iam.gserviceaccount.com")
    monkeypatch.setenv("GOOGLE_SHARED_DRIVE_FOLDER_ID", "shared-drive-folder")
    from app.core.rate_limit import google_login_limiter

    google_login_limiter.reset()
    from app.core.rate_limit import oauth_register_limiter, token_limiter
    from app.services.oauth import clear_metadata_cache

    token_limiter.reset()
    oauth_register_limiter.reset()
    clear_metadata_cache()

    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def org(db_session):
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.core.enums import UserRole
    from app.models import Department, User

    now = datetime(2026, 11, 15, 9, tzinfo=UTC)
    product = Department(code="product", name="Product", description="Product")
    sales = Department(code="sales", name="Sales", description="Sales")
    db_session.add_all([product, sales])
    db_session.flush()

    def add(email, name, role, department, *, is_bot=False, is_active=True, last_login_at=now):
        user = User(
            email=email,
            name=name,
            role=role,
            department_id=department.id,
            is_active=is_active,
            is_bot=is_bot,
            last_login_at=last_login_at,
        )
        db_session.add(user)
        return user

    users = SimpleNamespace(
        product=product,
        sales=sales,
        super_admin=add("alex.morgan@company.com", "Alex Morgan", UserRole.super_admin, product),
        admin=add("sarah.chen@company.com", "Sarah Chen", UserRole.admin, product),
        manager=add("james.wilson@company.com", "James Wilson", UserRole.manager, product),
        employee=add("emma.davis@company.com", "Emma Davis", UserRole.employee, product, last_login_at=None),
        guest=add("noah@partner.co", "Noah Williams", UserRole.guest, sales),
        bot=add("atlas.indexer@company.com", "Atlas Indexer", UserRole.employee, product, is_bot=True),
        sales_employee=add("sam.sales@company.com", "Sam Sales", UserRole.employee, sales),
        sales_manager=add("pat.sales@company.com", "Pat Sales", UserRole.manager, sales),
        deactivated=add("mia.robinson@company.com", "Mia Robinson", UserRole.employee, product, is_active=False),
    )
    db_session.flush()
    return users


@pytest.fixture(scope="session", autouse=True)
def _disable_ingestion_worker():
    """The API test client must not drain jobs on the developer's database."""
    previous = os.environ.get("INGESTION_WORKER_ENABLED")
    os.environ["INGESTION_WORKER_ENABLED"] = "false"
    previous_cleanup = os.environ.get("OAUTH_CLEANUP_ENABLED")
    os.environ["OAUTH_CLEANUP_ENABLED"] = "false"
    yield
    if previous is None:
        os.environ.pop("INGESTION_WORKER_ENABLED", None)
    else:
        os.environ["INGESTION_WORKER_ENABLED"] = previous
    if previous_cleanup is None:
        os.environ.pop("OAUTH_CLEANUP_ENABLED", None)
    else:
        os.environ["OAUTH_CLEANUP_ENABLED"] = previous_cleanup


@pytest.fixture(autouse=True)
def _reset_events():
    from app.core.events import event_bus
    from app.ingestion import register_ingestion_handlers
    from app.integrations.drive_sync import register_drive_sync_handlers

    event_bus.clear()
    register_drive_sync_handlers()
    register_ingestion_handlers()
    from app.services.oauth import register_oauth_handlers
    from app.services.tokens import register_token_handlers

    register_token_handlers()
    register_oauth_handlers()
    yield
    event_bus.clear()


@pytest.fixture
def events():
    from app.core.events import USER_ACCESS_CHANGED, event_bus

    seen: list[dict] = []
    event_bus.subscribe(USER_ACCESS_CHANGED, seen.append)
    yield seen
    event_bus.unsubscribe(USER_ACCESS_CHANGED, seen.append)
