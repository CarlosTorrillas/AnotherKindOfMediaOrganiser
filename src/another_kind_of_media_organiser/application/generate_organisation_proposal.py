"""Application use case for generating an Organisation Proposal."""

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from another_kind_of_media_organiser.domain.media import MediaEntry, ScanResult
from another_kind_of_media_organiser.domain.organisation import (
    OrganisationProposal,
    PlacementClassification,
    ProposedPlacement,
)
from another_kind_of_media_organiser.infrastructure import file_content


_ENGLISH_MONTH_NAMES = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_REVIEW_DETAILS = {
    PlacementClassification.EXACT_DUPLICATE: ("exactDuplicates", "dup"),
    PlacementClassification.POTENTIAL_CONFLICT: (
        "potentialConflicts",
        "conflict",
    ),
    PlacementClassification.UNVERIFIED_CONFLICT: (
        "unverifiedConflicts",
        "unverified",
    ),
}


def resolve_media_creation_date(media_entry: MediaEntry) -> datetime:
    """Resolve Media Creation Date using modification time as a temporary fallback."""
    return media_entry.modification_date


def generate_organisation_proposal(scan_result: ScanResult) -> OrganisationProposal:
    """Build and classify a deterministic, read-only organisation plan."""
    proposed = []
    for entry in sorted(scan_result.media_entries, key=lambda item: item.path.as_posix()):
        creation_date = resolve_media_creation_date(entry)
        proposed.append(
            (entry, creation_date, _destination_for(entry, creation_date))
        )

    groups = defaultdict(list)
    for item in proposed:
        groups[item[2]].append(item)
    collision_destinations = tuple(
        sorted(
            (destination for destination, items in groups.items() if len(items) > 1),
            key=Path.as_posix,
        )
    )

    digest_cache: dict[Path, str | None] = {}
    placements = []
    for entry, creation_date, normal_destination in proposed:
        group = groups[normal_destination]
        if len(group) == 1:
            placements.append(
                _placement(
                    entry,
                    creation_date,
                    normal_destination,
                    normal_destination,
                    PlacementClassification.NORMAL,
                    has_collision=False,
                )
            )
            continue

        if entry is group[0][0]:
            placements.append(
                _placement(
                    entry,
                    creation_date,
                    normal_destination,
                    normal_destination,
                    PlacementClassification.CANONICAL,
                    has_collision=True,
                )
            )
            continue

        classification = _classify_against_canonical(
            group[0][0].path,
            entry.path,
            digest_cache,
        )
        earlier_same_classification = sum(
            placement.normal_destination == normal_destination
            and placement.classification is classification
            for placement in placements
        )
        destination = _review_destination(
            normal_destination,
            classification,
            earlier_same_classification + 1,
        )
        placements.append(
            _placement(
                entry,
                creation_date,
                destination,
                normal_destination,
                classification,
                has_collision=True,
            )
        )

    return OrganisationProposal(tuple(placements), collision_destinations)


def _classify_against_canonical(
    canonical_path: Path,
    candidate_path: Path,
    digest_cache: dict[Path, str | None],
) -> PlacementClassification:
    try:
        canonical_size = file_content.file_size(canonical_path)
        candidate_size = file_content.file_size(candidate_path)
    except OSError:
        return PlacementClassification.UNVERIFIED_CONFLICT

    if canonical_size != candidate_size:
        return PlacementClassification.POTENTIAL_CONFLICT

    canonical_digest = _digest(canonical_path, digest_cache)
    if canonical_digest is None:
        return PlacementClassification.UNVERIFIED_CONFLICT
    candidate_digest = _digest(candidate_path, digest_cache)
    if candidate_digest is None:
        return PlacementClassification.UNVERIFIED_CONFLICT
    if candidate_digest == canonical_digest:
        return PlacementClassification.EXACT_DUPLICATE
    return PlacementClassification.POTENTIAL_CONFLICT


def _digest(path: Path, cache: dict[Path, str | None]) -> str | None:
    if path not in cache:
        try:
            cache[path] = file_content.sha256_digest(path)
        except OSError:
            cache[path] = None
    return cache[path]


def _review_destination(
    normal_destination: Path,
    classification: PlacementClassification,
    number: int,
) -> Path:
    folder, marker = _REVIEW_DETAILS[classification]
    review_filename = (
        f"{normal_destination.stem}__{marker}{number}{normal_destination.suffix}"
    )
    return normal_destination.parent / folder / review_filename


def _placement(
    entry: MediaEntry,
    creation_date: datetime,
    destination: Path,
    normal_destination: Path,
    classification: PlacementClassification,
    *,
    has_collision: bool,
) -> ProposedPlacement:
    return ProposedPlacement(
        source=entry,
        destination=destination,
        normal_destination=normal_destination,
        category=entry.category,
        media_creation_date=creation_date,
        has_collision=has_collision,
        classification=classification,
    )


def _destination_for(media_entry: MediaEntry, creation_date: datetime) -> Path:
    month = f"{creation_date.month:02d}-{_ENGLISH_MONTH_NAMES[creation_date.month]}"
    return Path(
        str(creation_date.year),
        month,
        media_entry.category.value,
        media_entry.path.name,
    )
