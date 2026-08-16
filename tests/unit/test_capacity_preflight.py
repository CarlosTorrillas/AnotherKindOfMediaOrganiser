import os
from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser.application.capacity_preflight import (
    plan_organisation_capacity,
)
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)


def proposal_for(tmp_path: Path, files: list[tuple[str, bytes, datetime]]):
    source = tmp_path / "source"
    for name, content, date in files:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        timestamp = date.timestamp()
        os.utime(path, (timestamp, timestamp))
    return generate_organisation_proposal(scan_media_collection(source))


def date(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=timezone.utc)


def test_full_proposal_fits_and_reuses_every_placement(tmp_path: Path) -> None:
    proposal = proposal_for(
        tmp_path,
        [("jan.jpg", b"123", date(2023, 1)), ("feb.jpg", b"4567", date(2023, 2))],
    )

    result = plan_organisation_capacity(
        proposal, available_bytes=17, allocation_unit=1, reserve_bytes=10
    )

    assert result.required_bytes == 7
    assert result.usable_bytes == 7
    assert result.execution_proposal == proposal
    assert not result.is_partial


def test_partial_proposal_is_oldest_complete_month_prefix(tmp_path: Path) -> None:
    proposal = proposal_for(
        tmp_path,
        [
            ("newest.jpg", b"33333", date(2024, 3)),
            ("later-small.jpg", b"x", date(2024, 4)),
            ("oldest.jpg", b"111", date(2023, 12)),
            ("middle.jpg", b"2222", date(2024, 1)),
        ],
    )

    result = plan_organisation_capacity(
        proposal, available_bytes=7, allocation_unit=1, reserve_bytes=0
    )

    assert result.is_partial
    assert result.included_months == ((2023, 12), (2024, 1))
    assert result.excluded_months == ((2024, 3), (2024, 4))
    assert result.execution_required_bytes == 7
    selected = result.execution_proposal
    assert selected is not None
    assert selected.placements == tuple(
        placement
        for placement in proposal.placements
        if (placement.media_creation_date.year, placement.media_creation_date.month)
        in result.included_months
    )
    assert all(
        selected_placement.destination == original.destination
        for selected_placement in selected.placements
        for original in proposal.placements
        if selected_placement.source == original.source
    )


def test_next_month_is_wholly_excluded_and_name_conflicts_stay_together(
    tmp_path: Path,
) -> None:
    proposal = proposal_for(
        tmp_path,
        [
            ("jan.jpg", b"1", date(2024, 1)),
            ("a/IMG.jpg", b"22", date(2024, 2)),
            ("b/IMG.jpg", b"333", date(2024, 2)),
        ],
    )

    without_february = plan_organisation_capacity(
        proposal, available_bytes=5, allocation_unit=1, reserve_bytes=0
    )
    with_february = plan_organisation_capacity(
        proposal, available_bytes=6, allocation_unit=1, reserve_bytes=0
    )

    assert without_february.included_months == ((2024, 1),)
    assert all(
        placement.media_creation_date.month != 2
        for placement in without_february.execution_proposal.placements
    )
    assert with_february.execution_proposal == proposal
    assert proposal.name_conflict_files == 1


def test_no_executable_proposal_when_oldest_month_exceeds_usable_capacity(
    tmp_path: Path,
) -> None:
    proposal = proposal_for(tmp_path, [("large.jpg", b"12345", date(2024, 1))])

    result = plan_organisation_capacity(
        proposal, available_bytes=4, allocation_unit=1, reserve_bytes=0
    )

    assert result.execution_proposal is None
    assert result.included_months == ()
    assert result.excluded_months == ((2024, 1),)


def test_unsupported_files_do_not_consume_capacity(tmp_path: Path) -> None:
    proposal = proposal_for(
        tmp_path,
        [("photo.jpg", b"12", date(2024, 1)), ("huge.txt", b"x" * 100, date(2024, 1))],
    )

    result = plan_organisation_capacity(
        proposal, available_bytes=2, allocation_unit=1, reserve_bytes=0
    )

    assert result.required_bytes == 2
    assert result.execution_proposal == proposal


def test_capacity_rounds_each_file_to_destination_allocation_unit(
    tmp_path: Path,
) -> None:
    proposal = proposal_for(
        tmp_path,
        [
            ("small-a.jpg", b"a", date(2024, 1)),
            ("small-b.jpg", b"bc", date(2024, 1)),
            ("exact.jpg", b"1234", date(2024, 1)),
        ],
    )

    result = plan_organisation_capacity(
        proposal,
        available_bytes=100,
        allocation_unit=4,
        reserve_bytes=10,
    )

    assert result.logical_required_bytes == 7
    assert result.required_bytes == 12
    assert result.required_bytes >= result.logical_required_bytes
    assert result.allocation_unit == 4
    assert result.reserve_bytes == 10


def test_many_small_files_are_rounded_individually(tmp_path: Path) -> None:
    proposal = proposal_for(
        tmp_path,
        [(f"{index}.jpg", b"x", date(2024, 1)) for index in range(100)],
    )

    result = plan_organisation_capacity(
        proposal,
        available_bytes=20_000,
        allocation_unit=128,
        reserve_bytes=1_024,
    )

    assert result.logical_required_bytes == 100
    assert result.required_bytes == 12_800
    assert result.usable_bytes == 18_976
