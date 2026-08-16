"""Domain concepts for planning media organisation."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from another_kind_of_media_organiser.domain.media import MediaCategory, MediaEntry


class PlacementClassification(Enum):
    """The role of a placement after collision classification."""

    NORMAL = "NORMAL"
    CANONICAL = "CANONICAL"
    NAME_CONFLICT = "NAME_CONFLICT"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    POTENTIAL_CONFLICT = "POTENTIAL_CONFLICT"
    UNVERIFIED_CONFLICT = "UNVERIFIED_CONFLICT"


@dataclass(frozen=True)
class ProposedPlacement:
    """One recognised media entry's placement in an organisation proposal."""

    source: MediaEntry
    destination: Path
    normal_destination: Path
    category: MediaCategory
    media_creation_date: datetime
    has_collision: bool
    classification: PlacementClassification


@dataclass(frozen=True)
class OrganisationProposal:
    """A read-only plan for organising recognised media."""

    placements: tuple[ProposedPlacement, ...]
    collision_destinations: tuple[Path, ...]

    @property
    def name_conflict_files(self) -> int:
        return self._count(PlacementClassification.NAME_CONFLICT)

    @property
    def exact_duplicate_files(self) -> int:
        return self._count(PlacementClassification.EXACT_DUPLICATE)

    @property
    def potential_conflict_files(self) -> int:
        return self._count(PlacementClassification.POTENTIAL_CONFLICT)

    @property
    def unverified_conflict_files(self) -> int:
        return self._count(PlacementClassification.UNVERIFIED_CONFLICT)

    def _count(self, classification: PlacementClassification) -> int:
        return sum(
            placement.classification is classification
            for placement in self.placements
        )
