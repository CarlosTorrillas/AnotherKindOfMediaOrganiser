"""Domain concepts for planning media organisation."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from another_kind_of_media_organiser.domain.media import MediaCategory, MediaEntry


@dataclass(frozen=True)
class ProposedPlacement:
    """One recognised media entry's placement in an organisation proposal."""

    source: MediaEntry
    destination: Path
    category: MediaCategory
    media_creation_date: datetime
    has_collision: bool


@dataclass(frozen=True)
class OrganisationProposal:
    """A read-only plan for organising recognised media."""

    placements: tuple[ProposedPlacement, ...]
    collision_destinations: tuple[Path, ...]

