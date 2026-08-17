from pathlib import Path

import pytest

from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.infrastructure import filesystem_scanner


def media(path: Path, content: bytes = b"media") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@pytest.mark.parametrize(
    "directory_name",
    [
        ".DocumentRevisions-V100",
        ".Spotlight-V100",
        ".TemporaryItems",
        ".Trashes",
        ".fseventsd",
    ],
)
def test_known_macos_directory_is_excluded_without_making_scan_incomplete(
    tmp_path: Path, directory_name: str
) -> None:
    excluded = media(tmp_path / directory_name / "system.jpg")
    included = media(tmp_path / "photo.jpg")

    result = scan_media_collection(tmp_path)

    assert result.is_complete
    assert [entry.path for entry in result.media_entries] == [included]
    assert result.excluded_paths == (excluded.parent,)
    assert result.inaccessible_paths == ()


def test_arbitrary_hidden_directory_is_not_excluded(tmp_path: Path) -> None:
    hidden_media = media(tmp_path / ".private-photos" / "photo.jpg")

    result = scan_media_collection(tmp_path)

    assert [entry.path for entry in result.media_entries] == [hidden_media]
    assert result.excluded_paths == ()


def test_user_exclusion_prunes_subtree_and_is_reported(tmp_path: Path) -> None:
    excluded_media = media(tmp_path / "archive" / "nested" / "old.jpg")
    included = media(tmp_path / "current.jpg")

    result = scan_media_collection(tmp_path, excluded_paths=(Path("archive"),))

    assert [entry.path for entry in result.media_entries] == [included]
    assert result.excluded_paths == (excluded_media.parents[1],)
    assert result.is_complete


@pytest.mark.parametrize("excluded", [Path("../outside"), Path("/absolute")])
def test_exclusion_cannot_escape_scan_root(tmp_path: Path, excluded: Path) -> None:
    with pytest.raises(ValueError, match="Exclusion"):
        scan_media_collection(tmp_path, excluded_paths=(excluded,))


def test_non_excluded_access_failure_remains_incomplete(
    tmp_path: Path, monkeypatch
) -> None:
    inaccessible = tmp_path / "private"

    def walk_with_error(root, *, followlinks, onerror):
        onerror(PermissionError(13, "Permission denied", inaccessible))
        yield str(root), [], []

    monkeypatch.setattr(filesystem_scanner.os, "walk", walk_with_error)

    result = scan_media_collection(tmp_path)

    assert not result.is_complete
    assert result.excluded_paths == ()
    assert result.inaccessible_paths[0].path == inaccessible
