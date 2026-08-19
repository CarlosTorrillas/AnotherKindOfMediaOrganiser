import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from behave import given, then, when

from another_kind_of_media_organiser import cli
from another_kind_of_media_organiser.domain.media import InaccessiblePath


@given("a Scan Result containing an inaccessible path")
def step_incomplete_result(context) -> None:
    temporary_directory = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary_directory.cleanup)
    context.root = Path(temporary_directory.name)
    context.source = context.root / "source"
    context.source.mkdir()
    context.media = context.source / "photo.jpg"
    context.media.write_bytes(b"valuable")
    context.destination = context.root / "destination"
    context.destination.mkdir()
    context.sentinel = context.destination / "existing.txt"
    context.sentinel.write_bytes(b"keep")
    result = cli.scan_media_collection(context.source)
    context.inaccessible = context.source / "private"
    context.result = replace(
        result,
        inaccessible_paths=(
            InaccessiblePath(context.inaccessible, "Permission denied"),
        ),
    )
    original_scan = cli.scan_media_collection
    cli.scan_media_collection = lambda _path: context.result
    context.add_cleanup(
        lambda: setattr(cli, "scan_media_collection", original_scan)
    )


def _run(context, arguments: list[str]) -> None:
    output = StringIO()
    error = StringIO()
    with redirect_stdout(output), redirect_stderr(error):
        context.exit_code = cli.main(arguments)
    context.output = output.getvalue()
    context.error = error.getvalue()


@when("the user requests the scan summary")
def step_scan_summary(context) -> None:
    _run(context, ["scan", str(context.source)])


@when("the user proposes organisation from the incomplete scan")
def step_partial_proposal(context) -> None:
    _run(context, ["propose", str(context.source)])


@when("the user verifies collisions from the incomplete scan")
def step_partial_verification(context) -> None:
    original_cache = cli._open_digest_cache
    cli._open_digest_cache = lambda: None
    context.add_cleanup(lambda: setattr(cli, "_open_digest_cache", original_cache))
    _run(context, ["verify-collisions", str(context.source)])


def _run_incomplete_execution(context, answer: str) -> None:
    with patch("builtins.input", return_value=answer):
        _run(
            context,
            [
                "organise",
                str(context.source),
                "--destination",
                str(context.destination),
            ],
        )


@when("the user declines Organisation Execution from the incomplete scan")
def step_declined_execution(context) -> None:
    _run_incomplete_execution(context, "no")


@when("the user accepts Organisation Execution from the incomplete scan")
def step_accepted_execution(context) -> None:
    _run_incomplete_execution(context, "yes")


@then("the CLI reports that the scan is incomplete")
def step_cli_incomplete(context) -> None:
    assert "Scan complete: NO" in context.output


@then("the CLI reports the inaccessible path")
def step_cli_inaccessible_path(context) -> None:
    assert str(context.inaccessible) in context.output
    assert "Permission denied" in context.output


@then("the CLI warns that the proposal includes accessible media only")
def step_partial_proposal_warning(context) -> None:
    assert "WARNING: Scan is incomplete." in context.error
    assert "Proposal includes accessible media only." in context.error


@then("the CLI warns that verification covers accessible media only")
def step_partial_verification_warning(context) -> None:
    assert "WARNING: Scan is incomplete." in context.error
    assert "Verification covers accessible media only." in context.error


@then("the incomplete-operation warning and inaccessible scope are reported")
def step_incomplete_warning(context) -> None:
    assert context.exit_code == 0
    assert "Some files or folders cannot be accessed." in context.output
    assert "The COPY operation will be incomplete." in context.output
    assert str(context.inaccessible) in context.output
    assert "Permission denied" in context.output
    assert "organise the accessible media" in context.output


@then("the accessible media is organised")
def step_accessible_media_organised(context) -> None:
    assert context.exit_code == 0
    copied = next(context.destination.rglob("*.jpg"))
    assert copied.read_bytes() == b"valuable"
    assert context.media.read_bytes() == b"valuable"


@then("the skipped inaccessible scope is reported after completion")
def step_skipped_scope_reported(context) -> None:
    assert "Organisation completed with inaccessible items skipped." in context.output
    assert "Skipped inaccessible paths: 1" in context.output
    assert str(context.inaccessible) in context.output
    assert "Inaccessible items were left untouched." in context.output


@then("the source and Destination Collection remain unchanged")
def step_collections_unchanged(context) -> None:
    assert context.media.read_bytes() == b"valuable"
    assert context.sentinel.read_bytes() == b"keep"
    assert sorted(context.destination.iterdir()) == [context.sentinel]
