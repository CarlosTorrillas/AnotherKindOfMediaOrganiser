"""Application use case for scanning a media collection."""

import os
from pathlib import Path

from another_kind_of_media_organiser.domain.media import ScanResult
from another_kind_of_media_organiser.infrastructure.filesystem_scanner import (
    scan_directory,
)


DEFAULT_MACOS_EXCLUSIONS = (
    Path(".DocumentRevisions-V100"),
    Path(".Spotlight-V100"),
    Path(".TemporaryItems"),
    Path(".Trashes"),
    Path(".fseventsd"),
)


def scan_media_collection(
    directory: Path,
    *,
    excluded_paths: tuple[Path, ...] = (),
) -> ScanResult:
    """Inspect a media collection and return its read-only summary."""
    exclusions = _normalise_exclusions(
        directory,
        DEFAULT_MACOS_EXCLUSIONS + excluded_paths,
    )
    return scan_directory(directory, excluded_paths=exclusions)


def _normalise_exclusions(root: Path, exclusions: tuple[Path, ...]) -> frozenset[Path]:
    root_absolute = Path(os.path.abspath(root))
    normalised: set[Path] = set()
    for exclusion in exclusions:
        if exclusion.is_absolute():
            raise ValueError(f"Exclusion must be relative to the scan root: {exclusion}")
        resolved = Path(os.path.abspath(root_absolute / exclusion))
        if resolved == root_absolute or not resolved.is_relative_to(root_absolute):
            raise ValueError(f"Exclusion escapes the scan root: {exclusion}")
        normalised.add(resolved)
    return frozenset(normalised)
