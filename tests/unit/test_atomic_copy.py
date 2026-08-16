import os
from pathlib import Path

import pytest

from another_kind_of_media_organiser.infrastructure import atomic_copy


def test_copies_through_a_temporary_file_and_preserves_mtime(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"valuable media")
    os.utime(source, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    destination = tmp_path / "nested" / "destination.jpg"
    copied_chunks: list[int] = []

    atomic_copy.copy_file(source, destination, copied_chunks.append)

    assert destination.read_bytes() == b"valuable media"
    assert destination.stat().st_mtime_ns == source.stat().st_mtime_ns
    assert sum(copied_chunks) == len(b"valuable media")
    assert list(destination.parent.glob("*.copying")) == []


def test_failed_copy_removes_only_its_temporary_file(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"valuable media")
    destination = tmp_path / "destination.jpg"
    pre_existing = tmp_path / ".someone-elses.copying"
    pre_existing.write_bytes(b"do not remove")

    def fail_after_partial_copy(source_file, destination_file, callback):
        destination_file.write(source_file.read(4))
        callback(4)
        raise OSError("destination disconnected")

    monkeypatch.setattr(atomic_copy, "_copy_stream", fail_after_partial_copy)

    with pytest.raises(OSError):
        atomic_copy.copy_file(source, destination, lambda _count: None)

    assert not destination.exists()
    assert pre_existing.read_bytes() == b"do not remove"
    assert [path for path in tmp_path.iterdir() if path.name.endswith(".copying")] == [
        pre_existing
    ]


def test_cancelled_copy_removes_the_incomplete_temporary_file(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"valuable media")
    destination = tmp_path / "destination.jpg"

    def cancel_after_partial_copy(source_file, destination_file, callback):
        destination_file.write(source_file.read(4))
        callback(4)
        raise KeyboardInterrupt

    monkeypatch.setattr(atomic_copy, "_copy_stream", cancel_after_partial_copy)

    with pytest.raises(KeyboardInterrupt):
        atomic_copy.copy_file(source, destination, lambda _count: None)

    assert not destination.exists()
    assert not tuple(tmp_path.glob("*.copying"))
