import os
from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser import cli
from another_kind_of_media_organiser.cli import main


def set_modification_date(path: Path, date: datetime) -> None:
    timestamp = date.timestamp()
    os.utime(path, (timestamp, timestamp))


def create_collision(
    root: Path, filename: str, date: datetime, source_directories: tuple[str, ...]
) -> tuple[Path, ...]:
    source_paths = tuple(root / directory / filename for directory in source_directories)
    for path in source_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        set_modification_date(path, date)
    return source_paths


def test_propose_command_prints_a_read_only_summary(tmp_path: Path, capsys) -> None:
    older = tmp_path / "recording.opus"
    older.touch()
    set_modification_date(older, datetime(2023, 2, 2, tzinfo=timezone.utc))
    newer = tmp_path / "photo.jpg"
    newer.touch()
    set_modification_date(newer, datetime(2024, 1, 3, tzinfo=timezone.utc))
    (tmp_path / "notes.txt").touch()

    exit_code = main(["propose", str(tmp_path)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out == (
        "Organisation proposal\n"
        "No files have been changed.\n"
        "\n"
        "Media files: 2\n"
        "Proposed destinations: 2\n"
        "Destination collisions: 0\n"
        "Exact duplicate files: 0\n"
        "Potential conflict files: 0\n"
        "Unverified conflict files: 0\n"
        "\n"
        "Years:\n"
        "2023: 1\n"
        "2024: 1\n"
    )
    assert captured.err == ""


def test_propose_command_displays_a_collision_and_all_competing_sources(
    tmp_path: Path, capsys
) -> None:
    date = datetime(2024, 1, 3, tzinfo=timezone.utc)
    first, second, third = create_collision(
        tmp_path,
        "IMG_001.jpg",
        date,
        ("camera-a", "camera-b", "backup"),
    )

    exit_code = main(["propose", str(tmp_path)])

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "Organisation proposal\n"
        "No files have been changed.\n"
        "\n"
        "Media files: 3\n"
        "Proposed destinations: 3\n"
        "Destination collisions: 1\n"
        "Exact duplicate files: 2\n"
        "Potential conflict files: 0\n"
        "Unverified conflict files: 0\n"
        "\n"
        "Years:\n"
        "2024: 3\n"
        "\n"
        "Collision examples:\n"
        "\n"
        "2024/01-January/IMAGE/IMG_001.jpg\n"
        "  canonical:\n"
        f"    {third}\n"
        "  exact duplicate:\n"
        f"    {first}\n"
        "  exact duplicate:\n"
        f"    {second}\n"
        "\n"
        "Showing 1 of 1 collisions\n"
    )


def test_propose_command_shows_at_most_ten_deterministic_collision_examples(
    tmp_path: Path, capsys
) -> None:
    date = datetime(2024, 6, 15, tzinfo=timezone.utc)
    for number in reversed(range(12)):
        create_collision(
            tmp_path,
            f"IMG_{number:03d}.jpg",
            date,
            (f"source-b-{number:03d}", f"source-a-{number:03d}"),
        )

    assert main(["propose", str(tmp_path)]) == 0
    first_output = capsys.readouterr().out
    assert main(["propose", str(tmp_path)]) == 0
    second_output = capsys.readouterr().out

    assert first_output == second_output
    destination_lines = [
        line
        for line in first_output.splitlines()
        if line.startswith("2024/06-June/IMAGE/")
    ]
    assert destination_lines == [
        f"2024/06-June/IMAGE/IMG_{number:03d}.jpg" for number in range(10)
    ]
    assert "IMG_010.jpg\n" not in first_output
    assert "IMG_011.jpg\n" not in first_output
    assert "Destination collisions: 12\n" in first_output
    assert "Exact duplicate files: 12\n" in first_output
    assert "Potential conflict files: 0\n" in first_output
    assert "Unverified conflict files: 0\n" in first_output
    assert "Showing 10 of 12 collisions\n" in first_output


def test_non_interactive_progress_uses_plain_periodic_lines(
    tmp_path: Path, capsys
) -> None:
    date = datetime(2024, 1, 3, tzinfo=timezone.utc)
    create_collision(tmp_path, "IMG_001.jpg", date, ("a", "b", "c"))

    assert main(["propose", str(tmp_path)]) == 0

    progress_output = capsys.readouterr().err
    assert "Collision classification: 0/2 files" in progress_output
    assert "Collision classification: 2/2 files" in progress_output
    assert "\r" not in progress_output
    assert "\x1b" not in progress_output


def test_ctrl_c_during_proposal_reports_safe_cancellation(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    media_path = tmp_path / "photo.jpg"
    media_path.write_bytes(b"valuable media")

    def interrupted_proposal(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "generate_organisation_proposal", interrupted_proposal)

    assert main(["propose", str(tmp_path)]) == 130

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "Proposal generation cancelled.\n"
        "No files have been changed.\n"
    )
    assert media_path.read_bytes() == b"valuable media"
