"""Read-only destination filesystem capacity reporting."""

import shutil
from pathlib import Path


def available_capacity(destination: Path) -> int:
    """Return free bytes on the filesystem that will contain destination."""
    existing = destination.resolve(strict=False)
    while not existing.exists():
        parent = existing.parent
        if parent == existing:
            raise OSError(f"No existing ancestor for destination: {destination}")
        existing = parent
    return shutil.disk_usage(existing).free
