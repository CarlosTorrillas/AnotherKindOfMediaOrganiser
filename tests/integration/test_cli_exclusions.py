from pathlib import Path

import pytest

from another_kind_of_media_organiser import cli


def write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_scan_reports_excluded_paths(tmp_path: Path, capsys) -> None:
    excluded = write(tmp_path / ".Spotlight-V100" / "index.jpg", b"system")
    write(tmp_path / "photo.jpg", b"photo")

    assert cli.main(["scan", str(tmp_path)]) == 0

    output = capsys.readouterr().out
    assert "Scan complete: YES" in output
    assert "Excluded paths: 1" in output
    assert str(excluded.parent) in output
    assert "Inaccessible paths: 0" in output


def test_excluded_media_is_absent_from_proposal(tmp_path: Path, capsys) -> None:
    write(tmp_path / "archive" / "old.jpg", b"old")
    write(tmp_path / "photo.jpg", b"current")

    assert cli.main(["propose", str(tmp_path), "--exclude", "archive"]) == 0

    output = capsys.readouterr().out
    assert "Media files: 1" in output
    assert "Excluded paths: 1" in output


@pytest.mark.parametrize("move", [False, True])
def test_copy_and_move_never_touch_excluded_media(
    tmp_path: Path, monkeypatch, move: bool
) -> None:
    source = tmp_path / "source"
    included = write(source / "current.jpg", b"current")
    excluded = write(source / "archive" / "valuable.jpg", b"do not touch")
    destination = tmp_path / "destination"
    monkeypatch.setattr(
        cli,
        "available_capacity",
        lambda _path: cli.DEFAULT_SAFETY_RESERVE_BYTES + 1024**3,
    )
    monkeypatch.setattr(cli, "allocation_unit", lambda _path: 1)
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
    arguments = [
        "organise",
        str(source),
        "--destination",
        str(destination),
        "--exclude",
        "archive",
    ]
    if move:
        arguments.append("--move")

    assert cli.main(arguments) == 0

    assert excluded.read_bytes() == b"do not touch"
    assert included.exists() is (not move)
    copied = [path for path in destination.rglob("*.jpg")]
    assert len(copied) == 1
    assert copied[0].read_bytes() == b"current"


def test_cli_rejects_exclusion_that_escapes_source(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    source.mkdir()

    assert cli.main(["scan", str(source), "--exclude", "../outside"]) == 2

    assert "Exclusion" in capsys.readouterr().err
