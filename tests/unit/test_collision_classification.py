import os
from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser.application import generate_organisation_proposal as proposal_module
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.organisation import PlacementClassification


def colliding_scan_result(
    tmp_path: Path, contents: tuple[bytes, ...], suffix: str = ".jpg"
):
    timestamp = datetime(2024, 8, 1, tzinfo=timezone.utc).timestamp()
    paths = []
    for index, content in enumerate(contents):
        path = tmp_path / f"source-{index}" / f"IMG_001{suffix}"
        path.parent.mkdir()
        path.write_bytes(content)
        os.utime(path, (timestamp, timestamp))
        paths.append(path)
    return scan_media_collection(tmp_path), tuple(paths)


def placements_of(proposal, classification: PlacementClassification):
    return tuple(
        placement
        for placement in proposal.placements
        if placement.classification is classification
    )


def test_different_sizes_become_conflicts_without_hashing(
    tmp_path: Path, monkeypatch
) -> None:
    scan_result, _ = colliding_scan_result(tmp_path, (b"short", b"much longer"))

    def unexpected_hash(_path: Path) -> str:
        raise AssertionError("different-sized files must not be hashed")

    monkeypatch.setattr(proposal_module.file_content, "sha256_digest", unexpected_hash)

    proposal = generate_organisation_proposal(scan_result)

    assert proposal.exact_duplicate_files == 0
    assert proposal.potential_conflict_files == 1


def test_identical_content_creates_numbered_duplicate_destinations(
    tmp_path: Path,
) -> None:
    scan_result, paths = colliding_scan_result(
        tmp_path, (b"identical", b"identical", b"identical"), suffix=".JPG"
    )

    proposal = generate_organisation_proposal(scan_result)

    assert placements_of(proposal, PlacementClassification.CANONICAL)[0].source.path == paths[0]
    duplicates = placements_of(proposal, PlacementClassification.EXACT_DUPLICATE)
    assert [placement.destination.name for placement in duplicates] == [
        "IMG_001__dup1.JPG",
        "IMG_001__dup2.JPG",
    ]
    assert [placement.source.path for placement in duplicates] == list(paths[1:])


def test_mixed_content_groups_keep_every_source_once(tmp_path: Path) -> None:
    scan_result, paths = colliding_scan_result(
        tmp_path,
        (b"canonical", b"canonical", b"canonical", b"different", b"different"),
    )

    proposal = generate_organisation_proposal(scan_result)

    assert proposal.exact_duplicate_files == 2
    assert proposal.potential_conflict_files == 2
    assert proposal.unverified_conflict_files == 0
    assert [placement.destination.name for placement in placements_of(
        proposal, PlacementClassification.POTENTIAL_CONFLICT
    )] == ["IMG_001__conflict1.jpg", "IMG_001__conflict2.jpg"]
    assert sorted(placement.source.path for placement in proposal.placements) == sorted(paths)
    assert len(proposal.placements) == len(paths)


def test_hashes_only_same_sized_collision_candidates_once(
    tmp_path: Path, monkeypatch
) -> None:
    scan_result, paths = colliding_scan_result(
        tmp_path, (b"same", b"same", b"diff", b"a different size")
    )
    non_collision = tmp_path / "unique.jpg"
    non_collision.write_bytes(b"same")
    scan_result = scan_media_collection(tmp_path)
    hash_calls: list[Path] = []
    real_digest = proposal_module.file_content.sha256_digest

    def recording_digest(path: Path) -> str:
        hash_calls.append(path)
        return real_digest(path)

    monkeypatch.setattr(proposal_module.file_content, "sha256_digest", recording_digest)

    generate_organisation_proposal(scan_result)

    assert sorted(hash_calls) == sorted(paths[:3])
    assert len(hash_calls) == len(set(hash_calls))
    assert non_collision not in hash_calls


def test_unreadable_candidate_is_unverified_not_different(
    tmp_path: Path, monkeypatch
) -> None:
    scan_result, paths = colliding_scan_result(tmp_path, (b"same", b"same"))
    real_digest = proposal_module.file_content.sha256_digest

    def unreadable_digest(path: Path) -> str:
        if path == paths[1]:
            raise PermissionError(path)
        return real_digest(path)

    monkeypatch.setattr(proposal_module.file_content, "sha256_digest", unreadable_digest)

    proposal = generate_organisation_proposal(scan_result)

    unverified = placements_of(proposal, PlacementClassification.UNVERIFIED_CONFLICT)
    assert len(unverified) == 1
    assert unverified[0].source.path == paths[1]
    assert unverified[0].destination.name == "IMG_001__unverified1.jpg"
    assert proposal.exact_duplicate_files == 0
    assert proposal.potential_conflict_files == 0


def test_unreadable_canonical_makes_all_comparisons_unverified(
    tmp_path: Path, monkeypatch
) -> None:
    scan_result, paths = colliding_scan_result(tmp_path, (b"same", b"same", b"diff"))

    def unreadable_canonical(path: Path) -> str:
        if path == paths[0]:
            raise PermissionError(path)
        raise AssertionError("candidates should not be hashed without a canonical digest")

    monkeypatch.setattr(
        proposal_module.file_content, "sha256_digest", unreadable_canonical
    )

    proposal = generate_organisation_proposal(scan_result)

    assert proposal.unverified_conflict_files == 2
    assert proposal.exact_duplicate_files == 0
    assert proposal.potential_conflict_files == 0

