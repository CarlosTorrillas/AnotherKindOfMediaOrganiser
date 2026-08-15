"""Read-only filesystem traversal for media collection scans."""

import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser.domain.media import (
    MediaCategory,
    MediaEntry,
    ScanResult,
    classify_media,
    normalise_file_extension,
)


def scan_directory(root: Path) -> ScanResult:
    """Recursively inspect a directory without following symbolic links."""
    if not root.is_dir():
        raise NotADirectoryError(root)

    entries: list[MediaEntry] = []
    category_counts: Counter[MediaCategory] = Counter()
    recognised_extension_counts: Counter[str] = Counter()
    unsupported_extension_counts: Counter[str] = Counter()
    total_files = 0
    unsupported_files = 0
    directories_scanned = 0

    for directory, child_directories, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        child_directories[:] = [
            name for name in child_directories if not (directory_path / name).is_symlink()
        ]
        directories_scanned += 1

        for filename in filenames:
            path = directory_path / filename
            if path.is_symlink():
                continue

            total_files += 1
            category = classify_media(path)
            extension = normalise_file_extension(path)
            if category is MediaCategory.UNSUPPORTED:
                unsupported_files += 1
                unsupported_extension_counts[extension] += 1
                continue

            category_counts[category] += 1
            recognised_extension_counts[extension] += 1
            modification_date = datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=timezone.utc,
            )
            entries.append(MediaEntry(path, category, modification_date))

    counts_by_category = {
        category: category_counts[category]
        for category in (
            MediaCategory.IMAGE,
            MediaCategory.RAW,
            MediaCategory.VIDEO,
        )
    }
    return ScanResult(
        total_files=total_files,
        unsupported_files=unsupported_files,
        directories_scanned=directories_scanned,
        counts_by_category=counts_by_category,
        recognised_extension_counts=dict(recognised_extension_counts),
        unsupported_extension_counts=dict(unsupported_extension_counts),
        media_entries=tuple(entries),
    )
