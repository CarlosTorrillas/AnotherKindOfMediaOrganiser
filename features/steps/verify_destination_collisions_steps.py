import io
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from behave import given, then, when

from another_kind_of_media_organiser import cli
from another_kind_of_media_organiser.application import (
    generate_organisation_proposal as proposal_module,
)


def _run_verification(context) -> None:
    if not hasattr(context, "verification_cache_path"):
        cache_directory = tempfile.TemporaryDirectory()
        context.add_cleanup(cache_directory.cleanup)
        context.verification_cache_path = (
            Path(cache_directory.name) / "hash-cache.sqlite3"
        )
    original_cache_path = cli.default_digest_cache_path
    cli.default_digest_cache_path = lambda: context.verification_cache_path
    context.add_cleanup(
        lambda: setattr(cli, "default_digest_cache_path", original_cache_path)
    )
    output = io.StringIO()
    progress = io.StringIO()
    with redirect_stdout(output), redirect_stderr(progress):
        context.exit_code = cli.main(
            ["verify-collisions", str(context.collection)]
        )
    context.output = output.getvalue()
    context.progress = progress.getvalue()


@given("a Media Collection without Destination Collisions")
def step_collection_without_collisions(context) -> None:
    temporary_directory = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary_directory.cleanup)
    context.collection = Path(temporary_directory.name) / "collection"
    context.collection.mkdir()
    (context.collection / "unique.jpg").write_bytes(b"unique")


@given("a Destination Collision has already been content-verified")
def step_previously_verified_collision(context) -> None:
    temporary_directory = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary_directory.cleanup)
    context.collection = Path(temporary_directory.name) / "collection"
    for source_name in ("source-a", "source-b"):
        source = context.collection / source_name / "IMG_001.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"same")
    _run_verification(context)


@when("the user verifies destination collisions")
def step_verify_collisions(context) -> None:
    _run_verification(context)


@when("the user verifies destination collisions without hashing")
def step_verify_without_hashing(context) -> None:
    original_digest = proposal_module.file_content.sha256_digest

    def unexpected_digest(*_args, **_kwargs):
        raise AssertionError("collections without collisions must not be hashed")

    proposal_module.file_content.sha256_digest = unexpected_digest
    context.add_cleanup(
        lambda: setattr(
            proposal_module.file_content, "sha256_digest", original_digest
        )
    )
    _run_verification(context)


@when("the user verifies the same collision again")
def step_verify_again(context) -> None:
    _run_verification(context)


@then("collision verification reports one Exact Duplicate")
def step_reports_duplicate(context) -> None:
    assert context.exit_code == 0
    assert "Exact duplicate files: 1" in context.output


@then("collision verification reports one Potential Conflict")
def step_reports_conflict(context) -> None:
    assert context.exit_code == 0
    assert "Potential conflict files: 1" in context.output


@then("no collisions require verification")
def step_reports_no_collisions(context) -> None:
    assert context.exit_code == 0
    assert "No destination collisions require verification." in context.output


@then("collision verification reports cached hashes were reused")
def step_reports_cache_hits(context) -> None:
    assert "cache hits 2" in context.progress
    assert "hashed this run 0 B" in context.progress


@then("collision verification leaves the Media Collection unchanged")
def step_verification_read_only(context) -> None:
    paths_after = sorted(
        path.relative_to(context.collection) for path in context.collection.rglob("*")
    )
    state_after = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in context.sources
    }
    assert paths_after == context.paths_before
    assert state_after == context.state_before
