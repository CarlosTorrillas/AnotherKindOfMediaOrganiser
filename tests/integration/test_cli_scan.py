from pathlib import Path

from another_kind_of_media_organiser.cli import main


def test_scan_command_prints_a_concise_summary(tmp_path: Path, capsys) -> None:
    (tmp_path / "photo.jpg").touch()
    (tmp_path / "portrait.JPG").touch()
    (tmp_path / "negative.arw").touch()
    (tmp_path / "movie.mov").touch()
    (tmp_path / "picture.webp").touch()
    (tmp_path / "camera.dng").touch()
    (tmp_path / "recording.3gp").touch()
    (tmp_path / "voice.opus").touch()
    (tmp_path / "notes.txt").touch()
    (tmp_path / "data.TXT").touch()
    (tmp_path / ".DS_Store").touch()
    (tmp_path / "README").touch()

    exit_code = main(["scan", str(tmp_path)])

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "Files scanned: 12\n"
        "Media files: 8\n"
        "Images: 3\n"
        "RAW: 2\n"
        "Videos: 2\n"
        "Audio: 1\n"
        "Unsupported: 4\n"
        "Directories scanned: 1\n"
        "\n"
        "Recognised media:\n"
        ".jpg: 2\n"
        ".3gp: 1\n"
        ".arw: 1\n"
        ".dng: 1\n"
        ".mov: 1\n"
        ".opus: 1\n"
        ".webp: 1\n"
        "\n"
        "Unsupported:\n"
        ".txt: 2\n"
        ".ds_store: 1\n"
        "[no extension]: 1\n"
    )


def test_scan_command_reports_a_missing_directory_without_a_traceback(
    tmp_path: Path, capsys
) -> None:
    missing_directory = tmp_path / "missing"

    exit_code = main(["scan", str(missing_directory)])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert captured.out == ""
    assert captured.err == f"Error: '{missing_directory}' is not a valid directory.\n"
    assert "Traceback" not in captured.err


def test_scan_command_reports_a_file_without_a_traceback(
    tmp_path: Path, capsys
) -> None:
    file_path = tmp_path / "photo.jpg"
    file_path.touch()

    exit_code = main(["scan", str(file_path)])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert captured.out == ""
    assert captured.err == f"Error: '{file_path}' is not a valid directory.\n"
    assert "Traceback" not in captured.err
