from io import StringIO

from another_kind_of_media_organiser import cli
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    CollisionClassificationProgress,
)
from another_kind_of_media_organiser.cli import main


def test_cli_identifies_application(capsys) -> None:
    exit_code = main([])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "AnotherKindOfMediaOrganiser\n"
    assert captured.err == ""


class InteractiveStream(StringIO):
    def isatty(self) -> bool:
        return True


def test_interactive_progress_reuses_one_terminal_line() -> None:
    output = InteractiveStream()
    reporter = cli._CollisionProgressReporter(output, clock=lambda: 1.0)

    reporter(CollisionClassificationProgress(0, 2, 0, 0, 0, 0))
    reporter(CollisionClassificationProgress(2, 2, 1, 1, 0, 12))

    assert output.getvalue().count("\r") == 2
    assert output.getvalue().endswith("\n")
    assert "2/2 files" in output.getvalue()
