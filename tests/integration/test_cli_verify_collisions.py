import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from another_kind_of_media_organiser import cli
from another_kind_of_media_organiser.application import (
    generate_organisation_proposal as proposal_module,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.cli import main


@pytest.fixture(autouse=True)
def isolated_digest_cache(tmp_path: Path, monkeypatch) -> Path:
    cache_path = tmp_path.parent / f"{tmp_path.name}-hash-cache.sqlite3"
    monkeypatch.setattr(cli, "default_digest_cache_path", lambda: cache_path)
    return cache_path


def create_collision(
    root: Path, filename: str, contents: tuple[bytes, ...]
) -> tuple[Path, ...]:
    timestamp = datetime(2024, 8, 1, tzinfo=timezone.utc).timestamp()
    paths = []
    for index, content in enumerate(contents):
        path = root / f"source-{index}" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        os.utime(path, (timestamp, timestamp))
        paths.append(path)
    return tuple(paths)


def test_help_distinguishes_lightweight_proposal_from_deep_verification(
    capsys,
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--help"])

    assert raised.value.code == 0
    output = capsys.readouterr().out
    assert "propose" in output
    assert "verify-collisions" in output
    assert "deep" in output


def test_verify_collisions_classifies_content_and_remains_read_only(
    tmp_path: Path, capsys
) -> None:
    duplicate_paths = create_collision(
        tmp_path, "IMG_001.jpg", (b"identical", b"identical")
    )
    conflict_paths = create_collision(
        tmp_path, "IMG_002.jpg", (b"content-a", b"content-b")
    )
    state_before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (*duplicate_paths, *conflict_paths)
    }

    assert main(["verify-collisions", str(tmp_path)]) == 0

    captured = capsys.readouterr()
    assert "Collision verification" in captured.out
    assert "Destination collisions: 2" in captured.out
    assert "Exact duplicate files: 1" in captured.out
    assert "Potential conflict files: 1" in captured.out
    assert "Unverified conflict files: 0" in captured.out
    assert "This may take a long time" in captured.out
    assert "Collision verification:" in captured.err
    assert state_before == {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in state_before
    }


def test_verify_collisions_reports_unreadable_candidate(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    _, candidate = create_collision(
        tmp_path, "IMG_001.jpg", (b"same size", b"same size")
    )
    real_scan = scan_media_collection

    def scan_then_remove_candidate(directory: Path):
        result = real_scan(directory)
        candidate.unlink()
        return result

    monkeypatch.setattr(cli, "scan_media_collection", scan_then_remove_candidate)

    assert main(["verify-collisions", str(tmp_path)]) == 0

    assert "Unverified conflict files: 1" in capsys.readouterr().out


def test_no_collisions_performs_no_hashing(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    (tmp_path / "unique.jpg").write_bytes(b"unique")

    def unexpected_digest(*_args, **_kwargs):
        raise AssertionError("no collision content should be hashed")

    monkeypatch.setattr(
        proposal_module.file_content, "sha256_digest", unexpected_digest
    )

    assert main(["verify-collisions", str(tmp_path)]) == 0

    captured = capsys.readouterr()
    assert "No destination collisions require verification." in captured.out
    assert "Collision verification:" not in captured.err


def test_second_verification_reuses_persistent_hashes(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    create_collision(tmp_path, "IMG_001.jpg", (b"same", b"same"))
    real_digest = proposal_module.file_content.sha256_digest
    hash_calls: list[Path] = []

    def recording_digest(path: Path, **kwargs) -> str:
        hash_calls.append(path)
        return real_digest(path, **kwargs)

    monkeypatch.setattr(
        proposal_module.file_content, "sha256_digest", recording_digest
    )

    assert main(["verify-collisions", str(tmp_path)]) == 0
    first = capsys.readouterr()
    assert len(hash_calls) == 2
    assert "cache hits 0" in first.err

    hash_calls.clear()
    assert main(["verify-collisions", str(tmp_path)]) == 0
    second = capsys.readouterr()
    assert hash_calls == []
    assert "cache hits 2" in second.err
    assert "hashed this run 0 B" in second.err


def test_ctrl_c_during_verification_is_safe(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    media_path = tmp_path / "photo.jpg"
    media_path.write_bytes(b"valuable media")

    def interrupted_verification(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        cli,
        "generate_content_verified_organisation_proposal",
        interrupted_verification,
        raising=False,
    )

    assert main(["verify-collisions", str(tmp_path)]) == 130

    captured = capsys.readouterr()
    assert "Collision verification cancelled." in captured.err
    assert "No files have been changed." in captured.err
    assert media_path.read_bytes() == b"valuable media"
