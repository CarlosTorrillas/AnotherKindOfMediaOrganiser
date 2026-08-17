import os
from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser.infrastructure.digest_cache import (
    SqliteDigestCache,
)
from another_kind_of_media_organiser.presentation.web.verification_jobs import (
    VerificationCoordinator,
    VerificationState,
)


def _collision(root: Path) -> None:
    timestamp = datetime(2025, 2, 3, tzinfo=timezone.utc).timestamp()
    for directory in ("a", "b"):
        path = root / directory / "same.jpg"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"identical valuable media")
        os.utime(path, (timestamp, timestamp))


def _wait(job) -> None:
    assert job.finished.wait(timeout=5), "verification did not finish"


def test_browser_job_reuses_persistent_hashes_and_remains_read_only(
    tmp_path: Path,
) -> None:
    collection = tmp_path / "collection"
    _collision(collection)
    cache_path = tmp_path / "cache.sqlite3"
    before = {
        path.relative_to(collection): path.read_bytes()
        for path in collection.rglob("*")
        if path.is_file()
    }
    coordinator = VerificationCoordinator(
        cache_factory=lambda: SqliteDigestCache(cache_path)
    )

    first = coordinator.submit(collection, ())
    _wait(first)
    second = coordinator.submit(collection, ())
    _wait(second)

    assert first.state is VerificationState.COMPLETED
    assert first.progress is not None
    assert first.progress.cache_hits == 0
    assert first.progress.bytes_hashed > 0
    assert second.state is VerificationState.COMPLETED
    assert second.progress is not None
    assert second.progress.cache_hits == 2
    assert second.progress.bytes_hashed == 0
    after = {
        path.relative_to(collection): path.read_bytes()
        for path in collection.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_browser_job_can_be_cancelled_without_modifying_media(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    _collision(collection)
    before = tuple(sorted(collection.rglob("*")))

    def controlled_verifier(result, callback, *, digest_cache):
        callback(CollisionClassificationProgress(0, 1, 0, 0, 0, 0, 0))
        while True:
            callback(CollisionClassificationProgress(0, 1, 0, 0, 0, 1024, 0))

    from another_kind_of_media_organiser.application.generate_organisation_proposal import (
        CollisionClassificationProgress,
    )

    coordinator = VerificationCoordinator(verifier=controlled_verifier)
    job = coordinator.submit(collection, ())
    assert job.started.wait(timeout=2)

    coordinator.cancel(job.job_id)
    _wait(job)

    assert job.state is VerificationState.CANCELLED
    assert tuple(sorted(collection.rglob("*"))) == before
