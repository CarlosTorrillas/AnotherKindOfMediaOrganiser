from pathlib import Path

from another_kind_of_media_organiser import cli
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.cli import main


def test_declining_confirmation_creates_nothing(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "photo.jpg").write_bytes(b"valuable")
    destination = tmp_path / "destination"
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    assert main(["organise", str(source), "--destination", str(destination)]) == 0

    captured = capsys.readouterr()
    assert "Operation: COPY" in captured.out
    assert "Organisation cancelled before copying." in captured.out
    assert not destination.exists()
    assert (source / "photo.jpg").read_bytes() == b"valuable"


def test_accepting_confirmation_copies_the_lightweight_proposal(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    first = source / "a" / "IMG_001.jpg"
    second = source / "b" / "IMG_001.jpg"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    destination = tmp_path / "destination"
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

    def unexpected_verification(*_args, **_kwargs):
        raise AssertionError("organise must use the lightweight proposal")

    monkeypatch.setattr(
        cli,
        "generate_content_verified_organisation_proposal",
        unexpected_verification,
    )

    assert main(["organise", str(source), "--destination", str(destination)]) == 0

    captured = capsys.readouterr()
    copied_files = sorted(path for path in destination.rglob("*") if path.is_file())
    assert len(copied_files) == 2
    assert any(path.parent.name == "nameConflicts" for path in copied_files)
    assert "Organisation completed." in captured.out
    assert "Files copied: 2 / 2" in captured.out
    assert "Collision verification" not in captured.err
    assert first.read_bytes() == b"one"
    assert second.read_bytes() == b"two"


def test_destination_conflict_fails_before_confirmation_or_copying(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    media.write_bytes(b"source")
    destination = tmp_path / "destination"
    proposal = generate_organisation_proposal(scan_media_collection(source))
    existing = destination / proposal.placements[0].destination
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")

    def unexpected_confirmation(_prompt):
        raise AssertionError("preflight failures must not request confirmation")

    monkeypatch.setattr("builtins.input", unexpected_confirmation)

    assert main(["organise", str(source), "--destination", str(destination)]) == 2

    captured = capsys.readouterr()
    assert "already exists" in captured.err
    assert existing.read_bytes() == b"existing"
    assert media.read_bytes() == b"source"


def test_ctrl_c_reports_partial_completion_safely(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    media.write_bytes(b"source")
    destination = tmp_path / "destination"
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")

    def interrupted_execution(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "execute_organisation_plan", interrupted_execution, raising=False)

    assert main(["organise", str(source), "--destination", str(destination)]) == 130

    captured = capsys.readouterr()
    assert "Organisation cancelled." in captured.err
    assert "Source files have not been modified." in captured.err
    assert media.read_bytes() == b"source"


def test_runtime_failure_reports_partial_destination_state(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    media.write_bytes(b"source")
    destination = tmp_path / "destination"
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")

    def failed_execution(plan, _progress):
        item = plan.items[0]
        raise cli.OrganisationCopyError(
            item.source,
            item.destination,
            0,
            len(plan.items),
            OSError("disk full"),
        )

    monkeypatch.setattr(cli, "execute_organisation_plan", failed_execution)

    assert main(["organise", str(source), "--destination", str(destination)]) == 1

    captured = capsys.readouterr()
    assert "Organisation execution failed." in captured.err
    assert f"Failed source: {media}" in captured.err
    assert "Files copied: 0 / 1" in captured.err
    assert "Destination may contain successfully completed copies." in captured.err
    assert media.read_bytes() == b"source"
