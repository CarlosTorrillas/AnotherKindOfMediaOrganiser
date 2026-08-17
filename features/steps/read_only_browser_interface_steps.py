import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from behave import given, then, when

from another_kind_of_media_organiser.domain.media import (
    InaccessiblePath,
    MediaCategory,
    ScanResult,
)
from another_kind_of_media_organiser.presentation.web import create_app
import another_kind_of_media_organiser.presentation.web.routes as routes


def _workspace(context) -> Path:
    temporary = TemporaryDirectory()
    context.add_cleanup(temporary.cleanup)
    context.root = Path(temporary.name)
    return context.root


def _media(path: Path, contents: bytes = b"media") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    stamp = datetime(2025, 2, 3, tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamp, stamp))


def _client(context):
    if not hasattr(context, "client"):
        context.client = create_app({"TESTING": True}).test_client()
    return context.client


def _snapshot(root: Path) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        (str(path.relative_to(root)), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


@given("the web server is running")
@given("the browser interface is open")
def step_web_running(context):
    _client(context)


@when("the user opens the root page")
def step_open_root(context):
    context.response = _client(context).get("/")


@then("the Media Collection form is displayed")
def step_form_displayed(context):
    assert b"Media Collection path" in context.response.data


@then("no filesystem modification occurs")
def step_no_modification_on_open(context):
    assert context.response.status_code == 200


@given("a valid Media Collection path is provided")
def step_valid_collection(context):
    root = _workspace(context)
    _media(root / "photo.jpg")
    (root / "notes.txt").write_text("notes")


@when("the user starts a browser scan")
def step_start_scan(context):
    context.response = _client(context).post("/scan", data={"source": str(context.root)})


@then("the Scan Result is displayed")
def step_scan_result(context):
    assert b"Scan Result" in context.response.data


@then("the browser scan is reported as complete")
def step_complete(context):
    assert b"Scan complete: YES" in context.response.data


@then("recognised and unsupported media counts are shown")
def step_counts(context):
    assert b"Recognised media" in context.response.data
    assert b"Unsupported files" in context.response.data


@then("directories scanned are shown")
def step_directories(context):
    assert b"Directories scanned" in context.response.data


@given("a Media Collection contains an excluded path")
def step_collection_with_exclusion(context):
    root = _workspace(context)
    _media(root / "included.jpg")
    _media(root / "archive" / "excluded.jpg")


@when("the user scans the collection with that exclusion")
def step_scan_excluding(context):
    context.response = _client(context).post(
        "/scan", data={"source": str(context.root), "exclude": "archive"}
    )


@then("the excluded path is reported")
def step_excluded_reported(context):
    assert b"archive" in context.response.data
    assert b"Excluded paths</dt><dd>1" in context.response.data


@then("excluded media is not included in the Scan Result")
def step_excluded_not_scanned(context):
    assert b"Recognised media</dt><dd>1" in context.response.data


@then("the excluded path is not reported as inaccessible")
def step_excluded_not_inaccessible(context):
    assert b"Inaccessible paths</dt><dd>0" in context.response.data


@given("a Media Collection scan reports an inaccessible non-excluded path")
@given("the browser Scan Result is incomplete")
def step_incomplete_result(context):
    context.original_scan = routes.scan_media_collection
    context.add_cleanup(setattr, routes, "scan_media_collection", context.original_scan)
    routes.scan_media_collection = lambda *_a, **_k: ScanResult(
        total_files=0,
        unsupported_files=0,
        directories_scanned=1,
        counts_by_category={category: 0 for category in MediaCategory},
        recognised_extension_counts={},
        unsupported_extension_counts={},
        media_entries=(),
        inaccessible_paths=(
            InaccessiblePath(Path("z-private"), "denied"),
            InaccessiblePath(Path("a-private"), "denied"),
        ),
    )


@when("that Scan Result is displayed in the browser")
def step_display_incomplete(context):
    context.response = _client(context).post("/scan", data={"source": "/collection"})


@then("the browser scan is reported as incomplete")
def step_report_incomplete(context):
    assert b"Scan complete: NO" in context.response.data


@then("a prominent incomplete-scan warning is displayed")
def step_incomplete_warning(context):
    assert b"WARNING: Scan is incomplete." in context.response.data


@then("deterministic inaccessible-path examples are shown")
def step_inaccessible_order(context):
    assert context.response.data.index(b"a-private") < context.response.data.index(b"z-private")


@given("a Media Collection has been scanned from the browser")
def step_scanned_collection(context):
    root = _workspace(context)
    _media(root / "photo.jpg", b"valuable")
    context.before = _snapshot(root)
    _client(context).post("/scan", data={"source": str(root)})


@when("the user requests an Organisation Proposal")
def step_request_proposal(context):
    context.response = _client(context).post(
        "/proposal", data={"source": str(context.root)}
    )


@then("the existing lightweight proposal workflow is used")
def step_lightweight_workflow(context):
    assert context.response.status_code == 200


@then("the proposal is displayed")
@then("the proposal may include accessible media")
def step_proposal_displayed(context):
    assert b"Organisation Proposal" in context.response.data


@then("no file content is hashed")
def step_no_hash(context):
    assert b"Exact Duplicate" not in context.response.data


@then("no filesystem content is modified")
def step_collection_unchanged(context):
    assert _snapshot(context.root) == context.before


@given("the lightweight Organisation Proposal contains destination collisions")
def step_collision_collection(context):
    root = _workspace(context)
    _media(root / "a" / "same.jpg", b"one")
    _media(root / "b" / "same.jpg", b"two")


@when("the proposal is displayed in the browser")
def step_show_collision_proposal(context):
    context.response = _client(context).post(
        "/proposal", data={"source": str(context.root)}
    )


@then("the destination collision count is shown")
def step_collision_count(context):
    assert b"Destination collisions</dt><dd>1" in context.response.data


@then("the Name Conflict file count is shown")
def step_name_conflict_count(context):
    assert b"Name Conflict files</dt><dd>1" in context.response.data


@then("deterministic collision examples are displayed")
def step_collision_examples(context):
    assert b"2025/02-February/IMAGE/same.jpg" in context.response.data


@when("the user requests a browser Organisation Proposal for the incomplete scan")
def step_incomplete_proposal(context):
    context.response = _client(context).post("/proposal", data={"source": "/collection"})


@then("a prominent proposal warning states that the underlying scan is incomplete")
def step_incomplete_proposal_warning(context):
    assert b"Proposal includes accessible media only." in context.response.data


@when("the user submits a missing source")
def step_missing_source(context):
    context.response = _client(context).post("/scan", data={"source": "/missing/collection"})


@then("a clear browser validation error is displayed")
def step_validation_error(context):
    assert context.response.status_code == 400
    assert b"not a valid directory" in context.response.data


@then("no Python traceback is exposed")
def step_no_traceback(context):
    assert b"Traceback" not in context.response.data


@when("the user submits an exclusion escaping the scan root")
def step_unsafe_exclusion(context):
    context.response = _client(context).post(
        "/scan", data={"source": "/collection", "exclude": "../outside"}
    )


@then("the browser exclusion is rejected")
def step_exclusion_rejected(context):
    assert context.response.status_code == 400
    assert b"must remain inside" in context.response.data


@then("scanning does not proceed with that unsafe exclusion")
def step_unsafe_not_scanned(context):
    assert b"Scan Result" not in context.response.data


@given("a submitted browser value contains executable markup")
def step_markup_value(context):
    context.unsafe_value = "<script>alert('unsafe')</script>"


@when("the value is rendered by the browser interface")
def step_render_markup(context):
    context.response = _client(context).post("/scan", data={"source": context.unsafe_value})


@then("the browser value is safely escaped")
def step_value_escaped(context):
    assert b"&lt;script&gt;" in context.response.data


@then("it cannot inject executable markup")
def step_no_markup_injection(context):
    assert context.unsafe_value.encode() not in context.response.data


@then("no media is copied, moved, deleted, or renamed")
@then("no proposed directories are created")
def step_read_only(context):
    assert _snapshot(context.root) == context.before
