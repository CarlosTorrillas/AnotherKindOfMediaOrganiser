from pathlib import Path
from types import SimpleNamespace

import pytest

from another_kind_of_media_organiser.infrastructure import filesystem_capacity


def test_allocation_unit_uses_fundamental_statvfs_fragment_size(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        filesystem_capacity.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_frsize=131_072, f_bsize=1_048_576),
    )

    assert filesystem_capacity.allocation_unit(tmp_path / "future") == 131_072


def test_allocation_unit_falls_back_to_io_block_size(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        filesystem_capacity.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_frsize=0, f_bsize=4_096),
    )

    assert filesystem_capacity.allocation_unit(tmp_path / "future") == 4_096


def test_allocation_unit_fails_when_statvfs_has_no_valid_value(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        filesystem_capacity.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_frsize=0, f_bsize=0),
    )

    with pytest.raises(OSError, match="allocation unit is unavailable"):
        filesystem_capacity.allocation_unit(tmp_path / "future")
