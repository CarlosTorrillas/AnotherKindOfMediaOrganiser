import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from another_kind_of_media_organiser.application import (
    generate_organisation_proposal as proposal_module,
)
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.infrastructure.digest_cache import (
    SqliteDigestCache,
)


def _collision(root: Path, contents: tuple[bytes, ...]):
    timestamp = datetime(2024, 8, 1, tzinfo=timezone.utc).timestamp()
    for index, content in enumerate(contents):
        path = root / f"source-{index}" / "IMG_001.jpg"
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        os.utime(path, (timestamp, timestamp))
    return scan_media_collection(root)


def test_cache_miss_hashes_and_second_run_reuses_persisted_digests(
    tmp_path: Path, monkeypatch
) -> None:
    collection = tmp_path / "media"
    scan_result = _collision(collection, (b"same", b"same"))
    database = tmp_path / "cache" / "hashes.sqlite3"
    real_digest = proposal_module.file_content.sha256_digest
    hash_calls: list[Path] = []

    def recording_digest(path: Path, **kwargs) -> str:
        hash_calls.append(path)
        return real_digest(path, **kwargs)

    monkeypatch.setattr(proposal_module.file_content, "sha256_digest", recording_digest)
    with SqliteDigestCache(database) as cache:
        first = generate_organisation_proposal(scan_result, digest_cache=cache)

    assert first.exact_duplicate_files == 1
    assert len(hash_calls) == 2
    assert database.is_file()

    hash_calls.clear()
    progress = []
    with SqliteDigestCache(database) as cache:
        second = generate_organisation_proposal(
            scan_result, progress.append, digest_cache=cache
        )

    assert second == first
    assert hash_calls == []
    assert progress[-1].cache_hits == 2
    assert progress[-1].bytes_hashed == 0


@pytest.mark.parametrize("change", ["size", "mtime"])
def test_changed_size_or_mtime_invalidates_cached_digest(
    tmp_path: Path, monkeypatch, change: str
) -> None:
    collection = tmp_path / "media"
    scan_result = _collision(collection, (b"same", b"same"))
    changed_path = collection / "source-1" / "IMG_001.jpg"
    database = tmp_path / "cache.sqlite3"
    with SqliteDigestCache(database) as cache:
        generate_organisation_proposal(scan_result, digest_cache=cache)

    if change == "size":
        for path in collection.glob("*/IMG_001.jpg"):
            path.write_bytes(b"new same-sized content")
    else:
        stat = changed_path.stat()
        os.utime(changed_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1))
    refreshed_scan = scan_media_collection(collection)
    real_digest = proposal_module.file_content.sha256_digest
    hash_calls: list[Path] = []

    def recording_digest(path: Path, **kwargs) -> str:
        hash_calls.append(path)
        return real_digest(path, **kwargs)

    monkeypatch.setattr(proposal_module.file_content, "sha256_digest", recording_digest)
    with SqliteDigestCache(database) as cache:
        generate_organisation_proposal(refreshed_scan, digest_cache=cache)

    if change == "size":
        assert len(hash_calls) == 2
    else:
        assert hash_calls == [changed_path]


def test_interrupted_run_preserves_completed_file_hashes(
    tmp_path: Path, monkeypatch
) -> None:
    collection = tmp_path / "media"
    scan_result = _collision(collection, (b"same", b"same", b"same"))
    database = tmp_path / "cache.sqlite3"

    def interrupt_after_first_candidate(progress) -> None:
        if progress.processed_candidates == 1:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        with SqliteDigestCache(database) as cache:
            generate_organisation_proposal(
                scan_result, interrupt_after_first_candidate, digest_cache=cache
            )

    real_digest = proposal_module.file_content.sha256_digest
    hash_calls: list[Path] = []

    def recording_digest(path: Path, **kwargs) -> str:
        hash_calls.append(path)
        return real_digest(path, **kwargs)

    monkeypatch.setattr(proposal_module.file_content, "sha256_digest", recording_digest)
    progress = []
    with SqliteDigestCache(database) as cache:
        proposal = generate_organisation_proposal(
            scan_result, progress.append, digest_cache=cache
        )

    assert proposal.exact_duplicate_files == 2
    assert hash_calls == [collection / "source-2" / "IMG_001.jpg"]
    assert progress[-1].cache_hits == 2
