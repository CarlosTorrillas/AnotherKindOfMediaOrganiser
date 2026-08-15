from another_kind_of_media_organiser.cli import main


def test_cli_identifies_application(capsys) -> None:
    main()

    captured = capsys.readouterr()

    assert captured.out == "AnotherKindOfMediaOrganiser\n"
    assert captured.err == ""

