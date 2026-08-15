from pathlib import Path

from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)


def create_files(root: Path, *filenames: str) -> None:
    for filename in filenames:
        (root / filename).touch()


def test_reports_recognised_extensions_case_insensitively(tmp_path: Path) -> None:
    create_files(
        tmp_path,
        "first.jpg",
        "second.JPG",
        "portrait.jpeg",
        "negative.NEF",
        "clip.mov",
    )

    result = scan_media_collection(tmp_path)

    assert result.recognised_extension_counts == {
        ".jpg": 2,
        ".jpeg": 1,
        ".nef": 1,
        ".mov": 1,
    }


def test_reports_unsupported_extensions_case_insensitively(tmp_path: Path) -> None:
    create_files(tmp_path, "first.xmp", "second.XMP", "edit.aae", ".DS_Store")

    result = scan_media_collection(tmp_path)

    assert result.unsupported_extension_counts == {
        ".xmp": 2,
        ".aae": 1,
        ".ds_store": 1,
    }


def test_reports_files_without_extensions_explicitly(tmp_path: Path) -> None:
    create_files(tmp_path, "README", "LICENSE")

    result = scan_media_collection(tmp_path)

    assert result.unsupported_extension_counts == {"": 2}


def test_extension_counts_are_consistent_with_scan_totals(tmp_path: Path) -> None:
    create_files(
        tmp_path,
        "photo.jpg",
        "portrait.png",
        "negative.arw",
        "sidecar.xmp",
        "document.pdf",
        "README",
    )

    result = scan_media_collection(tmp_path)

    recognised_count = sum(result.recognised_extension_counts.values())
    unsupported_count = sum(result.unsupported_extension_counts.values())
    assert recognised_count == result.media_files
    assert unsupported_count == result.unsupported_files
    assert recognised_count + unsupported_count == result.total_files

