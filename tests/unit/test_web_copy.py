import errno
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

from another_kind_of_media_organiser.application.capacity_preflight import (
    DEFAULT_SAFETY_RESERVE_BYTES,
)
from another_kind_of_media_organiser.application.execute_organisation_proposal import (
    OrganisationCopyError,
    OrganisationExecutionProgress,
)
from another_kind_of_media_organiser.presentation.web import create_app
from another_kind_of_media_organiser.presentation.web.copy_jobs import (
    CopyCoordinator,
    CopyState,
)


def _media(path: Path, content: bytes, year: int = 2024, month: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    stamp = datetime(year, month, 1, tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamp, stamp))


def _coordinator(*, available: int | None = None, executor=None):
    options = {
        "available_capacity_provider": lambda _path: (
            available
            if available is not None
            else DEFAULT_SAFETY_RESERVE_BYTES + 1024**3
        ),
        "allocation_unit_provider": lambda _path: 1,
    }
    if executor is not None:
        options["executor"] = executor
    return CopyCoordinator(**options)


def _client(coordinator):
    return create_app(
        {"TESTING": True, "COPY_COORDINATOR": coordinator}
    ).test_client()


def test_preflight_page_is_read_only_and_requires_explicit_confirmation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "photo.jpg", b"valuable")
    coordinator = _coordinator()
    client = _client(coordinator)

    response = client.post(
        "/copy-preflights",
        data={"source": str(source), "destination": str(destination)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Capacity Preflight" in response.data
    assert b"Operation</dt><dd>COPY" in response.data
    assert b"Source files will NOT be deleted." in response.data
    assert b"Confirm COPY" in response.data
    assert not destination.exists()
    assert (source / "photo.jpg").read_bytes() == b"valuable"


def test_confirmed_copy_uses_existing_executor_and_preserves_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "photo.jpg", b"valuable")
    coordinator = _coordinator()
    record = coordinator.prepare(source, destination, ())

    job = coordinator.confirm(record.copy_id, acceptance="copy")
    assert job is not None
    assert job.finished.wait(timeout=5)

    assert job.state is CopyState.COMPLETED
    assert (source / "photo.jpg").read_bytes() == b"valuable"
    copied = next(destination.rglob("*.jpg"))
    assert copied.read_bytes() == b"valuable"
    assert job.progress.files_copied == 1


def test_partial_copy_requires_partial_acceptance_and_copies_only_oldest_month(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "january.jpg", b"jan", month=1)
    _media(source / "february.jpg", b"february", month=2)
    coordinator = _coordinator(available=DEFAULT_SAFETY_RESERVE_BYTES + 3)
    record = coordinator.prepare(source, destination, ())

    assert record.capacity.is_partial
    assert coordinator.confirm(record.copy_id, acceptance="copy") is None
    job = coordinator.confirm(record.copy_id, acceptance="partial-copy")
    assert job is not None
    assert job.finished.wait(timeout=5)

    assert job.state is CopyState.COMPLETED
    copied = [path for path in destination.rglob("*") if path.is_file()]
    assert len(copied) == 1
    assert copied[0].read_bytes() == b"jan"
    assert (source / "january.jpg").read_bytes() == b"jan"
    assert (source / "february.jpg").read_bytes() == b"february"


def test_declined_copy_writes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "photo.jpg", b"valuable")
    coordinator = _coordinator()
    record = coordinator.prepare(source, destination, ())

    declined = coordinator.decline(record.copy_id)

    assert declined.state is CopyState.DECLINED
    assert not destination.exists()
    assert (source / "photo.jpg").read_bytes() == b"valuable"


def test_copy_failure_exposes_enospc_and_preserves_completed_copies(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "first.jpg", b"first")
    _media(source / "second.jpg", b"second")

    def failing_executor(plan, callback):
        first = plan.items[0]
        first.destination.parent.mkdir(parents=True)
        first.destination.write_bytes(first.source.read_bytes())
        callback(OrganisationExecutionProgress(1, 2, first.size))
        second = plan.items[1]
        raise OrganisationCopyError(
            second.source,
            second.destination,
            1,
            2,
            OSError(errno.ENOSPC, "No space left on device"),
        )

    coordinator = _coordinator(executor=failing_executor)
    record = coordinator.prepare(source, destination, ())
    job = coordinator.confirm(record.copy_id, acceptance="copy")
    assert job.finished.wait(timeout=5)
    response = _client(coordinator).get(f"/copies/{record.copy_id}")

    assert job.state is CopyState.FAILED
    assert b"Organisation execution failed." in response.data
    assert b"Reason: No space left on device" in response.data
    assert b"Files copied</dt><dd>1 / 2" in response.data
    assert all(path.is_file() for path in source.iterdir())
    assert len([path for path in destination.rglob("*") if path.is_file()]) == 1


def test_replayed_confirmation_does_not_start_a_second_copy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "photo.jpg", b"valuable")
    release = Event()
    calls = 0

    def controlled_executor(plan, callback):
        nonlocal calls
        calls += 1
        callback(OrganisationExecutionProgress(0, 1, 0))
        release.wait(timeout=5)
        return type("Result", (), {"files_copied": 0, "total_files": 1, "bytes_copied": 0})()

    coordinator = _coordinator(executor=controlled_executor)
    record = coordinator.prepare(source, destination, ())

    first = coordinator.confirm(record.copy_id, acceptance="copy")
    assert first.started.wait(timeout=2)
    second = coordinator.confirm(record.copy_id, acceptance="copy")
    release.set()
    assert first.finished.wait(timeout=5)

    assert second is first
    assert calls == 1
