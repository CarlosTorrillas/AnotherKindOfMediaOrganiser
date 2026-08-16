import tempfile
from pathlib import Path

from behave import given, then, when

from another_kind_of_media_organiser.application.execute_organisation_proposal import (
    OrganisationDeletionError,
    OrganisationExecutionMode,
    OrganisationVerificationError,
    execute_organisation_plan,
    prepare_organisation_execution,
)
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)


def _setup(context, files: dict[str, bytes]) -> None:
    temporary = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary.cleanup)
    context.source = Path(temporary.name) / "source"
    context.destination = Path(temporary.name) / "destination"
    for relative, content in files.items():
        path = context.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    context.originals = {
        path.resolve(): path.read_bytes()
        for path in context.source.rglob("*")
        if path.is_file()
    }
    context.proposal = generate_organisation_proposal(
        scan_media_collection(context.source)
    )
    context.plan = prepare_organisation_execution(
        context.proposal, context.source, context.destination
    )


@given("a valid Organisation Proposal for moving")
def given_move_proposal(context) -> None:
    _setup(context, {"photo.jpg": b"valuable"})


@given("a MOVE proposal containing Name Conflicts")
def given_move_conflicts(context) -> None:
    _setup(context, {"a/IMG_001.jpg": b"one", "b/IMG_001.jpg": b"two"})


@when("the user accepts MOVE Organisation Execution")
def when_move_accepted(context) -> None:
    context.events = []

    def verify(source, destination):
        assert source.read_bytes() == destination.read_bytes()
        context.events.append(("verified", source))

    def delete(source):
        assert ("verified", source) in context.events
        context.events.append(("deleted", source))
        source.unlink()

    context.result = execute_organisation_plan(
        context.plan,
        mode=OrganisationExecutionMode.MOVE,
        verify_file=verify,
        delete_file=delete,
    )


@when("MOVE copying fails")
def when_move_copy_fails(context) -> None:
    try:
        execute_organisation_plan(
            context.plan,
            mode=OrganisationExecutionMode.MOVE,
            copy_file=lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
        )
    except OSError:
        pass


@when("MOVE verification fails")
def when_move_verification_fails(context) -> None:
    try:
        execute_organisation_plan(
            context.plan,
            mode=OrganisationExecutionMode.MOVE,
            verify_file=lambda *_args: (_ for _ in ()).throw(ValueError("mismatch")),
        )
    except OrganisationVerificationError:
        pass


@when("MOVE source deletion fails")
def when_move_deletion_fails(context) -> None:
    try:
        execute_organisation_plan(
            context.plan,
            mode=OrganisationExecutionMode.MOVE,
            delete_file=lambda _path: (_ for _ in ()).throw(OSError("denied")),
        )
    except OrganisationDeletionError:
        pass


@when("MOVE is cancelled during verification")
def when_move_cancelled(context) -> None:
    try:
        execute_organisation_plan(
            context.plan,
            mode=OrganisationExecutionMode.MOVE,
            verify_file=lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
    except KeyboardInterrupt:
        pass


@then("each destination contains the original source content")
def then_destination_matches(context) -> None:
    for item in context.plan.items:
        assert item.destination.read_bytes() == context.originals[item.source]


@then("each source is deleted only after its destination is verified")
def then_verified_before_deleted(context) -> None:
    assert context.result.source_files_deleted == len(context.plan.items)
    for item in context.plan.items:
        assert context.events.index(("verified", item.source)) < context.events.index(
            ("deleted", item.source)
        )


@then("the source media remains")
@then("the current source media remains")
def then_source_remains(context) -> None:
    assert all(path.read_bytes() == content for path, content in context.originals.items())


@then("the verified destination remains")
def then_verified_destination_remains(context) -> None:
    then_destination_matches(context)


@then("canonical and nameConflicts placements exist at their proposed destinations")
def then_conflicts_moved(context) -> None:
    then_destination_matches(context)
    assert any(item.destination.parent.name == "nameConflicts" for item in context.plan.items)
