import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from behave import given, then, when

from another_kind_of_media_organiser.application.capacity_preflight import (
    plan_organisation_capacity,
)
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)


def _proposal(context, files: list[tuple[str, bytes, int]]) -> None:
    temporary = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary.cleanup)
    context.source = Path(temporary.name) / "source"
    context.destination = Path(temporary.name) / "destination"
    for name, content, month in files:
        path = context.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        timestamp = datetime(2024, month, 1, tzinfo=timezone.utc).timestamp()
        os.utime(path, (timestamp, timestamp))
    context.proposal = generate_organisation_proposal(
        scan_media_collection(context.source)
    )
    context.original_destinations = {
        placement.source.path: placement.destination
        for placement in context.proposal.placements
    }


@given("a chronological Organisation Proposal that fits usable capacity")
def given_full_fits(context) -> None:
    _proposal(context, [("jan.jpg", b"jan", 1), ("feb.jpg", b"feb", 2)])
    context.available = 6


@given("January and February fit but March exceeds usable capacity")
def given_partial(context) -> None:
    _proposal(
        context,
        [
            ("march.jpg", b"33333", 3),
            ("april.jpg", b"4", 4),
            ("jan.jpg", b"111", 1),
            ("feb.jpg", b"2222", 2),
        ],
    )
    context.available = 7


@given("a month containing canonical and Name Conflict placements")
def given_conflicts(context) -> None:
    _proposal(context, [("a/IMG.jpg", b"one", 1), ("b/IMG.jpg", b"two", 1)])
    context.available = 6


@given("the oldest complete month exceeds usable capacity")
def given_none_fits(context) -> None:
    _proposal(context, [("large.jpg", b"large", 1)])
    context.available = 4


@given("Capacity Preflight offers a partial Organisation Proposal")
def given_partial_offered(context) -> None:
    given_partial(context)
    perform_preflight(context)


@when("Capacity Preflight is performed")
@when("that month is selected by Capacity Preflight")
def perform_preflight(context) -> None:
    context.capacity = plan_organisation_capacity(
        context.proposal, context.available, reserve_bytes=0
    )


@when("the user declines partial Organisation Execution")
def decline_partial(context) -> None:
    context.accepted = False


@then("the full Organisation Proposal is selected unchanged")
def then_full(context) -> None:
    assert context.capacity.execution_proposal == context.proposal


@then("January and February are selected in chronological order")
def then_prefix(context) -> None:
    assert context.capacity.included_months == ((2024, 1), (2024, 2))


@then("March is excluded completely")
def then_march_excluded(context) -> None:
    assert (2024, 3) in context.capacity.excluded_months


@then("planning does not skip ahead to a later month")
def then_no_skip_ahead(context) -> None:
    assert context.capacity.excluded_months == ((2024, 3), (2024, 4))


@then("every included placement keeps its original destination")
def then_destinations_unchanged(context) -> None:
    assert all(
        placement.destination == context.original_destinations[placement.source.path]
        for placement in context.capacity.execution_proposal.placements
    )


@then("both colliding placements remain in the selected month")
def then_conflicts_together(context) -> None:
    assert len(context.capacity.execution_proposal.placements) == 2
    assert context.capacity.execution_proposal.name_conflict_files == 1


@then("there is no executable Organisation Proposal")
def then_none(context) -> None:
    assert context.capacity.execution_proposal is None


@then("no destination content is written")
def then_no_write(context) -> None:
    assert not context.accepted
    assert not context.destination.exists()
