import errno
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from behave import given, then, when

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


def _workspace(context):
    temporary = TemporaryDirectory()
    context.add_cleanup(temporary.cleanup)
    base = Path(temporary.name)
    context.source = base / "source"
    context.destination = base / "destination"
    return base


def _media(path: Path, content: bytes, month: int = 1):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    stamp = datetime(2024, month, 1, tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamp, stamp))


def _snapshot(root: Path):
    if not root.exists():
        return ()
    return tuple(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def _client(context, *, available=None, executor=None):
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
    context.coordinator = CopyCoordinator(**options)
    context.client = create_app(
        {"TESTING": True, "COPY_COORDINATOR": context.coordinator}
    ).test_client()


def _preflight(context):
    response = context.client.post(
        "/copy-preflights",
        data={
            "source": str(context.source),
            "destination": str(context.destination),
        },
    )
    assert response.status_code == 303
    context.preflight_location = response.headers["Location"]
    context.copy_id = context.preflight_location.split("/")[-1]
    context.record = context.coordinator.get(context.copy_id)
    context.response = context.client.get(context.preflight_location)


def _decision(context, acceptance=None, decision="confirm"):
    data = {"decision": decision}
    if acceptance is not None:
        data["acceptance"] = acceptance
    response = context.client.post(
        f"/copy-preflights/{context.copy_id}/decision", data=data
    )
    context.status_location = response.headers["Location"]
    return response


@given("an accepted browser Organisation Proposal")
def step_accepted_proposal(context):
    _workspace(context)
    _media(context.source / "photo.jpg", b"valuable")
    context.source_before = _snapshot(context.source)
    context.destination_before = _snapshot(context.destination)
    _client(context)


@given("the browser destination passes Capacity Preflight")
def step_destination_fits(context):
    _preflight(context)
    assert not context.record.capacity.is_partial


@when("the user explicitly confirms browser COPY")
def step_confirm_copy(context):
    _decision(context, "copy")
    assert context.record.finished.wait(timeout=5)
    context.response = context.client.get(context.status_location)


@then("the existing COPY Organisation Execution is used")
def step_existing_executor(context):
    assert context.record.state is CopyState.COMPLETED


@then("proposed media is copied to the browser destination")
def step_media_copied(context):
    copied = next(context.destination.rglob("*.jpg"))
    assert copied.read_bytes() == b"valuable"


@then("browser source media remains untouched")
def step_source_untouched(context):
    assert _snapshot(context.source) == context.source_before


@given("a browser Organisation Proposal")
def step_browser_proposal(context):
    _workspace(context)
    _media(context.source / "photo.jpg", b"valuable")
    context.source_before = _snapshot(context.source)
    context.destination_before = _snapshot(context.destination)
    _client(context)


@when("the user selects a browser destination")
def step_select_destination(context):
    _preflight(context)


@then("browser Capacity Preflight is displayed")
def step_preflight_displayed(context):
    assert b"Capacity Preflight" in context.response.data
    assert b"Safety reserve" in context.response.data
    assert b"Confirm COPY" in context.response.data


@then("no filesystem modification has occurred before browser confirmation")
def step_preflight_read_only(context):
    assert _snapshot(context.source) == context.source_before
    assert _snapshot(context.destination) == context.destination_before


@given("the complete browser proposal does not fit")
def step_full_does_not_fit(context):
    _workspace(context)
    _media(context.source / "january.jpg", b"jan", 1)
    _media(context.source / "february.jpg", b"february", 2)
    context.source_before = _snapshot(context.source)
    _client(context, available=DEFAULT_SAFETY_RESERVE_BYTES + 3)
    _preflight(context)
    assert b"Full organisation does not fit." in context.response.data


@given("a browser Partial Organisation Proposal does fit")
def step_partial_fits(context):
    assert context.record.capacity.is_partial
    assert b"Proposed partial organisation" in context.response.data


@when("the user explicitly accepts the partial browser COPY")
def step_accept_partial(context):
    _decision(context, "partial-copy")
    assert context.record.finished.wait(timeout=5)


@then("only the accepted partial browser proposal is executed")
def step_only_partial(context):
    copied = [path for path in context.destination.rglob("*") if path.is_file()]
    assert len(copied) == 1
    assert copied[0].read_bytes() == b"jan"


@then("excluded browser media remains untouched")
def step_excluded_untouched(context):
    assert (context.source / "february.jpg").read_bytes() == b"february"


@given("browser COPY confirmation is displayed")
def step_confirmation(context):
    step_browser_proposal(context)
    _preflight(context)
    assert b"Continue? The default is NO." in context.response.data


@when("the user declines browser COPY")
def step_decline(context):
    _decision(context, decision="decline")


@then("no filesystem content is modified by browser COPY")
def step_decline_no_write(context):
    assert context.record.state is CopyState.DECLINED
    assert _snapshot(context.source) == context.source_before
    assert _snapshot(context.destination) == context.destination_before


@given("browser COPY execution encounters a filesystem error")
def step_copy_failure(context):
    _workspace(context)
    _media(context.source / "first.jpg", b"first")
    _media(context.source / "second.jpg", b"second")
    context.source_before = _snapshot(context.source)

    def fail(plan, callback):
        first = plan.items[0]
        first.destination.parent.mkdir(parents=True)
        first.destination.write_bytes(first.source.read_bytes())
        callback(OrganisationExecutionProgress(1, 2, first.size))
        second = plan.items[1]
        raise OrganisationCopyError(
            second.source, second.destination, 1, 2,
            OSError(errno.ENOSPC, "No space left on device"),
        )

    _client(context, executor=fail)
    _preflight(context)
    _decision(context, "copy")


@when("browser COPY execution stops")
def step_failure_stops(context):
    assert context.record.finished.wait(timeout=5)
    context.response = context.client.get(context.status_location)


@then("the browser COPY failure reason is displayed")
def step_failure_reason(context):
    assert b"Reason: No space left on device" in context.response.data


@then("completed browser copies remain completed")
def step_completed_remain(context):
    assert len([path for path in context.destination.rglob("*") if path.is_file()]) == 1


@given("browser COPY is already running")
def step_copy_running(context):
    _workspace(context)
    _media(context.source / "photo.jpg", b"valuable")
    context.release = Event()
    context.add_cleanup(context.release.set)
    context.calls = 0

    def controlled(plan, callback):
        context.calls += 1
        callback(OrganisationExecutionProgress(0, len(plan.items), 0))
        context.release.wait(timeout=5)
        return type("Result", (), {
            "files_copied": 0, "total_files": len(plan.items), "bytes_copied": 0
        })()

    _client(context, executor=controlled)
    _preflight(context)
    _decision(context, "copy")
    assert context.record.started.wait(timeout=2)


@when("the browser submits COPY execution again")
def step_submit_again(context):
    _decision(context, "copy")
    context.release.set()
    assert context.record.finished.wait(timeout=5)


@given("the selected browser destination is contained within the selected source")
def step_contained_destination(context):
    _workspace(context)
    context.destination = context.source / "Organised"
    _media(context.source / "photo.jpg", b"valuable")
    _media(context.destination / "existing.jpg", b"existing output")
    context.source_before = _snapshot(context.source)
    _client(context)


@given("no filesystem mutation has started for the contained destination")
def step_contained_destination_unchanged(context):
    assert _snapshot(context.source) == context.source_before


@when("the user starts browser Organisation Execution")
def step_start_contained_execution(context):
    _preflight(context)


@then("AKOMO warns that the browser destination is inside the source")
def step_warn_contained_destination(context):
    assert (
        b"Destination Collection is inside the source Media Collection"
        in context.response.data
    )
    assert b"excluded from source material for this operation" in context.response.data


@then("AKOMO requires explicit browser confirmation before continuing")
def step_require_contained_confirmation(context):
    assert (
        b"explicitly accept organising into a destination inside the source"
        in context.response.data
    )
    assert context.record.state is CopyState.AWAITING_CONFIRMATION
    assert _snapshot(context.source) == context.source_before


@given("AKOMO has warned about the browser destination inside the source")
def step_contained_warning_displayed(context):
    step_contained_destination(context)
    _preflight(context)
    step_warn_contained_destination(context)


@when("the user declines the contained-destination browser COPY")
def step_decline_contained_copy(context):
    _decision(context, decision="decline")


@then("AKOMO performs no filesystem mutation for the contained destination")
def step_no_contained_mutation(context):
    assert context.record.state is CopyState.DECLINED
    assert _snapshot(context.source) == context.source_before


@when("the user confirms the contained-destination browser COPY")
def step_confirm_contained_copy(context):
    _decision(context, "copy")
    assert context.record.finished.wait(timeout=5)


@then("AKOMO organises the eligible browser source media")
def step_organise_eligible_contained_media(context):
    copied = list((context.destination / "2024").rglob("*.jpg"))
    assert len(copied) == 1
    assert copied[0].read_bytes() == b"valuable"


@then("the browser destination tree is not treated as source material")
def step_destination_not_source_material(context):
    assert [item.source for item in context.record.plan.items] == [
        context.source / "photo.jpg"
    ]
    assert (context.destination / "existing.jpg").read_bytes() == b"existing output"


@then("media written into the browser destination does not become a new candidate")
def step_output_not_candidate(context):
    assert context.record.result.total_files == 1


@then("a second browser COPY is not started")
def step_single_execution(context):
    assert context.calls == 1
