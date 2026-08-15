"""Application use case for scanning a media collection."""

from pathlib import Path

from another_kind_of_media_organiser.domain.media import ScanResult
from another_kind_of_media_organiser.infrastructure.filesystem_scanner import (
    scan_directory,
)


def scan_media_collection(directory: Path) -> ScanResult:
    """Inspect a media collection and return its read-only summary."""
    return scan_directory(directory)

