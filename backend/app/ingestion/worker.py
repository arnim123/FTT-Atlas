"""In-process worker.

The loop only calls `IngestionQueue.run_next`. Moving the queue to Celery or
arq means constructing a different `IngestionQueue`; this loop is the piece
that goes away. The extraction pipeline stays the same.
"""

from threading import Event, Thread
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.database import SessionLocal, current_request_session
from app.core.events import (
    DOCUMENT_CREATED,
    DOCUMENT_UPDATED,
    DOCUMENT_VERSION_ADDED,
    GOOGLE_MODIFIED,
    event_bus,
)
from app.ingestion.queue import IngestionQueue, get_queue

_stop = Event()
_thread: Thread | None = None
_BATCH = 25


def register_ingestion_handlers() -> None:
    event_bus.subscribe(DOCUMENT_CREATED, _enqueue_from_event)
    event_bus.subscribe(DOCUMENT_UPDATED, _enqueue_from_event)
    event_bus.subscribe(DOCUMENT_VERSION_ADDED, _enqueue_from_event)
    event_bus.subscribe(GOOGLE_MODIFIED, _enqueue_from_event)


def start_ingestion_worker() -> None:
    """Start the daemon thread unless the process disabled it."""
    global _thread
    settings = get_settings()
    if not settings.ingestion_worker_enabled:
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = Thread(
        target=_loop,
        name="ingestion",
        daemon=True,
        args=(get_queue(), SessionLocal, settings.ingestion_poll_seconds),
    )
    _thread.start()


def stop_ingestion_worker() -> None:
    _stop.set()


def run_available(queue: IngestionQueue, session_factory: sessionmaker[Session], *, limit: int = _BATCH) -> int:
    """Process due jobs on a fresh session and commit each one."""
    session = session_factory()
    processed = 0
    try:
        while processed < limit and not _stop.is_set():
            if not queue.run_next(session):
                break
            session.commit()
            processed += 1
        if processed == 0:
            session.rollback()
        return processed
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _loop(queue: IngestionQueue, session_factory: sessionmaker[Session], poll_seconds: float) -> None:
    while not _stop.is_set():
        try:
            processed = run_available(queue, session_factory)
        except Exception:
            processed = 0
        if processed == 0:
            _stop.wait(poll_seconds)


def _enqueue_from_event(payload: dict) -> None:
    raw = payload.get("document_id")
    if raw is None:
        return
    try:
        document_id = UUID(str(raw))
    except ValueError:
        return
    session = current_request_session()
    owns_session = session is None
    if session is None:
        session = SessionLocal()
    try:
        get_queue().enqueue(session, document_id)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        if owns_session:
            session.close()
