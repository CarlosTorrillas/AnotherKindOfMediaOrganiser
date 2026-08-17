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


def test_web_command_binds_to_localhost_by_default(capsys, monkeypatch) -> None:
    import another_kind_of_media_organiser.presentation.web as web

    calls = []

    class FakeApp:
        def run(self, **options):
            calls.append(options)

    monkeypatch.setattr(web, "create_app", lambda: FakeApp())

    assert main(["web"]) == 0

    captured = capsys.readouterr()
    assert captured.out == "Read-only browser interface: http://127.0.0.1:8080\n"
    assert captured.err == ""
    assert calls == [
        {"host": "127.0.0.1", "port": 8080, "debug": False, "use_reloader": False}
    ]


def test_web_command_warns_for_an_explicit_non_local_bind(capsys, monkeypatch) -> None:
    import another_kind_of_media_organiser.presentation.web as web

    class FakeApp:
        def run(self, **_options):
            pass

    monkeypatch.setattr(web, "create_app", lambda: FakeApp())

    assert main(["web", "--host", "0.0.0.0", "--port", "9000"]) == 0

    captured = capsys.readouterr()
    assert "http://0.0.0.0:9000" in captured.out
    assert "no authentication" in captured.err


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
