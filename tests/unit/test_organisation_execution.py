import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from another_kind_of_media_organiser.application.execute_organisation_proposal import (
    DestinationConflictError,
    OrganisationCopyError,
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


@pytest.mark.parametrize("relationship", ["same", "destination_inside", "source_inside"])
def test_preflight_rejects_unsafe_source_destination_relationships(
    tmp_path: Path, relationship: str
) -> None:
    source = tmp_path / "source"
    proposal = proposal_for(source, {"photo.jpg": b"valuable"})
    if relationship == "same":
        destination = source
    elif relationship == "destination_inside":
        destination = source / "organised"
    else:
        destination = tmp_path

    with pytest.raises(UnsafeDestinationError):
        prepare_organisation_execution(proposal, source, destination)

    assert (source / "photo.jpg").read_bytes() == b"valuable"


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
