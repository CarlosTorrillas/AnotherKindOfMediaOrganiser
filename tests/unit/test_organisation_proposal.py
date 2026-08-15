from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
    resolve_media_creation_date,
)
from another_kind_of_media_organiser.domain.media import (
    MediaCategory,
    MediaEntry,
    ScanResult,
)


def entry(path: str, category: MediaCategory, date: datetime) -> MediaEntry:
    return MediaEntry(Path(path), category, date)


def scan_result(
    entries: tuple[MediaEntry, ...], unsupported_files: int = 0
) -> ScanResult:
    category_counts = Counter(item.category for item in entries)
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


def test_proposes_year_month_category_and_original_filename() -> None:
    january = datetime(2024, 1, 5, 12, tzinfo=timezone.utc)
    december = datetime(2023, 12, 9, 8, tzinfo=timezone.utc)
    image = entry("camera/IMG_001.JPG", MediaCategory.IMAGE, january)
    audio = entry("phone/Voice Note.OpUs", MediaCategory.AUDIO, december)

    proposal = generate_organisation_proposal(scan_result((image, audio)))

    assert [(placement.source, placement.destination) for placement in proposal.placements] == [
        (image, Path("2024/01-January/IMAGE/IMG_001.JPG")),
        (audio, Path("2023/12-December/AUDIO/Voice Note.OpUs")),
    ]
    assert proposal.placements[0].media_creation_date == january
    assert proposal.placements[1].media_creation_date == december


def test_excludes_unsupported_files_from_proposal() -> None:
    media = entry(
        "photo.jpg", MediaCategory.IMAGE, datetime(2024, 2, 1, tzinfo=timezone.utc)
    )

    proposal = generate_organisation_proposal(
        scan_result((media,), unsupported_files=3)
    )

    assert len(proposal.placements) == 1
    assert proposal.placements[0].source == media


def test_reports_collisions_without_discarding_or_renaming_entries() -> None:
    date = datetime(2024, 8, 1, tzinfo=timezone.utc)
    first = entry("camera-a/IMG_001.jpg", MediaCategory.IMAGE, date)
    second = entry("camera-b/IMG_001.jpg", MediaCategory.IMAGE, date)

    proposal = generate_organisation_proposal(scan_result((second, first)))

    expected_destination = Path("2024/08-August/IMAGE/IMG_001.jpg")
    assert tuple(placement.source for placement in proposal.placements) == (first, second)
    assert tuple(placement.destination for placement in proposal.placements) == (
        expected_destination,
        expected_destination,
    )
    assert proposal.collision_destinations == (expected_destination,)
    assert all(placement.has_collision for placement in proposal.placements)


def test_proposal_is_deterministic_for_the_same_entries_in_any_input_order() -> None:
    date = datetime(2024, 3, 1, tzinfo=timezone.utc)
    first = entry("b/video.mp4", MediaCategory.VIDEO, date)
    second = entry("a/photo.jpg", MediaCategory.IMAGE, date)

    forward = generate_organisation_proposal(scan_result((first, second)))
    reverse = generate_organisation_proposal(scan_result((second, first)))

    assert forward == reverse


def test_filesystem_modification_date_temporarily_resolves_media_creation_date() -> None:
    modification_date = datetime(2022, 7, 4, 9, tzinfo=timezone.utc)
    media = entry("photo.jpg", MediaCategory.IMAGE, modification_date)

    assert resolve_media_creation_date(media) == modification_date

