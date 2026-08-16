from pathlib import Path

from another_kind_of_media_organiser import cli
from another_kind_of_media_organiser.domain.media import InaccessiblePath


def incomplete_result(root: Path):
    result = cli.scan_media_collection(root)
    return type(result)(
        **{
            **result.__dict__,
            "inaccessible_paths": (
                InaccessiblePath(root / "private", "Permission denied"),
            ),
        }
    )


def test_propose_warns_that_its_scan_is_incomplete(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    (tmp_path / "photo.jpg").write_bytes(b"accessible")
    result = incomplete_result(tmp_path)
    monkeypatch.setattr(cli, "scan_media_collection", lambda _path: result)

    assert cli.main(["propose", str(tmp_path)]) == 0

    captured = capsys.readouterr()
    assert "Organisation proposal" in captured.out
    assert "WARNING: Scan is incomplete." in captured.err
    assert "Proposal includes accessible media only." in captured.err


def test_verify_collisions_warns_that_its_scan_is_incomplete(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    (tmp_path / "photo.jpg").write_bytes(b"accessible")
    result = incomplete_result(tmp_path)
    monkeypatch.setattr(cli, "scan_media_collection", lambda _path: result)
    monkeypatch.setattr(cli, "_open_digest_cache", lambda: None)

    assert cli.main(["verify-collisions", str(tmp_path)]) == 0

    captured = capsys.readouterr()
    assert "Collision verification" in captured.out
    assert "WARNING: Scan is incomplete." in captured.err
    assert "Verification covers accessible media only." in captured.err


def test_organise_refuses_incomplete_scan_before_any_write(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    media.write_bytes(b"valuable")
    destination = tmp_path / "destination"
    destination.mkdir()
    sentinel = destination / "existing.txt"
    sentinel.write_bytes(b"keep")
    result = incomplete_result(source)
    monkeypatch.setattr(cli, "scan_media_collection", lambda _path: result)

    def unexpected_action(*_args, **_kwargs):
        raise AssertionError(
            "incomplete scan must stop before planning or confirmation"
        )

    monkeypatch.setattr(cli, "generate_organisation_proposal", unexpected_action)
    monkeypatch.setattr("builtins.input", unexpected_action)

    assert (
        cli.main(["organise", str(source), "--destination", str(destination)])
        == 2
    )

    captured = capsys.readouterr()
    assert "Organisation refused: source scan is incomplete." in captured.err
    assert "No destination files or directories have been created." in captured.err
    assert media.read_bytes() == b"valuable"
    assert sentinel.read_bytes() == b"keep"
    assert sorted(destination.iterdir()) == [sentinel]
