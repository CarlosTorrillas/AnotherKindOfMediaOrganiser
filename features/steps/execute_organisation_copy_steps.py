import tempfile
from pathlib import Path

from behave import given, then, when

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


def _roots(context) -> None:
    temporary_directory = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary_directory.cleanup)
    context.root = Path(temporary_directory.name)
    context.source = context.root / "source"
    context.destination = context.root / "destination"
    context.source.mkdir()


def _write(context, relative_path: str, content: bytes) -> Path:
    path = context.source / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _proposal(context):
    return generate_organisation_proposal(scan_media_collection(context.source))


def _remember_source(context) -> None:
    context.source_state = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in context.source.rglob("*")
        if path.is_file()
    }


@given("a source Media Collection and an empty Destination Collection")
def step_empty_destination(context) -> None:
    _roots(context)
    _write(context, "photo.jpg", b"valuable")
    _remember_source(context)


@given("a lightweight Organisation Proposal containing Name Conflicts")
def step_name_conflict_proposal(context) -> None:
    _roots(context)
    _write(context, "a/IMG_001.jpg", b"one")
    _write(context, "b/IMG_001.jpg", b"two")
    _remember_source(context)


@given("a valid Organisation Proposal for copying")
def step_valid_proposal(context) -> None:
    step_empty_destination(context)


@given("a proposed destination file already exists")
def step_existing_destination(context) -> None:
    step_empty_destination(context)
    proposal = _proposal(context)
    context.existing = context.destination / proposal.placements[0].destination
    context.existing.parent.mkdir(parents=True)
    context.existing.write_bytes(b"existing")


@given("the Destination Collection is {relationship} the source Media Collection")
def step_unsafe_relationship(context, relationship: str) -> None:
    step_empty_destination(context)
    if relationship == "the same as":
        context.destination = context.source
    elif relationship == "inside":
        context.destination = context.source / "organised"
    else:
        context.destination = context.root


@given("Organisation Execution has completed one copy")
def step_one_copy_ready(context) -> None:
    _roots(context)
    _write(context, "first.jpg", b"first")
    _write(context, "second.jpg", b"second")
    _remember_source(context)
    context.plan = prepare_organisation_execution(
        _proposal(context), context.source, context.destination
    )


@given("Organisation Execution is copying media")
def step_copying(context) -> None:
    step_one_copy_ready(context)


@when("the user accepts Organisation Execution")
def step_accept_execution(context) -> None:
    context.proposal = _proposal(context)
    plan = prepare_organisation_execution(
        context.proposal, context.source, context.destination
    )
    context.result = execute_organisation_plan(plan)


@when("the user declines Organisation Execution")
def step_decline_execution(context) -> None:
    context.proposal = _proposal(context)
    prepare_organisation_execution(
        context.proposal, context.source, context.destination
    )


@when("Organisation Execution is requested")
def step_request_execution(context) -> None:
    try:
        context.plan = prepare_organisation_execution(
            _proposal(context), context.source, context.destination
        )
    except (DestinationConflictError, UnsafeDestinationError) as error:
        context.execution_error = error


@when("the next copy operation fails")
def step_copy_fails(context) -> None:
    calls = 0

    def failing_copy(source, destination, on_bytes):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        on_bytes(source.stat().st_size)

    try:
        execute_organisation_plan(context.plan, copy_file=failing_copy)
    except OrganisationCopyError as error:
        context.execution_error = error


@when("copying is cancelled")
def step_copy_cancelled(context) -> None:
    calls = 0

    def cancelling_copy(source, destination, on_bytes):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        on_bytes(source.stat().st_size)

    try:
        execute_organisation_plan(context.plan, copy_file=cancelling_copy)
    except KeyboardInterrupt:
        context.cancelled = True


@then("recognised media is copied to its proposed destination")
def step_media_copied(context) -> None:
    assert all(
        (context.destination / placement.destination).read_bytes()
        == placement.source.path.read_bytes()
        for placement in context.proposal.placements
    )


@then("canonical and nameConflicts placements are copied exactly as proposed")
def step_conflicts_copied(context) -> None:
    step_media_copied(context)
    assert any(
        placement.destination.parent.name == "nameConflicts"
        for placement in context.proposal.placements
    )


@then("no Destination Collection is created")
def step_no_destination(context) -> None:
    assert not context.destination.exists()


@then("execution fails before confirmation")
def step_preflight_failed(context) -> None:
    assert isinstance(context.execution_error, DestinationConflictError)


@then("no source media is copied")
def step_nothing_copied(context) -> None:
    files = [path for path in context.destination.rglob("*") if path.is_file()]
    assert files == [context.existing]


@then("the existing destination file remains untouched")
def step_existing_untouched(context) -> None:
    assert context.existing.read_bytes() == b"existing"


@then("execution is rejected before writing")
def step_unsafe_rejected(context) -> None:
    assert isinstance(context.execution_error, UnsafeDestinationError)


@then("the completed destination copy remains")
def step_completed_remains(context) -> None:
    assert context.plan.items[0].destination.is_file()


@then("the failed destination is not presented as completed")
def step_failed_not_completed(context) -> None:
    assert isinstance(context.execution_error, OrganisationCopyError)
    assert not context.plan.items[1].destination.exists()


@then("completed destination copies remain")
def step_cancelled_completed_remain(context) -> None:
    assert context.cancelled
    assert context.plan.items[0].destination.is_file()


@then("the incomplete destination is not presented as completed")
def step_cancelled_incomplete_absent(context) -> None:
    assert not context.plan.items[1].destination.exists()


@then("the source Media Collection remains unchanged by execution")
def step_source_unchanged(context) -> None:
    assert context.source_state == {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in context.source_state
    }
