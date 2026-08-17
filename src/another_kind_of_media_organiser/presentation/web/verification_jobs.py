"""In-process coordination for long-running read-only browser verification."""

import queue
import sqlite3
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    CollisionClassificationProgress,
    ProgressCallback,
    generate_content_verified_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.media import ScanResult
from another_kind_of_media_organiser.domain.organisation import OrganisationProposal
from another_kind_of_media_organiser.infrastructure.digest_cache import (
    SqliteDigestCache,
    default_digest_cache_path,
)


class VerificationState(Enum):
    """Current state of a browser collision-verification job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class VerificationJob:
    """Reconnectable presentation state for one verification request."""

    job_id: str
    source: Path
    exclusions: tuple[Path, ...]
    state: VerificationState = VerificationState.QUEUED
    progress: CollisionClassificationProgress | None = None
    scan_result: ScanResult | None = None
    proposal: OrganisationProposal | None = None
    error: str | None = None
    cancel_requested: threading.Event = field(
        default_factory=threading.Event, repr=False
    )
    started: threading.Event = field(default_factory=threading.Event, repr=False)
    finished: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def is_active(self) -> bool:
        return self.state in {VerificationState.QUEUED, VerificationState.RUNNING}


Verifier = Callable[..., OrganisationProposal]
CacheFactory = Callable[[], SqliteDigestCache | None]


class VerificationCoordinator:
    """Run one verification at a time and retain reconnectable job state."""

    def __init__(
        self,
        *,
        verifier: Verifier = generate_content_verified_organisation_proposal,
        cache_factory: CacheFactory | None = None,
    ) -> None:
        self._verifier = verifier
        self._cache_factory = cache_factory or _open_digest_cache
        self._jobs: dict[str, VerificationJob] = {}
        self._jobs_lock = threading.Lock()
        self._queue: queue.Queue[VerificationJob] = queue.Queue()
        self._worker: threading.Thread | None = None

    def submit(
        self, source: Path, exclusions: tuple[Path, ...]
    ) -> VerificationJob:
        job = VerificationJob(uuid.uuid4().hex, source, exclusions)
        with self._jobs_lock:
            self._prune_finished_jobs()
            self._jobs[job.job_id] = job
            self._ensure_worker()
        self._queue.put(job)
        return job

    def _prune_finished_jobs(self) -> None:
        while len(self._jobs) >= 100:
            finished_job_id = next(
                (
                    job_id
                    for job_id, existing in self._jobs.items()
                    if not existing.is_active
                ),
                None,
            )
            if finished_job_id is None:
                return
            del self._jobs[finished_job_id]

    def get(self, job_id: str) -> VerificationJob | None:
        with self._jobs_lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> VerificationJob | None:
        job = self.get(job_id)
        if job is not None and job.is_active:
            job.cancel_requested.set()
            if job.state is VerificationState.QUEUED:
                self._cancel(job)
                job.finished.set()
        return job

    def _ensure_worker(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(
            target=self._work,
            name="media-organiser-verification",
            daemon=True,
        )
        self._worker.start()

    def _work(self) -> None:
        while True:
            job = self._queue.get()
            try:
                self._run(job)
            finally:
                self._queue.task_done()

    def _run(self, job: VerificationJob) -> None:
        if job.cancel_requested.is_set():
            self._cancel(job)
            return
        job.state = VerificationState.RUNNING
        job.started.set()
        cache = None
        try:
            if job.exclusions:
                result = scan_media_collection(
                    job.source, excluded_paths=job.exclusions
                )
            else:
                result = scan_media_collection(job.source)
            job.scan_result = result

            def report(progress: CollisionClassificationProgress) -> None:
                job.progress = progress
                if job.cancel_requested.is_set():
                    raise _VerificationCancelled

            cache = self._cache_factory()
            proposal = self._verifier(
                result,
                report,
                digest_cache=cache,
            )
            if job.cancel_requested.is_set():
                self._cancel(job)
                return
            job.proposal = proposal
            if job.progress is None:
                job.progress = CollisionClassificationProgress(0, 0, 0, 0, 0, 0, 0)
            job.state = VerificationState.COMPLETED
        except _VerificationCancelled:
            self._cancel(job)
        except Exception as error:
            job.error = _safe_error_message(error)
            job.state = VerificationState.FAILED
        finally:
            if cache is not None:
                try:
                    cache.close()
                except sqlite3.Error:
                    pass
            job.finished.set()

    @staticmethod
    def _cancel(job: VerificationJob) -> None:
        job.state = VerificationState.CANCELLED


class _VerificationCancelled(Exception):
    pass


def _open_digest_cache() -> SqliteDigestCache | None:
    try:
        return SqliteDigestCache(default_digest_cache_path())
    except (OSError, sqlite3.Error):
        return None


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, OSError) and error.strerror:
        return error.strerror
    message = str(error).strip()
    return message or "Collision verification could not be completed."
