"""Conservative filesystem copying for Organisation Execution."""

import os
import uuid
from collections.abc import Callable
from pathlib import Path


_COPY_CHUNK_SIZE = 1024 * 1024


def copy_file(
    source: Path,
    destination: Path,
    on_bytes_copied: Callable[[int], None],
) -> None:
    """Copy through a same-directory temporary file before final placement."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if _path_exists(destination):
        raise FileExistsError(destination)

    temporary = destination.parent / (
        f".{destination.name}.{uuid.uuid4().hex}.copying"
    )
    try:
        with source.open("rb") as source_file, temporary.open("xb") as temporary_file:
            _copy_stream(source_file, temporary_file, on_bytes_copied)
        temporary_metadata = temporary.stat()
        source_mtime_ns = source.stat().st_mtime_ns
        os.utime(
            temporary,
            ns=(temporary_metadata.st_atime_ns, source_mtime_ns),
        )
        if _path_exists(destination):
            raise FileExistsError(destination)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _copy_stream(source_file, destination_file, on_bytes_copied) -> None:
    while chunk := source_file.read(_COPY_CHUNK_SIZE):
        destination_file.write(chunk)
        on_bytes_copied(len(chunk))


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()
