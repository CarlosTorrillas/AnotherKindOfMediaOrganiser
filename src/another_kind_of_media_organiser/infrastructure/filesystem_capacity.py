"""Read-only destination filesystem capacity reporting."""

import os
import shutil
from pathlib import Path


def available_capacity(destination: Path) -> int:
    """Return free bytes on the filesystem that will contain destination."""
    return shutil.disk_usage(_existing_ancestor(destination)).free


def allocation_unit(destination: Path) -> int:
    """Return the fundamental allocation unit, with I/O block size fallback."""
    existing = _existing_ancestor(destination)
    filesystem = os.statvfs(existing)
    if isinstance(filesystem.f_frsize, int) and filesystem.f_frsize > 0:
        return filesystem.f_frsize
    if isinstance(filesystem.f_bsize, int) and filesystem.f_bsize > 0:
        return filesystem.f_bsize
    raise OSError(
        f"Destination filesystem allocation unit is unavailable: {destination}"
    )


def _existing_ancestor(destination: Path) -> Path:
    existing = destination.resolve(strict=False)
    while not existing.exists():
        parent = existing.parent
        if parent == existing:
            raise OSError(f"No existing ancestor for destination: {destination}")
        existing = parent
    return existing
