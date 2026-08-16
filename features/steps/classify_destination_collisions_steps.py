import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from behave import given, then, when

from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.organisation import (
    PlacementClassification,
)


def _collection(context, contents: tuple[bytes, ...]) -> None:
    temporary_directory = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary_directory.cleanup)
    context.collection = Path(temporary_directory.name) / "collection"
    context.collection.mkdir()
    context.sources = []
    timestamp = datetime(2024, 8, 1, tzinfo=timezone.utc).timestamp()
    for index, content in enumerate(contents):
        source = context.collection / f"source-{chr(97 + index)}" / "IMG_001.jpg"
        source.parent.mkdir()
        source.write_bytes(content)
        os.utime(source, (timestamp, timestamp))
        context.sources.append(source)


@given("two colliding Media Entries with identical content")
def step_two_identical(context) -> None:
    _collection(context, (b"identical", b"identical"))


@given("two colliding Media Entries with different content")
def step_two_different(context) -> None:
    _collection(context, (b"first", b"different"))


@given("two colliding Media Entries with the same filename but different content")
def step_same_name_different_content(context) -> None:
    step_two_different(context)


@given("four colliding Media Entries with identical content")
def step_four_identical(context) -> None:
    _collection(context, (b"same", b"same", b"same", b"same"))


@given("a Destination Collision where A equals B equals C and D differs")
def step_mixed_collision(context) -> None:
    _collection(context, (b"same", b"same", b"same", b"different"))


@given("a Media Collection containing a Destination Collision")
def step_collection_with_collision(context) -> None:
    _collection(context, (b"same", b"same", b"different"))


@given("a Destination Collision with an unreadable non-canonical file")
def step_unreadable_collision(context) -> None:
    _collection(context, (b"same size", b"same size"))
    context.scan_result = scan_media_collection(context.collection)
    context.sources[1].unlink()


@given("a readable Media Collection containing a Destination Collision")
def step_readable_collision(context) -> None:
    _collection(context, (b"same", b"same", b"different"))
    context.paths_before = sorted(
        path.relative_to(context.collection) for path in context.collection.rglob("*")
    )
    context.state_before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in context.sources
    }


@when("the Organisation Proposal classifies the Destination Collision")
def step_classify_collision(context) -> None:
    scan_result = getattr(context, "scan_result", None) or scan_media_collection(
        context.collection
    )
    context.proposal = generate_organisation_proposal(scan_result)


@when("the Organisation Proposal is generated repeatedly")
def step_generate_repeatedly(context) -> None:
    scan_result = scan_media_collection(context.collection)
    context.first_proposal = generate_organisation_proposal(scan_result)
    context.second_proposal = generate_organisation_proposal(scan_result)


def _placements(context, classification: PlacementClassification):
    return tuple(
        placement
        for placement in context.proposal.placements
        if placement.classification is classification
    )


@then("one receives the normal proposed destination")
def step_one_canonical(context) -> None:
    canonical = _placements(context, PlacementClassification.CANONICAL)
    assert len(canonical) == 1
    assert canonical[0].destination == canonical[0].normal_destination


@then("the other receives an exactDuplicates review destination")
def step_one_duplicate(context) -> None:
    duplicates = _placements(context, PlacementClassification.EXACT_DUPLICATE)
    assert len(duplicates) == 1
    assert duplicates[0].destination.parts[-2] == "exactDuplicates"


@then("the other receives a potentialConflicts review destination")
def step_one_conflict(context) -> None:
    conflicts = _placements(context, PlacementClassification.POTENTIAL_CONFLICT)
    assert len(conflicts) == 1
    assert conflicts[0].destination.parts[-2] == "potentialConflicts"


@then("neither is classified as an Exact Duplicate")
def step_no_exact_duplicate(context) -> None:
    assert not _placements(context, PlacementClassification.EXACT_DUPLICATE)


@then("every additional copy receives a unique deterministic exactDuplicates destination")
def step_unique_duplicate_destinations(context) -> None:
    destinations = tuple(
        placement.destination
        for placement in _placements(context, PlacementClassification.EXACT_DUPLICATE)
    )
    assert len(destinations) == 3
    assert len(set(destinations)) == 3
    assert [destination.name for destination in destinations] == [
        "IMG_001__dup1.jpg",
        "IMG_001__dup2.jpg",
        "IMG_001__dup3.jpg",
    ]


@then("A receives the normal proposed destination")
def step_a_is_canonical(context) -> None:
    step_one_canonical(context)
    assert _placements(context, PlacementClassification.CANONICAL)[0].source.path == (
        context.sources[0]
    )


@then("B and C are represented as Exact Duplicates")
def step_b_c_duplicates(context) -> None:
    assert tuple(
        placement.source.path
        for placement in _placements(context, PlacementClassification.EXACT_DUPLICATE)
    ) == tuple(context.sources[1:3])


@then("D is represented as a Potential Conflict")
def step_d_conflict(context) -> None:
    conflicts = _placements(context, PlacementClassification.POTENTIAL_CONFLICT)
    assert len(conflicts) == 1
    assert conflicts[0].source.path == context.sources[3]


@then("every source Media Entry remains represented exactly once")
def step_each_source_once(context) -> None:
    assert sorted(placement.source.path for placement in context.proposal.placements) == sorted(
        context.sources
    )


@then("canonical selection and review destinations are identical")
def step_deterministic(context) -> None:
    assert context.first_proposal == context.second_proposal


@then("the unreadable file is represented as an Unverified Conflict")
def step_unverified(context) -> None:
    unverified = _placements(context, PlacementClassification.UNVERIFIED_CONFLICT)
    assert len(unverified) == 1
    assert unverified[0].source.path == context.sources[1]
    assert unverified[0].destination.name == "IMG_001__unverified1.jpg"


@then("it is not an Exact Duplicate or Potential Conflict")
def step_unverified_is_exclusive(context) -> None:
    assert context.proposal.exact_duplicate_files == 0
    assert context.proposal.potential_conflict_files == 0
    assert context.proposal.unverified_conflict_files == 1


@then("collision classification leaves the Media Collection unchanged")
def step_classification_read_only(context) -> None:
    paths_after = sorted(
        path.relative_to(context.collection) for path in context.collection.rglob("*")
    )
    state_after = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in context.sources
    }
    assert paths_after == context.paths_before
    assert state_after == context.state_before

