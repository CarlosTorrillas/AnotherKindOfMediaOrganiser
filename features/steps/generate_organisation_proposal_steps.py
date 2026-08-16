import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from behave import given, then, when

from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.media import (
    MediaCategory,
    MediaEntry,
    ScanResult,
)


def _entry(path: str, category: MediaCategory, date: str) -> MediaEntry:
    creation_date = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    return MediaEntry(Path(path), category, creation_date)


def _scan_result(
    entries: tuple[MediaEntry, ...], unsupported_files: int = 0
) -> ScanResult:
    category_counts = Counter(entry.category for entry in entries)
    return ScanResult(
        total_files=len(entries) + unsupported_files,
        unsupported_files=unsupported_files,
        directories_scanned=1,
        counts_by_category={
            category: category_counts[category]
            for category in MediaCategory
            if category is not MediaCategory.UNSUPPORTED
        },
        recognised_extension_counts={},
        unsupported_extension_counts={".txt": unsupported_files}
        if unsupported_files
        else {},
        media_entries=entries,
    )


@given("recognised Media Entries with different Media Creation Dates")
def step_entries_with_dates(context) -> None:
    context.scan_result = _scan_result(
        (
            _entry("camera/january.jpg", MediaCategory.IMAGE, "2024-01-03"),
            _entry("phone/august.mp4", MediaCategory.VIDEO, "2023-08-19"),
        )
    )


@given("recognised IMAGE, RAW, VIDEO and AUDIO Media Entries")
def step_entries_in_all_categories(context) -> None:
    context.scan_result = _scan_result(
        tuple(
            _entry(f"source/{category.value.lower()}{extension}", category, "2024-04-02")
            for category, extension in (
                (MediaCategory.IMAGE, ".jpg"),
                (MediaCategory.RAW, ".dng"),
                (MediaCategory.VIDEO, ".mp4"),
                (MediaCategory.AUDIO, ".opus"),
            )
        )
    )


@given("recognised Media Entries with distinct original filenames")
def step_entries_with_original_filenames(context) -> None:
    context.scan_result = _scan_result(
        (
            _entry("camera/IMG_0001.JPG", MediaCategory.IMAGE, "2024-05-10"),
            _entry("phone/My Recording.OpUs", MediaCategory.AUDIO, "2024-05-10"),
        )
    )


@given("a Scan Result containing Recognised Media and Unsupported Files")
def step_result_with_unsupported_files(context) -> None:
    context.scan_result = _scan_result(
        (_entry("photo.jpg", MediaCategory.IMAGE, "2024-06-15"),),
        unsupported_files=2,
    )


@given("multiple Media Entries compete for the same normal proposed destination")
def step_multiple_colliding_entries(context) -> None:
    context.scan_result = _scan_result(
        (
            _entry("camera-c/IMG_001.jpg", MediaCategory.IMAGE, "2024-08-01"),
            _entry("camera-a/IMG_001.jpg", MediaCategory.IMAGE, "2024-08-20"),
            _entry("camera-b/IMG_001.jpg", MediaCategory.IMAGE, "2024-08-10"),
        )
    )


@given("a proposed destination collision whose file content cannot be read")
def step_unreadable_colliding_entries(context) -> None:
    context.scan_result = _scan_result(
        (
            _entry("camera-a/IMG_001.jpg", MediaCategory.IMAGE, "2024-08-01"),
            _entry("camera-b/IMG_001.jpg", MediaCategory.IMAGE, "2024-08-20"),
        )
    )


@given("a Media Collection for proposal generation")
def step_media_collection_for_proposal(context) -> None:
    temporary_directory = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary_directory.cleanup)
    context.collection = Path(temporary_directory.name) / "collection"
    context.collection.mkdir()
    media_path = context.collection / "photo.jpg"
    media_path.write_bytes(b"valuable original")
    os.utime(media_path, (1_704_067_200, 1_704_067_200))
    unsupported_path = context.collection / "notes.txt"
    unsupported_path.write_bytes(b"notes")
    context.paths_before = sorted(
        path.relative_to(context.collection) for path in context.collection.rglob("*")
    )
    context.state_before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in (media_path, unsupported_path)
    }


@when("the user generates an Organisation Proposal")
def step_generate_proposal(context) -> None:
    context.proposal = generate_organisation_proposal(context.scan_result)


@when("the user generates an Organisation Proposal from the Media Collection")
def step_scan_and_generate_proposal(context) -> None:
    context.proposal = generate_organisation_proposal(
        scan_media_collection(context.collection)
    )


@then("each Media Entry is proposed under its corresponding year and month")
def step_destinations_use_year_and_month(context) -> None:
    assert {placement.destination for placement in context.proposal.placements} == {
        Path("2024/01-January/IMAGE/january.jpg"),
        Path("2023/08-August/VIDEO/august.mp4"),
    }


@then("each proposed destination includes its Media Category")
def step_destinations_use_category(context) -> None:
    assert {
        placement.destination.parts[-2] for placement in context.proposal.placements
    } == {"IMAGE", "RAW", "VIDEO", "AUDIO"}


@then("each proposed destination preserves its original filename exactly")
def step_destinations_preserve_filename(context) -> None:
    assert {
        placement.destination.name for placement in context.proposal.placements
    } == {"IMG_0001.JPG", "My Recording.OpUs"}


@then("only Recognised Media receives proposed destinations")
def step_only_recognised_media_is_proposed(context) -> None:
    assert len(context.proposal.placements) == context.scan_result.media_files == 1


@then("one receives the deterministic canonical destination")
def step_deterministic_canonical_destination(context) -> None:
    assert context.proposal.placements[0].source.path == Path(
        "camera-a/IMG_001.jpg"
    )
    assert context.proposal.placements[0].destination == Path(
        "2024/08-August/IMAGE/IMG_001.jpg"
    )


@then(
    "every remaining entry receives a unique deterministic nameConflicts destination"
)
def step_deterministic_name_conflict_destinations(context) -> None:
    assert [
        placement.destination for placement in context.proposal.placements[1:]
    ] == [
        Path("2024/08-August/IMAGE/nameConflicts/IMG_001__conflict1.jpg"),
        Path("2024/08-August/IMAGE/nameConflicts/IMG_001__conflict2.jpg"),
    ]


@then("the Name Conflict is reported without reading file content")
def step_name_conflict_without_content(context) -> None:
    assert len(context.proposal.placements) == 2
    assert context.proposal.placements[1].destination.parent.name == "nameConflicts"


@then("the Media Collection remains unchanged")
def step_collection_unchanged(context) -> None:
    paths_after = sorted(
        path.relative_to(context.collection) for path in context.collection.rglob("*")
    )
    state_after = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in context.state_before
    }
    assert paths_after == context.paths_before
    assert state_after == context.state_before
