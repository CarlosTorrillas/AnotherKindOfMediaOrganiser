"""Browser coordination around existing capacity and COPY workflows."""

import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from another_kind_of_media_organiser.application.capacity_preflight import (
    CapacityPreflight,
    plan_organisation_capacity,
)
from another_kind_of_media_organiser.application.execute_organisation_proposal import (
    OrganisationCopyError,
    OrganisationExecutionPlan,
    OrganisationExecutionProgress,
    OrganisationExecutionResult,
    execute_organisation_plan,
    prepare_organisation_execution,
)
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.infrastructure.filesystem_capacity import (
    allocation_unit,
    available_capacity,
)


class CopyState(Enum):
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    DECLINED = "DECLINED"
    FAILED = "FAILED"


@dataclass
class CopyRecord:
    """One read-only preflight and, if accepted, its single COPY execution."""

    copy_id: str
    source: Path
    destination: Path
    exclusions: tuple[Path, ...]
    capacity: CapacityPreflight
    plan: OrganisationExecutionPlan | None
    state: CopyState = CopyState.AWAITING_CONFIRMATION
    progress: OrganisationExecutionProgress | None = None
    result: OrganisationExecutionResult | None = None
    error: str | None = None
    failed_source: Path | None = None
    failed_destination: Path | None = None
    files_copied_before_failure: int = 0
    total_files: int = 0
    started: threading.Event = field(default_factory=threading.Event, repr=False)
    finished: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def is_active(self) -> bool:
        return self.state in {CopyState.QUEUED, CopyState.RUNNING}


CapacityProvider = Callable[[Path], int]
AllocationProvider = Callable[[Path], int]
Executor = Callable[..., OrganisationExecutionResult]


class IncompleteScanError(ValueError):
    pass


class CopyCoordinator:
    """Prepare without writing, then execute each accepted COPY at most once."""

    def __init__(
        self,
        *,
        available_capacity_provider: CapacityProvider = available_capacity,
        allocation_unit_provider: AllocationProvider = allocation_unit,
        executor: Executor = execute_organisation_plan,
    ) -> None:
        self._available_capacity = available_capacity_provider
        self._allocation_unit = allocation_unit_provider
        self._executor = executor
        self._records: dict[str, CopyRecord] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[CopyRecord] = queue.Queue()
        self._worker: threading.Thread | None = None

    def prepare(
        self,
        source: Path,
        destination: Path,
        exclusions: tuple[Path, ...],
    ) -> CopyRecord:
        result = (
            scan_media_collection(source, excluded_paths=exclusions)
            if exclusions
            else scan_media_collection(source)
        )
        if not result.is_complete:
            raise IncompleteScanError(
                "Organisation refused: source scan is incomplete."
            )
        proposal = generate_organisation_proposal(result)
        full_plan = prepare_organisation_execution(proposal, source, destination)
        capacity = self._plan_capacity(proposal, destination)
        if capacity.execution_proposal is None:
            plan = None
        elif capacity.is_partial:
            plan = prepare_organisation_execution(
                capacity.execution_proposal, source, destination
            )
        else:
            plan = full_plan
        record = CopyRecord(
            uuid.uuid4().hex,
            source,
            destination,
            exclusions,
            capacity,
            plan,
            total_files=len(plan.items) if plan else 0,
        )
        with self._lock:
            self._prune_finished_records()
            self._records[record.copy_id] = record
            self._ensure_worker()
        return record

    def get(self, copy_id: str) -> CopyRecord | None:
        with self._lock:
            return self._records.get(copy_id)

    def confirm(self, copy_id: str, *, acceptance: str) -> CopyRecord | None:
        with self._lock:
            record = self._records.get(copy_id)
            if record is None:
                return None
            if record.state is not CopyState.AWAITING_CONFIRMATION:
                return record
            expected = "partial-copy" if record.capacity.is_partial else "copy"
            if record.plan is None or acceptance != expected:
                return None
            record.state = CopyState.QUEUED

        try:
            accepted_proposal = record.capacity.execution_proposal
            assert accepted_proposal is not None
            current_capacity = self._plan_capacity(
                accepted_proposal, record.destination
            )
            if (
                current_capacity.execution_proposal != accepted_proposal
                or current_capacity.is_partial
            ):
                raise OSError(
                    "Destination no longer has enough usable capacity for the "
                    "accepted proposal. Run Capacity Preflight again."
                )
            record.plan = prepare_organisation_execution(
                accepted_proposal, record.source, record.destination
            )
            record.total_files = len(record.plan.items)
        except Exception as error:
            record.error = _safe_error_message(error)
            record.state = CopyState.FAILED
            record.finished.set()
            return record

        self._queue.put(record)
        return record

    def decline(self, copy_id: str) -> CopyRecord | None:
        with self._lock:
            record = self._records.get(copy_id)
            if (
                record is not None
                and record.state is CopyState.AWAITING_CONFIRMATION
            ):
                record.state = CopyState.DECLINED
                record.finished.set()
            return record

    def _plan_capacity(self, proposal, destination: Path) -> CapacityPreflight:
        return plan_organisation_capacity(
            proposal,
            self._available_capacity(destination),
            allocation_unit=self._allocation_unit(destination),
        )

    def _ensure_worker(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(
            target=self._work,
            name="media-organiser-copy",
            daemon=True,
        )
        self._worker.start()

    def _work(self) -> None:
        while True:
            record = self._queue.get()
            try:
                self._run(record)
            finally:
                self._queue.task_done()

    def _run(self, record: CopyRecord) -> None:
        plan = record.plan
        if plan is None:
            record.error = "No accepted Organisation Proposal is available."
            record.state = CopyState.FAILED
            record.finished.set()
            return
        record.state = CopyState.RUNNING
        record.started.set()
        try:
            record.result = self._executor(plan, self._reporter(record))
            record.state = CopyState.COMPLETED
        except OrganisationCopyError as error:
            record.error = _safe_error_message(error.cause)
            record.failed_source = error.source
            record.failed_destination = error.destination
            record.files_copied_before_failure = error.files_copied
            record.total_files = error.total_files
            record.state = CopyState.FAILED
        except Exception as error:
            record.error = _safe_error_message(error)
            record.state = CopyState.FAILED
        finally:
            record.finished.set()

    @staticmethod
    def _reporter(record: CopyRecord):
        def report(progress: OrganisationExecutionProgress) -> None:
            record.progress = progress

        return report

    def _prune_finished_records(self) -> None:
        while len(self._records) >= 100:
            finished_id = next(
                (
                    copy_id
                    for copy_id, record in self._records.items()
                    if not record.is_active
                    and record.state is not CopyState.AWAITING_CONFIRMATION
                ),
                None,
            )
            if finished_id is None:
                return
            del self._records[finished_id]


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, OSError) and error.strerror:
        return error.strerror
    message = str(error).strip()
    return message or "Organisation execution could not be completed."
