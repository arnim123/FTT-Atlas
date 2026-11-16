from collections.abc import Iterator
from contextvars import ContextVar, Token

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

_request_session: ContextVar[Session | None] = ContextVar("request_session", default=None)


def bind_request_session(session: Session) -> Token:
    """Remember the session handling the current request. Drive sync reuses it."""
    return _request_session.set(session)


def reset_request_session(token: Token) -> None:
    _request_session.reset(token)


def current_request_session() -> Session | None:
    return _request_session.get()


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
