import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.media import MediaCategory


def create_file(root: Path, relative_path: str, content: bytes = b"media") -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_scan_summarises_supported_and_unsupported_files(tmp_path: Path) -> None:
    create_file(tmp_path, "image.jpg")
    create_file(tmp_path, "image.PNG")
    create_file(tmp_path, "raw/cr2-file.cr2")
    create_file(tmp_path, "video/clip.m4v")
    create_file(tmp_path, "notes.txt")

    result = scan_media_collection(tmp_path)

    assert result.total_files == 5
    assert result.media_files == 4
    assert result.unsupported_files == 1
    assert result.directories_scanned == 3
    assert result.counts_by_category == {
        MediaCategory.IMAGE: 2,
        MediaCategory.RAW: 1,
        MediaCategory.VIDEO: 1,
        MediaCategory.AUDIO: 0,
    }


def test_scan_records_media_paths_categories_and_modification_dates(
    tmp_path: Path,
) -> None:
    media_path = create_file(tmp_path, "nested/photo.heic")
    timestamp = 1_735_732_800
    os.utime(media_path, (timestamp, timestamp))

    result = scan_media_collection(tmp_path)

    assert len(result.media_entries) == 1
    entry = result.media_entries[0]
    assert entry.path == media_path
    assert entry.category is MediaCategory.IMAGE
    assert entry.modification_date == datetime.fromtimestamp(timestamp, tz=timezone.utc)


def test_scan_does_not_change_files_or_create_content(tmp_path: Path) -> None:
    media_path = create_file(tmp_path, "photo.jpg", b"valuable original")
    unsupported_path = create_file(tmp_path, "catalog.db", b"catalog")
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in (media_path, unsupported_path)
    }
    paths_before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    scan_media_collection(tmp_path)

    paths_after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    after = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in (media_path, unsupported_path)
    }
    assert paths_after == paths_before
    assert after == before


def test_scan_does_not_follow_directory_symlinks(tmp_path: Path) -> None:
    scan_root = tmp_path / "collection"
    scan_root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    create_file(external, "outside.jpg")
    try:
        (scan_root / "external-link").symlink_to(external, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symbolic links are unavailable: {error}")

    result = scan_media_collection(scan_root)

    assert result.total_files == 0
    assert result.directories_scanned == 1
    assert result.media_entries == ()
