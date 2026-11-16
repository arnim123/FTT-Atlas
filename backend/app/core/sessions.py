"""Open the request's database session, including the one tests substitute."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def open_session() -> Iterator[Session]:
    """Yield the active request session, or a short-lived one outside a request.

    FastAPI tests replace `get_db`. Callers outside a route, including the MCP
    verifier, reuse that same session so they see the test transaction.
    """
    from app.core.database import SessionLocal, get_db
    from app.main import app

    override = app.dependency_overrides.get(get_db)
    if override is not None:
        generator = override()
        session = next(generator)
        try:
            yield session
        finally:
            try:
                next(generator)
            except StopIteration:
                pass
        return
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
