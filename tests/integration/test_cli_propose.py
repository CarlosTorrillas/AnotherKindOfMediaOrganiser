import os
from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser.cli import main


def test_propose_command_prints_a_read_only_summary(tmp_path: Path, capsys) -> None:
    older = tmp_path / "recording.opus"
    older.touch()
    older_timestamp = datetime(2023, 2, 2, tzinfo=timezone.utc).timestamp()
    os.utime(older, (older_timestamp, older_timestamp))
    newer = tmp_path / "photo.jpg"
    newer.touch()
    newer_timestamp = datetime(2024, 1, 3, tzinfo=timezone.utc).timestamp()
    os.utime(newer, (newer_timestamp, newer_timestamp))
    (tmp_path / "notes.txt").touch()

    exit_code = main(["propose", str(tmp_path)])

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "Organisation proposal\n"
        "No files have been changed.\n"
        "\n"
        "Media files: 2\n"
        "Proposed destinations: 2\n"
        "Collisions: 0\n"
        "\n"
        "Years:\n"
        "2023: 1\n"
        "2024: 1\n"
    )

