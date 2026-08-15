from pathlib import Path

from another_kind_of_media_organiser.cli import main


def test_scan_command_prints_a_concise_summary(tmp_path: Path, capsys) -> None:
    (tmp_path / "photo.jpg").touch()
    (tmp_path / "portrait.JPG").touch()
    (tmp_path / "negative.arw").touch()
    (tmp_path / "movie.mov").touch()
    (tmp_path / "notes.txt").touch()
    (tmp_path / "data.TXT").touch()
    (tmp_path / ".DS_Store").touch()
    (tmp_path / "README").touch()

    exit_code = main(["scan", str(tmp_path)])

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "Files scanned: 8\n"
        "Media files: 4\n"
        "Images: 2\n"
        "RAW: 1\n"
        "Videos: 1\n"
        "Unsupported: 4\n"
        "Directories scanned: 1\n"
        "\n"
        "Recognised media:\n"
        ".jpg: 2\n"
        ".arw: 1\n"
        ".mov: 1\n"
        "\n"
        "Unsupported:\n"
        ".txt: 2\n"
        ".ds_store: 1\n"
        "[no extension]: 1\n"
    )
