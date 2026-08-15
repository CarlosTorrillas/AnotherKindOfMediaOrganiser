from pathlib import Path

from another_kind_of_media_organiser.cli import main


def test_scan_command_prints_a_concise_summary(tmp_path: Path, capsys) -> None:
    (tmp_path / "photo.jpg").touch()
    (tmp_path / "negative.arw").touch()
    (tmp_path / "movie.mov").touch()
    (tmp_path / "notes.txt").touch()

    exit_code = main(["scan", str(tmp_path)])

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "Files scanned: 4\n"
        "Media files: 3\n"
        "Images: 1\n"
        "RAW: 1\n"
        "Videos: 1\n"
        "Unsupported: 1\n"
        "Directories scanned: 1\n"
    )

