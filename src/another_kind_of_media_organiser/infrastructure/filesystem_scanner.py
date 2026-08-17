"""Read-only filesystem traversal for media collection scans."""

import os
import stat
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser.domain.media import (
    MediaCategory,
    MediaEntry,
    InaccessiblePath,
    ScanResult,
    classify_media,
    normalise_file_extension,
)


def scan_directory(
    root: Path,
    *,
    excluded_paths: frozenset[Path] = frozenset(),
) -> ScanResult:
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
    inaccessible_paths: dict[Path, InaccessiblePath] = {}
    encountered_exclusions: set[Path] = set()

    def record_inaccessible(error: OSError, path: Path | None = None) -> None:
        inaccessible_path = path or Path(error.filename or root)
        reason = error.strerror or type(error).__name__
        inaccessible_paths[inaccessible_path] = InaccessiblePath(
            inaccessible_path,
            reason,
        )

    for directory, child_directories, filenames in os.walk(
        root,
        followlinks=False,
        onerror=record_inaccessible,
    ):
        directory_path = Path(directory)
        included_directories = []
        for name in child_directories:
            path = directory_path / name
            if Path(os.path.abspath(path)) in excluded_paths:
                encountered_exclusions.add(path)
            elif not path.is_symlink():
                included_directories.append(name)
        child_directories[:] = included_directories
        directories_scanned += 1

        for filename in filenames:
            path = directory_path / filename
            if Path(os.path.abspath(path)) in excluded_paths:
                encountered_exclusions.add(path)
                continue
            try:
                metadata = path.lstat()
            except OSError as error:
                record_inaccessible(error, path)
                continue
            if stat.S_ISLNK(metadata.st_mode):
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
                metadata.st_mtime,
                tz=timezone.utc,
            )
            entries.append(MediaEntry(path, category, modification_date))

    counts_by_category = {
        category: category_counts[category]
        for category in MediaCategory
        if category is not MediaCategory.UNSUPPORTED
    }
    return ScanResult(
        total_files=total_files,
        unsupported_files=unsupported_files,
        directories_scanned=directories_scanned,
        counts_by_category=counts_by_category,
        recognised_extension_counts=dict(recognised_extension_counts),
        unsupported_extension_counts=dict(unsupported_extension_counts),
        media_entries=tuple(entries),
        inaccessible_paths=tuple(
            sorted(inaccessible_paths.values(), key=lambda item: item.path.as_posix())
        ),
        excluded_paths=tuple(
            sorted(encountered_exclusions, key=lambda path: path.as_posix())
        ),
    )
