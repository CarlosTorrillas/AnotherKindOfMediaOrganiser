from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    CollisionClassificationProgress,
)
from another_kind_of_media_organiser.domain.media import MediaCategory, MediaEntry
from another_kind_of_media_organiser.domain.organisation import (
    OrganisationProposal,
    PlacementClassification,
    ProposedPlacement,
)
from another_kind_of_media_organiser.presentation.web import create_app
from another_kind_of_media_organiser.presentation.web.verification_jobs import (
    VerificationJob,
    VerificationState,
)


class FakeCoordinator:
    def __init__(self, job: VerificationJob) -> None:
        self.job = job
        self.submissions = []
        self.cancellations = []

    def submit(self, source: Path, exclusions: tuple[Path, ...]) -> VerificationJob:
        self.submissions.append((source, exclusions))
        return self.job

    def get(self, job_id: str) -> VerificationJob | None:
        return self.job if job_id == self.job.job_id else None

    def cancel(self, job_id: str) -> VerificationJob | None:
        self.cancellations.append(job_id)
        return self.get(job_id)


def _job(
    *,
    state: VerificationState = VerificationState.RUNNING,
    progress: CollisionClassificationProgress | None = None,
    proposal: OrganisationProposal | None = None,
    error: str | None = None,
) -> VerificationJob:
    return VerificationJob(
        job_id="job-123",
        source=Path("/collection"),
        exclusions=(Path("archive"),),
        state=state,
        progress=progress,
        proposal=proposal,
        error=error,
    )


def _client(job: VerificationJob):
    coordinator = FakeCoordinator(job)
    app = create_app(
        {"TESTING": True, "VERIFICATION_COORDINATOR": coordinator}
    )
    return app.test_client(), coordinator


def _verified_proposal(collision_count: int = 1) -> OrganisationProposal:
    created = datetime(2025, 2, 3, tzinfo=timezone.utc)
    placements = []
    destinations = []
    for number in range(collision_count):
        destination = Path(f"2025/02-February/IMAGE/photo-{number:04d}.jpg")
        destinations.append(destination)
        for suffix, classification in (
            ("canonical", PlacementClassification.CANONICAL),
            ("duplicate", PlacementClassification.EXACT_DUPLICATE),
        ):
            source = MediaEntry(
                Path(f"/collection/{number:04d}-{suffix}.jpg"),
                MediaCategory.IMAGE,
                created,
            )
            placements.append(
                ProposedPlacement(
                    source=source,
                    destination=destination,
                    normal_destination=destination,
                    category=MediaCategory.IMAGE,
                    media_creation_date=created,
                    has_collision=True,
                    classification=classification,
                )
            )
    return OrganisationProposal(tuple(placements), tuple(destinations))


def test_starting_verification_redirects_to_reconnectable_job_page() -> None:
    client, coordinator = _client(_job(state=VerificationState.QUEUED))

    response = client.post(
        "/verifications",
        data={"source": "/collection", "exclude": "archive"},
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/verifications/job-123")
    assert coordinator.submissions == [(Path("/collection"), (Path("archive"),))]


def test_running_verification_displays_progress_and_cancel_action() -> None:
    progress = CollisionClassificationProgress(47, 100, 20, 25, 2, 5_368_709_120, 31)
    client, _coordinator = _client(_job(progress=progress))

    response = client.get("/verifications/job-123")

    assert response.status_code == 200
    assert b"Verification is running" in response.data
    assert b"47% complete" in response.data
    assert b"47 / 100" in response.data
    assert b"47%" in response.data
    assert b"Cache hits</dt><dd>31" in response.data
    assert b"Hashed this run</dt><dd>5.0 GiB" in response.data
    assert b"Cancel verification" in response.data


def test_completed_verification_displays_classification_totals_and_cache() -> None:
    progress = CollisionClassificationProgress(3, 3, 1, 1, 1, 0, 2)
    client, _coordinator = _client(
        _job(
            state=VerificationState.COMPLETED,
            progress=progress,
            proposal=_verified_proposal(),
        )
    )

    response = client.get("/verifications/job-123")

    assert b"Collision Verification Result" in response.data
    assert b"Destination Collisions</dt><dd>1" in response.data
    assert b"Exact Duplicates</dt><dd>1" in response.data
    assert b"Potential Conflicts</dt><dd>0" in response.data
    assert b"Unverified Conflicts</dt><dd>0" in response.data
    assert b"Cache hits</dt><dd>2" in response.data
    assert b"Hashed this run</dt><dd>0 B" in response.data
    assert b"Identical content" in response.data
    assert b"Needs attention" in response.data
    assert b"Could not be verified" in response.data


def test_verification_displays_only_five_deterministic_examples() -> None:
    proposal = _verified_proposal(1_640)
    progress = CollisionClassificationProgress(1_640, 1_640, 1_640, 0, 0, 0, 0)
    client, _coordinator = _client(
        _job(
            state=VerificationState.COMPLETED,
            progress=progress,
            proposal=proposal,
        )
    )

    page = client.get("/verifications/job-123").data.decode()

    assert "Showing 5 of 1,640 collisions" in page
    assert "photo-0004.jpg" in page
    assert "photo-0005.jpg" not in page


def test_failed_verification_displays_safe_error_without_traceback() -> None:
    client, _coordinator = _client(
        _job(state=VerificationState.FAILED, error="Media Collection became unavailable.")
    )

    response = client.get("/verifications/job-123")

    assert response.status_code == 200
    assert b"Verification failed safely" in response.data
    assert b"Media Collection became unavailable." in response.data
    assert b"Traceback" not in response.data
    assert b"No files have been changed." in response.data


def test_cancelling_verification_signals_the_existing_job() -> None:
    client, coordinator = _client(_job())

    response = client.post("/verifications/job-123/cancel")

    assert response.status_code == 303
    assert coordinator.cancellations == ["job-123"]


def test_unsafe_verification_exclusion_is_rejected_before_job_creation() -> None:
    client, coordinator = _client(_job())

    response = client.post(
        "/verifications",
        data={"source": "/collection", "exclude": "../outside"},
    )

    assert response.status_code == 400
    assert coordinator.submissions == []
    assert b"must remain inside the Media Collection" in response.data
