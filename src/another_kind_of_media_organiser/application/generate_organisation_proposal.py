"""Application use case for generating an Organisation Proposal."""

from collections import Counter
from datetime import datetime
from pathlib import Path

from another_kind_of_media_organiser.domain.media import MediaEntry, ScanResult
from another_kind_of_media_organiser.domain.organisation import (
    OrganisationProposal,
    ProposedPlacement,
)


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


def resolve_media_creation_date(media_entry: MediaEntry) -> datetime:
    """Resolve Media Creation Date using modification time as a temporary fallback."""
    return media_entry.modification_date


def generate_organisation_proposal(scan_result: ScanResult) -> OrganisationProposal:
    """Build a deterministic, read-only plan for every recognised Media Entry."""
    proposed = []
    for entry in sorted(scan_result.media_entries, key=lambda item: item.path.as_posix()):
        creation_date = resolve_media_creation_date(entry)
        proposed.append(
            (entry, creation_date, _destination_for(entry, creation_date))
        )
    destination_counts = Counter(destination for _, _, destination in proposed)
    collision_destinations = tuple(
        sorted(
            (
                destination
                for destination, count in destination_counts.items()
                if count > 1
            ),
            key=Path.as_posix,
        )
    )
    placements = tuple(
        ProposedPlacement(
            source=entry,
            destination=destination,
            category=entry.category,
            media_creation_date=creation_date,
            has_collision=destination_counts[destination] > 1,
        )
        for entry, creation_date, destination in proposed
    )
    return OrganisationProposal(placements, collision_destinations)


def _destination_for(media_entry: MediaEntry, creation_date: datetime) -> Path:
    month = f"{creation_date.month:02d}-{_ENGLISH_MONTH_NAMES[creation_date.month]}"
    return Path(
        str(creation_date.year),
        month,
        media_entry.category.value,
        media_entry.path.name,
    )
