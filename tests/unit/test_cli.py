from another_kind_of_media_organiser.cli import main


def test_cli_identifies_application(capsys) -> None:
    exit_code = main([])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "AnotherKindOfMediaOrganiser\n"
    assert captured.err == ""
