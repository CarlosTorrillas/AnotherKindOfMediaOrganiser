import tempfile
from pathlib import Path

from behave import given, then, when

from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.infrastructure import filesystem_scanner


def _root(context) -> Path:
    temporary = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary.cleanup)
    context.root = Path(temporary.name)
    return context.root


def _write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"media")
    return path


@given("a Media Collection containing a known macOS metadata directory")
def given_macos_metadata(context) -> None:
    root = _root(context)
    context.excluded = _write(root / ".Spotlight-V100" / "index.jpg").parent


@given("a hidden directory containing user media")
def given_hidden_media(context) -> None:
    context.hidden_media = _write(_root(context) / ".photos" / "photo.jpg")


@given("a Media Collection containing an explicitly excluded subtree")
def given_user_exclusion(context) -> None:
    root = _root(context)
    context.excluded = _write(root / "archive" / "old.jpg").parent
    context.user_exclusions = (Path("archive"),)


@given("a non-excluded directory reports an access failure")
def given_access_failure(context) -> None:
    root = _root(context)
    inaccessible = root / "private"
    original_walk = filesystem_scanner.os.walk

    def walk_with_error(scan_root, *, followlinks, onerror):
        onerror(PermissionError(13, "Permission denied", inaccessible))
        yield str(scan_root), [], []

    filesystem_scanner.os.walk = walk_with_error
    context.add_cleanup(setattr, filesystem_scanner.os, "walk", original_walk)


@given("an exclusion that escapes the Media Collection")
def given_escape(context) -> None:
    _root(context)
    context.user_exclusions = (Path("../outside"),)


@when("the Media Collection is scanned with default exclusions")
def when_default_scan(context) -> None:
    context.result = scan_media_collection(context.root)


@when("the Media Collection is scanned with that exclusion")
def when_excluded_scan(context) -> None:
    context.result = scan_media_collection(
        context.root, excluded_paths=context.user_exclusions
    )


@when("the Media Collection scan is requested")
def when_invalid_scan(context) -> None:
    try:
        scan_media_collection(context.root, excluded_paths=context.user_exclusions)
    except ValueError as error:
        context.error = error


@then("the metadata directory is reported as excluded")
@then("the excluded subtree is reported")
def then_reported(context) -> None:
    assert context.result.excluded_paths == (context.excluded,)


@then("the scan remains complete")
def then_complete(context) -> None:
    assert context.result.is_complete


@then("the hidden media is included in the scan")
def then_hidden_included(context) -> None:
    assert [entry.path for entry in context.result.media_entries] == [
        context.hidden_media
    ]


@then("media in the excluded subtree is absent")
def then_excluded_absent(context) -> None:
    assert context.result.media_entries == ()


@then("the scan remains incomplete")
def then_incomplete(context) -> None:
    assert not context.result.is_complete


@then("the exclusion is rejected before scanning")
def then_rejected(context) -> None:
    assert isinstance(context.error, ValueError)
