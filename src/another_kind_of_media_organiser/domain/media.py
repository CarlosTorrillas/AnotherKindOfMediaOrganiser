"""Domain concepts used when inspecting media collections."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Mapping


class MediaCategory(Enum):
    """A supported media category, or an unsupported file."""

    IMAGE = "IMAGE"
    RAW = "RAW"
    VIDEO = "VIDEO"
    UNSUPPORTED = "UNSUPPORTED"


_EXTENSIONS_BY_CATEGORY = {
    MediaCategory.IMAGE: frozenset({".jpg", ".jpeg", ".png", ".heic"}),
    MediaCategory.RAW: frozenset({".arw", ".cr2", ".nef"}),
    MediaCategory.VIDEO: frozenset({".mp4", ".mov", ".m4v"}),
}


def normalise_file_extension(filename: str | Path) -> str:
    """Return a lowercase extension, retaining extension-like dotfile names."""
    path = Path(filename)
    if path.suffix:
        return path.suffix.lower()
    if path.name.startswith(".") and len(path.name) > 1:
        return path.name.lower()
    return ""


def classify_media(filename: str | Path) -> MediaCategory:
    """Classify a filename using its case-insensitive extension."""
    extension = normalise_file_extension(filename)
    for category, extensions in _EXTENSIONS_BY_CATEGORY.items():
        if extension in extensions:
            return category
    return MediaCategory.UNSUPPORTED


@dataclass(frozen=True)
class MediaEntry:
    """A recognised media file discovered during a scan."""

    path: Path
    category: MediaCategory
    modification_date: datetime


@dataclass(frozen=True)
class ScanResult:
    """A read-only summary of a scanned media collection."""

    total_files: int
    unsupported_files: int
    directories_scanned: int
    counts_by_category: Mapping[MediaCategory, int]
    recognised_extension_counts: Mapping[str, int]
    unsupported_extension_counts: Mapping[str, int]
    media_entries: tuple[MediaEntry, ...]

    @property
    def media_files(self) -> int:
        """Return the number of recognised media files."""
        return len(self.media_entries)
