"""Postgres job queue behind `IngestionQueue`.

`enqueue` and `run_next` are the only operations the rest of the app uses.
A later Celery or arq backend implements the same two methods: `enqueue`
publishes a task, and the worker process calls `ExtractionPipeline.run`.
Callers do not change.

Claiming uses `FOR UPDATE SKIP LOCKED` so two workers can take different
pending rows without blocking each other. A failed attempt is put back with
exponential backoff until `ingestion_max_attempts`. Permanent extraction
errors fail the job immediately.
"""

from datetime import timedelta
from typing import Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import ExtractionStatus, JobStatus
from app.ingestion.extractors import PermanentExtractionError
from app.ingestion.pipeline import ExtractionPipeline
from app.models.base import utcnow
from app.models.document import Document
from app.models.ingestion import IngestionJob

EXTRACT_JOB = "extract"
_ERROR_LIMIT = 2000


@runtime_checkable
class IngestionQueue(Protocol):
    def enqueue(self, session: Session, document_id: UUID, job_type: str = EXTRACT_JOB, *, force: bool = False) -> UUID:
        """Schedule work. Returns the job id, reusing a pending job when one exists."""

    def run_next(self, session: Session) -> bool:
        """Claim and finish one due job. False when nothing is due."""


class PostgresIngestionQueue:
    def __init__(
        self,
        pipeline: ExtractionPipeline | None = None,
        *,
        max_attempts: int | None = None,
        backoff_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self.pipeline = pipeline or ExtractionPipeline()
        self.max_attempts = settings.ingestion_max_attempts if max_attempts is None else max_attempts
        self.backoff_seconds = settings.ingestion_backoff_seconds if backoff_seconds is None else backoff_seconds

    def enqueue(self, session: Session, document_id: UUID, job_type: str = EXTRACT_JOB, *, force: bool = False) -> UUID:
        pending = _active_job(session, document_id, job_type, pending_only=True)
        if pending is not None:
            pending.run_after = None
            if force:
                pending.last_error = None
            _mark_pending(session, document_id)
            session.flush()
            return pending.id
        # A running job keeps its row lock. The new pending row extracts again
        # after that attempt finishes, so a change during the run is not lost.
        job = IngestionJob(document_id=document_id, job_type=job_type, status=JobStatus.pending, attempts=0)
        session.add(job)
        _mark_pending(session, document_id)
        session.flush()
        return job.id

    def run_next(self, session: Session) -> bool:
        job = self.claim_next(session)
        if job is None:
            return False
        job_id = job.id
        document_id = job.document_id
        attempts = job.attempts
        try:
            with session.begin_nested():
                self.pipeline.run(session, document_id)
                self._mark_succeeded(session, job_id)
        except Exception as exc:
            session.expire_all()
            self._mark_failure(session, job_id, document_id, attempts, exc)
        return True

    def claim_next(self, session: Session) -> IngestionJob | None:
        job = session.scalar(claim_statement())
        if job is None:
            return None
        job.status = JobStatus.running
        job.attempts += 1
        job.started_at = utcnow()
        job.last_error = None
        document = session.get(Document, job.document_id)
        if document is not None and document.deleted_at is None:
            document.extraction_status = ExtractionStatus.processing
            document.extraction_error = None
        session.flush()
        return job

    def _mark_succeeded(self, session: Session, job_id: UUID) -> None:
        job = session.get(IngestionJob, job_id)
        if job is None:
            return
        job.status = JobStatus.succeeded
        job.finished_at = utcnow()
        job.last_error = None
        job.run_after = None
        session.flush()

    def _mark_failure(self, session: Session, job_id: UUID, document_id: UUID, attempts: int, exc: Exception) -> None:
        job = session.get(IngestionJob, job_id)
        if job is None:
            return
        message = _error_text(exc)
        give_up = isinstance(exc, PermanentExtractionError) or attempts >= self.max_attempts
        job.attempts = attempts
        job.last_error = message
        job.finished_at = utcnow()
        document = session.get(Document, document_id)
        if give_up:
            job.status = JobStatus.failed
            job.run_after = None
            if document is not None:
                document.extraction_status = ExtractionStatus.failed
                document.extraction_error = message
        else:
            job.status = JobStatus.pending
            delay = min(3600, self.backoff_seconds * (2 ** (attempts - 1)))
            job.run_after = utcnow() + timedelta(seconds=delay)
            if document is not None and document.deleted_at is None:
                document.extraction_status = ExtractionStatus.pending
                document.extraction_error = message
        session.flush()


def claim_statement():
    """The row lock the worker takes. Other workers skip a locked row."""
    return (
        select(IngestionJob)
        .where(
            IngestionJob.status == JobStatus.pending,
            or_(IngestionJob.run_after.is_(None), IngestionJob.run_after <= utcnow()),
        )
        .order_by(IngestionJob.created_at.asc(), IngestionJob.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )


def drain(queue: IngestionQueue, session: Session, *, limit: int = 50) -> int:
    """Finish up to `limit` due jobs. The caller commits."""
    finished = 0
    while finished < limit and queue.run_next(session):
        finished += 1
    return finished


_queue: IngestionQueue | None = None


def get_queue() -> IngestionQueue:
    global _queue
    if _queue is None:
        _queue = PostgresIngestionQueue()
    return _queue


def _active_job(session: Session, document_id: UUID, job_type: str, *, pending_only: bool) -> IngestionJob | None:
    statuses = (JobStatus.pending,) if pending_only else (JobStatus.pending, JobStatus.running)
    return session.scalar(
        select(IngestionJob)
        .where(
            IngestionJob.document_id == document_id,
            IngestionJob.job_type == job_type,
            IngestionJob.status.in_(statuses),
        )
        .order_by(IngestionJob.created_at.asc())
        .limit(1)
    )


def _mark_pending(session: Session, document_id: UUID) -> None:
    document = session.get(Document, document_id)
    if document is None or document.deleted_at is not None:
        return
    if document.extraction_status is ExtractionStatus.processing:
        return
    document.extraction_status = ExtractionStatus.pending
    document.extraction_error = None


def _error_text(exc: Exception) -> str:
    message = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
    cleaned = " ".join(message.split())
    return cleaned[:_ERROR_LIMIT] or exc.__class__.__name__
