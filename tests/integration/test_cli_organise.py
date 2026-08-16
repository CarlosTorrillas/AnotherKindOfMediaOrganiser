import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from another_kind_of_media_organiser import cli
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.cli import main


@pytest.fixture(autouse=True)
def deterministic_available_capacity(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "available_capacity",
        lambda _path: cli.DEFAULT_SAFETY_RESERVE_BYTES + 1024**4,
    )


def _dated_file(path: Path, content: bytes, year: int, month: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    timestamp = datetime(year, month, 1, tzinfo=timezone.utc).timestamp()
    os.utime(path, (timestamp, timestamp))


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


def test_move_requires_explicit_confirmation_then_removes_verified_source(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    media.write_bytes(b"valuable")
    destination = tmp_path / "destination"
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

    assert main(
        ["organise", str(source), "--destination", str(destination), "--move"]
    ) == 0

    captured = capsys.readouterr()
    copied = next(path for path in destination.rglob("*.jpg"))
    assert copied.read_bytes() == b"valuable"
    assert not media.exists()
    assert "Operation: MOVE" in captured.out
    assert "THIS OPERATION WILL DELETE SOURCE FILES." in captured.out
    assert "Source files deleted: 1" in captured.out


def test_declining_move_confirmation_changes_nothing(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    media.write_bytes(b"valuable")
    destination = tmp_path / "destination"
    monkeypatch.setattr("builtins.input", lambda _prompt: "no")

    assert main(
        ["organise", str(source), "--destination", str(destination), "--move"]
    ) == 0

    assert media.read_bytes() == b"valuable"
    assert not destination.exists()
    assert "cancelled before moving" in capsys.readouterr().out


@pytest.mark.parametrize("move", [False, True])
def test_accepted_partial_execution_only_processes_selected_oldest_month(
    tmp_path: Path, capsys, monkeypatch, move: bool
) -> None:
    source = tmp_path / "source"
    january = source / "january.jpg"
    february = source / "february.jpg"
    _dated_file(january, b"jan", 2024, 1)
    _dated_file(february, b"february", 2024, 2)
    destination = tmp_path / "destination"
    monkeypatch.setattr(
        cli,
        "available_capacity",
        lambda _path: cli.DEFAULT_SAFETY_RESERVE_BYTES + 3,
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
    arguments = ["organise", str(source), "--destination", str(destination)]
    if move:
        arguments.append("--move")

    assert main(arguments) == 0

    captured = capsys.readouterr()
    destinations = [path for path in destination.rglob("*") if path.is_file()]
    assert len(destinations) == 1
    assert destinations[0].read_bytes() == b"jan"
    assert "Partial organisation completed." in captured.out
    assert "Organised:\n  2024 January" in captured.out
    assert "2024/02" in captured.out
    assert february.read_bytes() == b"february"
    assert january.exists() is (not move)


def test_declining_partial_proposal_produces_zero_writes(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    _dated_file(source / "jan.jpg", b"jan", 2024, 1)
    _dated_file(source / "feb.jpg", b"february", 2024, 2)
    destination = tmp_path / "destination"
    monkeypatch.setattr(
        cli,
        "available_capacity",
        lambda _path: cli.DEFAULT_SAFETY_RESERVE_BYTES + 3,
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    assert main(["organise", str(source), "--destination", str(destination)]) == 0

    assert not destination.exists()
    assert len(tuple(source.glob("*.jpg"))) == 2
    assert "Continue with this partial organisation? [y/N]" in capsys.readouterr().out


def test_no_month_fits_and_capacity_query_failure_write_nothing(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "source"
    _dated_file(source / "jan.jpg", b"large", 2024, 1)
    destination = tmp_path / "destination"
    monkeypatch.setattr(
        cli,
        "available_capacity",
        lambda _path: cli.DEFAULT_SAFETY_RESERVE_BYTES + 4,
    )

    assert main(["organise", str(source), "--destination", str(destination)]) == 2
    assert not destination.exists()
    assert "No complete Year/Month group fits" in capsys.readouterr().err

    monkeypatch.setattr(
        cli,
        "available_capacity",
        lambda _path: (_ for _ in ()).throw(OSError("capacity unavailable")),
    )
    assert main(["organise", str(source), "--destination", str(destination)]) == 2
    assert not destination.exists()
    assert "capacity unavailable" in capsys.readouterr().err
