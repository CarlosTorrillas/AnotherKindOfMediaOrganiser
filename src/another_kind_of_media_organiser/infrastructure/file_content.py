"""Read-only file content inspection for collision classification."""

import hashlib
from collections.abc import Callable
from pathlib import Path


_DEFAULT_CHUNK_SIZE = 1024 * 1024


def file_size(path: Path) -> int:
    """Return a file's size without reading its content."""
    return path.stat().st_size


def sha256_digest(
    path: Path,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    on_bytes_read: Callable[[int], None] | None = None,
) -> str:
    """Calculate a SHA-256 digest while reading a file in bounded chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
            if on_bytes_read is not None:
                on_bytes_read(len(chunk))
    return digest.hexdigest()
