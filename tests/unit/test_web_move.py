import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

from another_kind_of_media_organiser.application.capacity_preflight import DEFAULT_SAFETY_RESERVE_BYTES
from another_kind_of_media_organiser.application.execute_organisation_proposal import (
    OrganisationDeletionError,
    OrganisationExecutionMode,
    OrganisationExecutionProgress,
    OrganisationVerificationError,
)
from another_kind_of_media_organiser.presentation.web import create_app
from another_kind_of_media_organiser.presentation.web.copy_jobs import CopyCoordinator, CopyState


def _media(path: Path, content: bytes, month: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    stamp = datetime(2024, month, 1, tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamp, stamp))


def _coordinator(*, available=None, executor=None):
    options = {
        "available_capacity_provider": lambda _path: available or DEFAULT_SAFETY_RESERVE_BYTES + 1024**3,
        "allocation_unit_provider": lambda _path: 1,
    }
    if executor:
        options["executor"] = executor
    return CopyCoordinator(**options)


def _client(coordinator):
    return create_app({"TESTING": True, "COPY_COORDINATOR": coordinator}).test_client()


def test_move_requires_strong_confirmation_and_writes_nothing_before_it(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "photo.jpg", b"valuable")
    coordinator = _coordinator()

    record = coordinator.prepare(source, destination, (), mode=OrganisationExecutionMode.MOVE)
    response = _client(coordinator).get(f"/move-preflights/{record.copy_id}")

    assert b"Operation</dt><dd>MOVE" in response.data
    assert b"THIS OPERATION WILL DELETE SOURCE FILES." in response.data
    assert b"copied and verified before" in response.data
    assert b"Confirm MOVE" in response.data
    assert (source / "photo.jpg").read_bytes() == b"valuable"
    assert not destination.exists()


def test_confirmed_move_uses_verified_application_mode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "photo.jpg", b"valuable")
    coordinator = _coordinator()
    record = coordinator.prepare(source, destination, (), mode=OrganisationExecutionMode.MOVE)

    coordinator.confirm(record.copy_id, acceptance="move")
    assert record.finished.wait(timeout=5)

    assert record.state is CopyState.COMPLETED
    assert not (source / "photo.jpg").exists()
    assert next(destination.rglob("*.jpg")).read_bytes() == b"valuable"
    assert record.result.files_verified == 1
    assert record.result.source_files_deleted == 1


def test_move_inside_source_warns_excludes_destination_and_requires_confirmation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = source / "Organised"
    _media(source / "photo.jpg", b"valuable")
    _media(destination / "existing.jpg", b"existing output")
    coordinator = _coordinator()

    record = coordinator.prepare(
        source,
        destination,
        (),
        mode=OrganisationExecutionMode.MOVE,
    )
    response = _client(coordinator).get(f"/move-preflights/{record.copy_id}")

    assert b"Destination Collection is inside the source Media Collection" in response.data
    assert b"THIS OPERATION WILL DELETE SOURCE FILES." in response.data
    assert [item.source for item in record.plan.items] == [source / "photo.jpg"]
    assert (source / "photo.jpg").read_bytes() == b"valuable"
    assert (destination / "existing.jpg").read_bytes() == b"existing output"


def test_confirmed_move_inside_source_moves_only_eligible_source_media(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = source / "Organised"
    _media(source / "photo.jpg", b"valuable")
    _media(destination / "existing.jpg", b"existing output")
    coordinator = _coordinator()
    record = coordinator.prepare(
        source,
        destination,
        (),
        mode=OrganisationExecutionMode.MOVE,
    )

    coordinator.confirm(record.copy_id, acceptance="move")
    assert record.finished.wait(timeout=5)

    assert record.state is CopyState.COMPLETED
    assert not (source / "photo.jpg").exists()
    assert (destination / "existing.jpg").read_bytes() == b"existing output"
    assert len(list((destination / "2024").rglob("*.jpg"))) == 1


def test_verification_failure_reports_and_preserves_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "photo.jpg", b"valuable")

    def fail(plan, callback, *, mode):
        item = plan.items[0]
        item.destination.parent.mkdir(parents=True)
        item.destination.write_bytes(b"bad")
        raise OrganisationVerificationError(item.source, item.destination, 1, 1, OSError("digest mismatch"))

    coordinator = _coordinator(executor=fail)
    record = coordinator.prepare(source, destination, (), mode=OrganisationExecutionMode.MOVE)
    coordinator.confirm(record.copy_id, acceptance="move")
    assert record.finished.wait(timeout=5)
    response = _client(coordinator).get(f"/moves/{record.copy_id}")

    assert b"Organisation verification failed." in response.data
    assert b"Reason: digest mismatch" in response.data
    assert (source / "photo.jpg").is_file()


def test_deletion_failure_reports_and_keeps_verified_destination_and_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "photo.jpg", b"valuable")

    def fail(plan, callback, *, mode):
        item = plan.items[0]
        item.destination.parent.mkdir(parents=True)
        item.destination.write_bytes(item.source.read_bytes())
        raise OrganisationDeletionError(item.source, item.destination, 1, 1, OSError("read only"), files_verified=1)

    coordinator = _coordinator(executor=fail)
    record = coordinator.prepare(source, destination, (), mode=OrganisationExecutionMode.MOVE)
    coordinator.confirm(record.copy_id, acceptance="move")
    assert record.finished.wait(timeout=5)
    response = _client(coordinator).get(f"/moves/{record.copy_id}")

    assert b"Source deletion failed after COPY+VERIFY succeeded." in response.data
    assert b"Reason: read only" in response.data
    assert (source / "photo.jpg").is_file()
    assert next(destination.rglob("*.jpg")).read_bytes() == b"valuable"


def test_partial_move_deletes_only_the_accepted_oldest_month(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "january.jpg", b"jan", 1)
    _media(source / "february.jpg", b"february", 2)
    coordinator = _coordinator(available=DEFAULT_SAFETY_RESERVE_BYTES + 3)
    record = coordinator.prepare(source, destination, (), mode=OrganisationExecutionMode.MOVE)

    coordinator.confirm(record.copy_id, acceptance="partial-move")
    assert record.finished.wait(timeout=5)
    response = _client(coordinator).get(f"/moves/{record.copy_id}")

    assert b"Partial organisation completed." in response.data
    assert b"2024 January" in response.data
    assert not (source / "january.jpg").exists()
    assert (source / "february.jpg").read_bytes() == b"february"
    assert b"Remaining media was not modified." in response.data


def test_running_move_displays_verified_deletion_progress(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _media(source / "photo.jpg", b"valuable")
    release = Event()

    def controlled(plan, callback, *, mode):
        callback(OrganisationExecutionProgress(4, 10, 18_4 * 1024**3 // 10, 3, 2))
        release.wait(timeout=5)
        return type("Result", (), {"files_copied": 4, "total_files": 10, "bytes_copied": 0, "files_verified": 3, "source_files_deleted": 2})()

    coordinator = _coordinator(executor=controlled)
    record = coordinator.prepare(source, destination, (), mode=OrganisationExecutionMode.MOVE)
    coordinator.confirm(record.copy_id, acceptance="move")
    assert record.started.wait(timeout=2)
    response = _client(coordinator).get(f"/moves/{record.copy_id}")
    release.set()

    assert b"Files</dt><dd>4 / 10" in response.data
    assert b"Moved</dt><dd>18.4 GiB" in response.data
    assert b"Verified</dt><dd>3" in response.data
    assert b"Source files deleted</dt><dd>2" in response.data
