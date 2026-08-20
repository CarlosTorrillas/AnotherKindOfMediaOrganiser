import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from another_kind_of_media_organiser.application.execute_organisation_proposal import (
    DestinationConflictError,
    OrganisationCopyError,
    OrganisationDeletionError,
    OrganisationExecutionMode,
    OrganisationVerificationError,
    UnsafeDestinationError,
    execute_organisation_plan,
    prepare_organisation_execution,
)
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)


def proposal_for(root: Path, files: dict[str, bytes]):
    timestamp = datetime(2024, 8, 1, tzinfo=timezone.utc).timestamp()
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        os.utime(path, (timestamp, timestamp))
    return generate_organisation_proposal(scan_media_collection(root))


@pytest.mark.parametrize("relationship", ["same", "source_inside"])
def test_preflight_rejects_unsafe_source_destination_relationships(
    tmp_path: Path, relationship: str
) -> None:
    source = tmp_path / "source"
    proposal = proposal_for(source, {"photo.jpg": b"valuable"})
    if relationship == "same":
        destination = source
    else:
        destination = tmp_path

    with pytest.raises(UnsafeDestinationError):
        prepare_organisation_execution(proposal, source, destination)

    assert (source / "photo.jpg").read_bytes() == b"valuable"


def test_preflight_allows_a_destination_inside_the_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    proposal = proposal_for(source, {"photo.jpg": b"valuable"})
    destination = source / "organised"

    plan = prepare_organisation_execution(proposal, source, destination)

    assert plan.destination_is_inside_source
    assert [item.source for item in plan.items] == [source / "photo.jpg"]


def test_preflight_rejects_a_destination_that_escapes_the_root(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    proposal = proposal_for(source, {"photo.jpg": b"valuable"})
    placement = proposal.placements[0]
    unsafe_proposal = type(proposal)(
        (type(placement)(**{**placement.__dict__, "destination": Path("../escape.jpg")}),),
        (),
    )

    with pytest.raises(UnsafeDestinationError):
        prepare_organisation_execution(
            unsafe_proposal, source, tmp_path / "destination"
        )


def test_preflight_rejects_a_destination_symlink_that_escapes_the_root(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    outside = tmp_path / "outside"
    destination.mkdir()
    outside.mkdir()
    (destination / "2024").symlink_to(outside, target_is_directory=True)
    proposal = proposal_for(source, {"photo.jpg": b"valuable"})

    with pytest.raises(UnsafeDestinationError):
        prepare_organisation_execution(proposal, source, destination)

    assert tuple(outside.iterdir()) == ()


def test_preflight_finds_every_existing_destination_before_copying(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    proposal = proposal_for(
        source, {"a/first.jpg": b"first", "b/second.jpg": b"second"}
    )
    existing = destination / proposal.placements[1].destination
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"keep me")

    with pytest.raises(DestinationConflictError) as raised:
        prepare_organisation_execution(proposal, source, destination)

    assert raised.value.path == existing
    assert existing.read_bytes() == b"keep me"
    assert not (destination / proposal.placements[0].destination).exists()


def test_execution_consumes_exact_proposed_destinations_and_reports_progress(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    proposal = proposal_for(
        source,
        {
            "camera-a/IMG_001.jpg": b"canonical",
            "camera-b/IMG_001.jpg": b"conflict",
        },
    )
    source_state = {
        placement.source.path: (
            placement.source.path.read_bytes(),
            placement.source.path.stat().st_mtime_ns,
        )
        for placement in proposal.placements
    }
    progress = []

    plan = prepare_organisation_execution(proposal, source, destination)
    result = execute_organisation_plan(plan, progress.append)

    assert result.files_copied == 2
    assert [item.destination.relative_to(destination) for item in plan.items] == [
        placement.destination for placement in proposal.placements
    ]
    assert (destination / proposal.placements[0].destination).read_bytes() == b"canonical"
    assert (destination / proposal.placements[1].destination).read_bytes() == b"conflict"
    assert proposal.placements[1].destination.parent.name == "nameConflicts"
    assert progress[-1].files_copied == 2
    assert progress[-1].bytes_copied == len(b"canonicalconflict")
    assert source_state == {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in source_state
    }


def test_runtime_failure_keeps_completed_copies_and_stops(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    proposal = proposal_for(
        source, {"first.jpg": b"first", "second.jpg": b"second"}
    )
    plan = prepare_organisation_execution(proposal, source, destination)
    calls = 0

    def failing_second_copy(source_path, destination_path, on_bytes_copied):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(source_path.read_bytes())
        on_bytes_copied(source_path.stat().st_size)

    with pytest.raises(OrganisationCopyError) as raised:
        execute_organisation_plan(plan, copy_file=failing_second_copy)

    assert raised.value.files_copied == 1
    assert plan.items[0].destination.is_file()
    assert not plan.items[1].destination.exists()
    assert all(item.source.is_file() for item in plan.items)


def test_move_copies_verifies_then_deletes_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    proposal = proposal_for(source, {"photo.jpg": b"valuable"})
    plan = prepare_organisation_execution(proposal, source, destination)
    events: list[str] = []

    def copy(source_path, destination_path, on_bytes):
        events.append("copy")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(source_path.read_bytes())
        on_bytes(source_path.stat().st_size)

    def verify(source_path, destination_path):
        events.append("verify")
        assert source_path.is_file()
        assert destination_path.read_bytes() == b"valuable"

    def delete(source_path):
        events.append("delete")
        source_path.unlink()

    result = execute_organisation_plan(
        plan,
        mode=OrganisationExecutionMode.MOVE,
        copy_file=copy,
        verify_file=verify,
        delete_file=delete,
    )

    assert events == ["copy", "verify", "delete"]
    assert not plan.items[0].source.exists()
    assert plan.items[0].destination.read_bytes() == b"valuable"
    assert result.files_verified == result.source_files_deleted == 1


def test_move_verification_failure_never_deletes_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    proposal = proposal_for(source, {"photo.jpg": b"valuable"})
    plan = prepare_organisation_execution(proposal, source, tmp_path / "destination")
    deleted = False

    def fail_verification(_source, _destination):
        raise ValueError("digest mismatch")

    def delete(_source):
        nonlocal deleted
        deleted = True

    with pytest.raises(OrganisationVerificationError):
        execute_organisation_plan(
            plan,
            mode=OrganisationExecutionMode.MOVE,
            verify_file=fail_verification,
            delete_file=delete,
        )

    assert plan.items[0].source.read_bytes() == b"valuable"
    assert plan.items[0].destination.is_file()
    assert not deleted


def test_move_deletion_failure_reports_verified_copy_and_preserves_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    proposal = proposal_for(source, {"photo.jpg": b"valuable"})
    plan = prepare_organisation_execution(proposal, source, tmp_path / "destination")

    with pytest.raises(OrganisationDeletionError) as raised:
        execute_organisation_plan(
            plan,
            mode=OrganisationExecutionMode.MOVE,
            delete_file=lambda _path: (_ for _ in ()).throw(OSError("read only")),
        )

    assert raised.value.files_verified == 1
    assert plan.items[0].source.is_file()
    assert plan.items[0].destination.read_bytes() == b"valuable"


def test_copy_mode_is_default_and_does_not_verify_or_delete(tmp_path: Path) -> None:
    source = tmp_path / "source"
    proposal = proposal_for(source, {"photo.jpg": b"valuable"})
    plan = prepare_organisation_execution(proposal, source, tmp_path / "destination")

    result = execute_organisation_plan(
        plan,
        verify_file=lambda *_args: (_ for _ in ()).throw(AssertionError()),
        delete_file=lambda *_args: (_ for _ in ()).throw(AssertionError()),
    )

    assert result.files_verified == result.source_files_deleted == 0
    assert plan.items[0].source.is_file()
