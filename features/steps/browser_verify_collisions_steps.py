import os
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from behave import given, then, when

from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    CollisionClassificationProgress,
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.media import MediaCategory, MediaEntry
from another_kind_of_media_organiser.domain.organisation import (
    OrganisationProposal,
    PlacementClassification,
    ProposedPlacement,
)
from another_kind_of_media_organiser.infrastructure import file_content
from another_kind_of_media_organiser.infrastructure.digest_cache import (
    SqliteDigestCache,
)
from another_kind_of_media_organiser.presentation.web import create_app
from another_kind_of_media_organiser.presentation.web.verification_jobs import (
    VerificationCoordinator,
    VerificationJob,
    VerificationState,
)


def _workspace(context) -> Path:
    temporary = TemporaryDirectory()
    context.add_cleanup(temporary.cleanup)
    context.root = Path(temporary.name) / "collection"
    context.root.mkdir()
    context.cache_path = Path(temporary.name) / "hash-cache.sqlite3"
    return context.root


def _write_collision(root: Path, contents: tuple[bytes, ...]) -> None:
    timestamp = datetime(2025, 2, 3, tzinfo=timezone.utc).timestamp()
    for number, content in enumerate(contents):
        path = root / chr(ord("a") + number) / "same.jpg"
        path.parent.mkdir()
        path.write_bytes(content)
        os.utime(path, (timestamp, timestamp))


def _snapshot(root: Path) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def _real_client(context, *, verifier=None):
    options = {"cache_factory": lambda: SqliteDigestCache(context.cache_path)}
    if verifier is not None:
        options["verifier"] = verifier
    context.coordinator = VerificationCoordinator(**options)
    context.client = create_app(
        {"TESTING": True, "VERIFICATION_COORDINATOR": context.coordinator}
    ).test_client()


def _start(context):
    response = context.client.post(
        "/verifications", data={"source": str(context.root)}
    )
    context.location = response.headers["Location"]
    context.job_id = context.location.rsplit("/", 1)[-1]
    context.job = context.coordinator.get(context.job_id)
    assert context.job is not None


def _wait(job: VerificationJob) -> None:
    assert job.finished.wait(timeout=5)


def _wait_for_progress(job: VerificationJob) -> None:
    deadline = time.monotonic() + 2
    while job.progress is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert job.progress is not None


def _proposal(count: int) -> OrganisationProposal:
    created = datetime(2025, 2, 3, tzinfo=timezone.utc)
    placements = []
    destinations = []
    for number in range(count):
        destination = Path(f"2025/02-February/IMAGE/photo-{number:04d}.jpg")
        destinations.append(destination)
        entry = MediaEntry(
            Path(f"/collection/photo-{number:04d}.jpg"),
            MediaCategory.IMAGE,
            created,
        )
        placements.append(
            ProposedPlacement(
                entry,
                destination,
                destination,
                MediaCategory.IMAGE,
                created,
                True,
                PlacementClassification.CANONICAL,
            )
        )
    return OrganisationProposal(tuple(placements), tuple(destinations))


class _FixedCoordinator:
    def __init__(self, job: VerificationJob) -> None:
        self.job = job

    def get(self, job_id: str):
        return self.job if job_id == self.job.job_id else None

    def cancel(self, job_id: str):
        return self.get(job_id)


@given("an Organisation Proposal contains browser destination collisions")
def step_collision_proposal(context):
    root = _workspace(context)
    _write_collision(root, (b"same", b"same", b"diff", b"read"))
    context.before = _snapshot(root)
    real_digest = file_content.sha256_digest

    def unreadable(path, **kwargs):
        if path.parent.name == "d":
            raise OSError("unreadable")
        return real_digest(path, **kwargs)

    file_content.sha256_digest = unreadable
    context.add_cleanup(setattr, file_content, "sha256_digest", real_digest)
    _real_client(context)
    proposal_page = context.client.post(
        "/proposal", data={"source": str(root)}
    )
    assert b"Verify Collisions" in proposal_page.data


@when("the user chooses Verify Collisions")
def step_choose_verify(context):
    _start(context)
    _wait(context.job)
    context.response = context.client.get(context.location)


@then("the existing deep collision verification workflow is executed")
def step_deep_workflow(context):
    assert context.job.state is VerificationState.COMPLETED


@then("Exact Duplicates are reported in the browser")
def step_exact(context):
    assert b"Exact Duplicates</dt><dd>1" in context.response.data


@then("Potential Conflicts are reported in the browser")
def step_potential(context):
    assert b"Potential Conflicts</dt><dd>1" in context.response.data


@then("Unverified Conflicts are reported in the browser")
def step_unverified(context):
    assert b"Unverified Conflicts</dt><dd>1" in context.response.data


@then("browser verification modifies no media")
def step_no_modification(context):
    if hasattr(context, "before"):
        assert _snapshot(context.root) == context.before


def _running_verifier(context):
    context.release = Event()
    context.add_cleanup(context.release.set)

    def verifier(result, callback, *, digest_cache):
        callback(CollisionClassificationProgress(47, 100, 20, 25, 2, 1024, 31))
        context.release.wait(timeout=5)
        callback(CollisionClassificationProgress(100, 100, 40, 55, 5, 1024, 31))
        return generate_organisation_proposal(result)

    return verifier


@given("browser collision verification is running")
def step_running(context):
    root = _workspace(context)
    _write_collision(root, (b"same", b"same"))
    context.before = _snapshot(root)
    _real_client(context, verifier=_running_verifier(context))
    _start(context)
    _wait_for_progress(context.job)


@when("progress is reported by the existing application workflow")
def step_progress_reported(context):
    context.response = context.client.get(context.location)


@then("the browser shows meaningful verification progress")
def step_progress_visible(context):
    assert b"47 / 100" in context.response.data
    assert b"Cache hits</dt><dd>31" in context.response.data


@then("the user can see that verification is still active")
def step_active(context):
    assert b"Verification is running" in context.response.data


@when("the user refreshes the verification page")
def step_refresh(context):
    context.first_response = context.client.get(context.location)
    context.response = context.client.get(context.location)


@then("the current verification progress is displayed")
def step_current_progress(context):
    assert b"47 / 100" in context.response.data


@then("the same verification job continues")
def step_same_job(context):
    assert context.job.state is VerificationState.RUNNING
    assert context.first_response.data == context.response.data


@given("previous collision hashes are available in the persistent cache")
def step_cached_hashes(context):
    root = _workspace(context)
    _write_collision(root, (b"same", b"same"))
    context.before = _snapshot(root)
    _real_client(context)
    _start(context)
    _wait(context.job)
    assert context.job.progress.cache_hits == 0


@when("browser verification is started again")
def step_verify_again(context):
    _start(context)
    _wait(context.job)
    context.response = context.client.get(context.location)


@then("valid cached hashes are reused by browser verification")
def step_cache_reused(context):
    assert context.job.progress.cache_hits == 2
    assert context.job.progress.bytes_hashed == 0


@then("cache hits are visible in the browser result")
def step_cache_visible(context):
    assert b"Cache hits</dt><dd>2" in context.response.data


@given("browser verification contains many collision results")
def step_many_results(context):
    proposal = _proposal(1_640)
    progress = CollisionClassificationProgress(1_640, 1_640, 0, 0, 0, 0, 0)
    job = VerificationJob(
        "many", Path("/collection"), (), VerificationState.COMPLETED,
        progress=progress, proposal=proposal,
    )
    coordinator = _FixedCoordinator(job)
    context.client = create_app(
        {"TESTING": True, "VERIFICATION_COORDINATOR": coordinator}
    ).test_client()


@when("the browser verification result is displayed")
def step_display_many(context):
    context.response = context.client.get("/verifications/many")


@then("at most 5 deterministic verification examples are shown")
def step_five_examples(context):
    page = context.response.data.decode()
    assert "photo-0004.jpg" in page
    assert "photo-0005.jpg" not in page


@then("the total number of browser verification collisions is visible")
def step_total_visible(context):
    assert b"Showing 5 of 1,640 collisions" in context.response.data


@when("the user cancels browser verification")
def step_cancel(context):
    context.response = context.client.post(
        f"/verifications/{context.job_id}/cancel", follow_redirects=True
    )
    context.release.set()
    _wait(context.job)
    context.response = context.client.get(context.location)


@then("browser verification stops safely")
def step_cancelled(context):
    assert context.job.state is VerificationState.CANCELLED
    assert b"Verification cancelled" in context.response.data


@then("completed hashes remain reusable")
def step_hashes_reusable(context):
    assert b"Completed hashes remain cached and can be reused." in context.response.data


@given("browser collision verification cannot complete")
def step_failure(context):
    root = _workspace(context)
    _write_collision(root, (b"same", b"same"))
    context.before = _snapshot(root)

    def fail(*_args, **_kwargs):
        raise OSError(5, "Input/output error")

    _real_client(context, verifier=fail)
    _start(context)
    _wait(context.job)


@when("the browser verification error occurs")
def step_show_failure(context):
    context.response = context.client.get(context.location)


@then("a clear browser verification error is displayed")
def step_safe_error(context):
    assert b"Verification failed safely" in context.response.data
    assert b"Input/output error" in context.response.data


@then("no Python traceback is exposed by browser verification")
def step_no_traceback(context):
    assert b"Traceback" not in context.response.data


@given("the browser interface is open for verification")
def step_open_for_verification(context):
    root = _workspace(context)
    _write_collision(root, (b"same", b"same"))
    context.before = _snapshot(root)
    _real_client(context)


@when("the user verifies collisions from the browser")
def step_verify_read_only(context):
    _start(context)
    _wait(context.job)


@then("no files are copied, moved, deleted, or renamed by verification")
def step_all_read_only(context):
    assert _snapshot(context.root) == context.before
