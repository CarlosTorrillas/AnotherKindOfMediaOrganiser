import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from behave import given, then, when

from another_kind_of_media_organiser.application.capacity_preflight import DEFAULT_SAFETY_RESERVE_BYTES
from another_kind_of_media_organiser.application.execute_organisation_proposal import (
    OrganisationDeletionError,
    OrganisationExecutionMode,
    OrganisationExecutionProgress,
    OrganisationVerificationError,
)
from another_kind_of_media_organiser.presentation.web import create_app
from another_kind_of_media_organiser.presentation.web.copy_jobs import CopyCoordinator, CopyState


def _setup(context, *, available=None, executor=None):
    temporary = TemporaryDirectory()
    context.add_cleanup(temporary.cleanup)
    base = Path(temporary.name)
    context.source = base / "source"
    context.destination = base / "destination"
    options = {
        "available_capacity_provider": lambda _path: available or DEFAULT_SAFETY_RESERVE_BYTES + 1024**3,
        "allocation_unit_provider": lambda _path: 1,
    }
    if executor:
        options["executor"] = executor
    context.coordinator = CopyCoordinator(**options)
    context.client = create_app({"TESTING": True, "COPY_COORDINATOR": context.coordinator}).test_client()


def _media(path, content, month=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    stamp = datetime(2024, month, 1, tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamp, stamp))


def _snapshot(root):
    if not root.exists():
        return ()
    return tuple((p.relative_to(root).as_posix(), p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file())


def _prepare(context):
    context.record = context.coordinator.prepare(
        context.source, context.destination, (), mode=OrganisationExecutionMode.MOVE
    )
    context.preflight_url = f"/move-preflights/{context.record.copy_id}"
    context.status_url = f"/moves/{context.record.copy_id}"


@given("an accepted browser proposal for MOVE")
def step_move_proposal(context):
    _setup(context)
    _media(context.source / "photo.jpg", b"valuable")
    context.before = _snapshot(context.source)


@given("browser MOVE Capacity Preflight succeeds")
def step_move_preflight(context):
    _prepare(context)
    assert not context.record.capacity.is_partial


@when("the user explicitly confirms browser MOVE")
def step_confirm_move(context):
    context.coordinator.confirm(context.record.copy_id, acceptance="move")
    assert context.record.finished.wait(timeout=5)


@then("each browser MOVE file is copied")
def step_moved_copy(context):
    assert next(context.destination.rglob("*.jpg")).read_bytes() == b"valuable"


@then("its browser destination is verified")
def step_moved_verified(context):
    assert context.record.result.files_verified == 1


@then("only then is its browser source deleted")
def step_moved_deleted(context):
    assert context.record.result.source_files_deleted == 1
    assert not (context.source / "photo.jpg").exists()


@given("the browser organisation execution page is displayed")
def step_execution_page(context):
    _setup(context)
    _media(context.source / "photo.jpg", b"valuable")
    response = context.client.post("/proposal", data={"source": str(context.source)})
    context.page = response.data


@when("the user has not explicitly selected browser MOVE")
def step_no_move_selected(context):
    pass


@then("no destructive browser operation is selected")
def step_move_not_default(context):
    assert b"Organise by COPY" in context.page
    assert b"Organise by verified MOVE" in context.page
    assert b'name="acceptance"' not in context.page
    assert (context.source / "photo.jpg").is_file()


@given("the destructive browser MOVE confirmation is displayed")
def step_move_confirmation(context):
    _setup(context)
    _media(context.source / "photo.jpg", b"valuable")
    context.before = _snapshot(context.source)
    _prepare(context)
    context.page = context.client.get(context.preflight_url).data
    assert b"THIS OPERATION WILL DELETE SOURCE FILES." in context.page


@when("the user declines browser MOVE")
def step_decline_move(context):
    context.coordinator.decline(context.record.copy_id)


@then("no filesystem content is modified by browser MOVE")
def step_move_no_changes(context):
    assert _snapshot(context.source) == context.before
    assert not context.destination.exists()


@given("a browser destination copy cannot be verified")
def step_verify_failure(context):
    def fail(plan, callback, *, mode):
        item = plan.items[0]
        item.destination.parent.mkdir(parents=True)
        item.destination.write_bytes(b"bad")
        raise OrganisationVerificationError(item.source, item.destination, 1, 1, OSError("digest mismatch"))
    _setup(context, executor=fail)
    _media(context.source / "photo.jpg", b"valuable")
    _prepare(context)


@when("browser MOVE processes that file")
def step_process_verify_failure(context):
    context.coordinator.confirm(context.record.copy_id, acceptance="move")
    assert context.record.finished.wait(timeout=5)
    context.page = context.client.get(context.status_url).data


@then("the browser MOVE source file is not deleted")
def step_source_not_deleted(context):
    assert (context.source / "photo.jpg").is_file()


@then("the browser verification failure is reported")
def step_verify_reported(context):
    assert b"Organisation verification failed." in context.page
    assert b"Reason: digest mismatch" in context.page


@given("a browser destination has been copied and verified")
def step_delete_failure(context):
    def fail(plan, callback, *, mode):
        item = plan.items[0]
        item.destination.parent.mkdir(parents=True)
        item.destination.write_bytes(item.source.read_bytes())
        raise OrganisationDeletionError(item.source, item.destination, 1, 1, OSError("read only"), files_verified=1)
    _setup(context, executor=fail)
    _media(context.source / "photo.jpg", b"valuable")
    _prepare(context)


@when("browser source deletion fails")
def step_process_delete_failure(context):
    step_process_verify_failure(context)


@then("the verified browser destination remains")
def step_verified_destination_remains(context):
    assert next(context.destination.rglob("*.jpg")).read_bytes() == b"valuable"


@then("the browser MOVE source remains")
def step_move_source_remains(context):
    assert (context.source / "photo.jpg").read_bytes() == b"valuable"


@then("the browser deletion failure is reported")
def step_deletion_reported(context):
    assert b"Source deletion failed after COPY+VERIFY succeeded." in context.page
    assert b"Reason: read only" in context.page


@given("only a browser Partial Organisation Proposal fits MOVE")
def step_partial_move(context):
    _setup(context, available=DEFAULT_SAFETY_RESERVE_BYTES + 3)
    _media(context.source / "january.jpg", b"jan", 1)
    _media(context.source / "february.jpg", b"february", 2)
    _prepare(context)
    assert context.record.capacity.is_partial


@when("the user accepts and completes browser MOVE")
def step_accept_partial_move(context):
    context.coordinator.confirm(context.record.copy_id, acceptance="partial-move")
    assert context.record.finished.wait(timeout=5)


@then("only media in the accepted partial browser MOVE is moved")
def step_only_partial_moved(context):
    assert not (context.source / "january.jpg").exists()
    assert next(context.destination.rglob("*.jpg")).read_bytes() == b"jan"


@then("remaining browser source media is not modified")
def step_remaining_source(context):
    assert (context.source / "february.jpg").read_bytes() == b"february"


@given("browser MOVE execution is already running")
def step_move_running(context):
    context.release = Event()
    context.progress_reported = Event()
    context.add_cleanup(context.release.set)
    context.calls = 0

    def controlled(plan, callback, *, mode):
        context.calls += 1
        callback(OrganisationExecutionProgress(0, 1, 0, 0, 0))
        context.progress_reported.set()
        context.release.wait(timeout=5)
        return type("Result", (), {"files_copied": 0, "total_files": 1, "bytes_copied": 0, "files_verified": 0, "source_files_deleted": 0})()

    _setup(context, executor=controlled)
    _media(context.source / "photo.jpg", b"valuable")
    _prepare(context)
    context.coordinator.confirm(context.record.copy_id, acceptance="move")
    assert context.record.started.wait(timeout=2)
    assert context.progress_reported.wait(timeout=2)


@when("the browser reconnects to MOVE progress")
def step_reconnect_move(context):
    context.first = context.client.get(context.status_url).data
    context.second = context.client.get(context.status_url).data
    context.release.set()
    assert context.record.finished.wait(timeout=5)


@then("the existing browser MOVE execution is shown")
def step_existing_move(context):
    assert b"Organisation MOVE is running" in context.first
    assert context.first == context.second


@then("a second browser MOVE is not started")
def step_no_second_move(context):
    assert context.calls == 1


@given("the browser MOVE destination is contained within the source")
def step_contained_move_destination(context):
    _setup(context)
    context.destination = context.source / "Organised"
    _media(context.source / "photo.jpg", b"valuable")
    _media(context.destination / "existing.jpg", b"existing output")
    context.before = _snapshot(context.source)


@given("no contained-destination MOVE mutation has started")
def step_no_contained_move_mutation(context):
    assert _snapshot(context.source) == context.before


@when("the user starts contained-destination browser MOVE")
def step_start_contained_move(context):
    _prepare(context)
    context.page = context.client.get(context.preflight_url).data


@then("AKOMO warns that the MOVE destination is inside the source")
def step_warn_contained_move(context):
    assert b"Destination Collection is inside the source Media Collection" in context.page
    assert b"THIS OPERATION WILL DELETE SOURCE FILES." in context.page


@then("AKOMO requires explicit contained-destination MOVE confirmation")
def step_require_contained_move_confirmation(context):
    assert b"explicitly accept organising into a destination inside the source" in context.page
    assert context.record.state is CopyState.AWAITING_CONFIRMATION
    assert _snapshot(context.source) == context.before


@given("AKOMO has warned about contained-destination browser MOVE")
def step_contained_move_warned(context):
    step_contained_move_destination(context)
    step_start_contained_move(context)
    step_warn_contained_move(context)


@when("the user declines contained-destination browser MOVE")
def step_decline_contained_move(context):
    context.coordinator.decline(context.record.copy_id)


@then("no filesystem content is modified by contained-destination MOVE")
def step_contained_move_unchanged(context):
    assert context.record.state is CopyState.DECLINED
    assert _snapshot(context.source) == context.before


@when("the user confirms contained-destination browser MOVE")
def step_confirm_contained_move(context):
    context.coordinator.confirm(context.record.copy_id, acceptance="move")
    assert context.record.finished.wait(timeout=5)


@then("eligible source media is moved into the contained destination")
def step_eligible_contained_move(context):
    assert not (context.source / "photo.jpg").exists()
    copied = list((context.destination / "2024").rglob("*.jpg"))
    assert len(copied) == 1
    assert copied[0].read_bytes() == b"valuable"


@then("existing contained-destination media is not treated as source material")
def step_existing_contained_media_excluded(context):
    assert [item.source for item in context.record.plan.items] == [
        context.source / "photo.jpg"
    ]
    assert (context.destination / "existing.jpg").read_bytes() == b"existing output"


@then("contained-destination output does not become a new MOVE candidate")
def step_contained_move_output_fixed(context):
    assert context.record.result.total_files == 1


@given("browser MOVE awaits confirmation for a missing destination inside the source")
def step_missing_contained_move_confirmation(context):
    _setup(context)
    context.destination = context.source / "Organised"
    _media(context.source / "photo.jpg", b"valuable")
    _prepare(context)
    assert context.record.state is CopyState.AWAITING_CONFIRMATION
    assert not context.destination.exists()


@when("the user confirms MOVE into the missing contained destination")
def step_confirm_missing_contained_move(context):
    context.coordinator.confirm(context.record.copy_id, acceptance="move")
    assert context.record.finished.wait(timeout=5)


@then("the missing contained MOVE destination is created")
def step_missing_contained_move_created(context):
    assert context.destination.is_dir()


@then("eligible media is moved into the created contained destination")
def step_media_moved_into_created_contained_destination(context):
    copied = list(context.destination.rglob("*.jpg"))
    assert len(copied) == 1
    assert copied[0].read_bytes() == b"valuable"
    assert not (context.source / "photo.jpg").exists()
