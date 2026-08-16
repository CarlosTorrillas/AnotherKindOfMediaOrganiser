"""Application use case for generating an Organisation Proposal."""

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from another_kind_of_media_organiser.domain.media import MediaEntry, ScanResult
from another_kind_of_media_organiser.domain.organisation import (
    OrganisationProposal,
    PlacementClassification,
    ProposedPlacement,
)
from another_kind_of_media_organiser.infrastructure import file_content
from another_kind_of_media_organiser.infrastructure.digest_cache import (
    SqliteDigestCache,
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


@dataclass(frozen=True)
class CollisionClassificationProgress:
    """Observable progress through non-canonical collision candidates."""

    processed_candidates: int
    total_candidates: int
    exact_duplicate_files: int
    potential_conflict_files: int
    unverified_conflict_files: int
    bytes_hashed: int
    cache_hits: int = 0


ProgressCallback = Callable[[CollisionClassificationProgress], None]


class _ProgressTracker:
    def __init__(self, total_candidates: int, callback: ProgressCallback) -> None:
        self.total_candidates = total_candidates
        self.callback = callback
        self.processed_candidates = 0
        self.bytes_hashed = 0
        self.cache_hits = 0
        self.counts: Counter[PlacementClassification] = Counter()

    def report(self) -> None:
        self.callback(
            CollisionClassificationProgress(
                self.processed_candidates,
                self.total_candidates,
                self.counts[PlacementClassification.EXACT_DUPLICATE],
                self.counts[PlacementClassification.POTENTIAL_CONFLICT],
                self.counts[PlacementClassification.UNVERIFIED_CONFLICT],
                self.bytes_hashed,
                self.cache_hits,
            )
        )

    def add_hashed_bytes(self, count: int) -> None:
        self.bytes_hashed += count
        self.report()

    def complete(self, classification: PlacementClassification) -> None:
        self.counts[classification] += 1
        self.processed_candidates += 1
        self.report()

    def cache_hit(self) -> None:
        self.cache_hits += 1
        self.report()


def resolve_media_creation_date(media_entry: MediaEntry) -> datetime:
    """Resolve Media Creation Date using modification time as a temporary fallback."""
    return media_entry.modification_date


def generate_organisation_proposal(
    scan_result: ScanResult,
    progress_callback: ProgressCallback | None = None,
    *,
    digest_cache: SqliteDigestCache | None = None,
) -> OrganisationProposal:
    """Build and classify a deterministic, read-only organisation plan."""
    proposed = []
    ordered_entries = sorted(
        scan_result.media_entries, key=lambda item: item.path.as_posix()
    )
    for entry in ordered_entries:
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
    total_candidates = sum(
        len(groups[destination]) - 1 for destination in collision_destinations
    )
    progress = (
        _ProgressTracker(total_candidates, progress_callback)
        if progress_callback is not None and total_candidates > 0
        else None
    )
    if progress is not None:
        progress.report()

    run_digest_cache: dict[Path, str | None] = {}
    size_cache: dict[Path, int | None] = {}
    review_counts: Counter[tuple[Path, PlacementClassification]] = Counter()
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
            size_cache,
            run_digest_cache,
            digest_cache,
            progress.add_hashed_bytes if progress is not None else None,
            progress.cache_hit if progress is not None else None,
        )
        if progress is not None:
            progress.complete(classification)
        review_key = (normal_destination, classification)
        review_counts[review_key] += 1
        destination = _review_destination(
            normal_destination,
            classification,
            review_counts[review_key],
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
    size_cache: dict[Path, int | None],
    digest_cache: dict[Path, str | None],
    digest_cache_store: SqliteDigestCache | None,
    on_bytes_hashed: Callable[[int], None] | None = None,
    on_cache_hit: Callable[[], None] | None = None,
) -> PlacementClassification:
    canonical_size = _size(canonical_path, size_cache)
    candidate_size = _size(candidate_path, size_cache)
    if canonical_size is None or candidate_size is None:
        return PlacementClassification.UNVERIFIED_CONFLICT

    if canonical_size != candidate_size:
        return PlacementClassification.POTENTIAL_CONFLICT

    canonical_digest = _digest(
        canonical_path,
        digest_cache,
        digest_cache_store,
        on_bytes_hashed,
        on_cache_hit,
    )
    if canonical_digest is None:
        return PlacementClassification.UNVERIFIED_CONFLICT
    candidate_digest = _digest(
        candidate_path,
        digest_cache,
        digest_cache_store,
        on_bytes_hashed,
        on_cache_hit,
    )
    if candidate_digest is None:
        return PlacementClassification.UNVERIFIED_CONFLICT
    if candidate_digest == canonical_digest:
        return PlacementClassification.EXACT_DUPLICATE
    return PlacementClassification.POTENTIAL_CONFLICT


def _size(path: Path, cache: dict[Path, int | None]) -> int | None:
    if path not in cache:
        try:
            cache[path] = file_content.file_size(path)
        except OSError:
            cache[path] = None
    return cache[path]


def _digest(
    path: Path,
    cache: dict[Path, str | None],
    persistent_cache: SqliteDigestCache | None,
    on_bytes_hashed: Callable[[int], None] | None = None,
    on_cache_hit: Callable[[], None] | None = None,
) -> str | None:
    if path not in cache:
        try:
            metadata_before = path.stat()
            if persistent_cache is not None:
                cached_digest = persistent_cache.lookup(
                    path, metadata_before.st_size, metadata_before.st_mtime_ns
                )
                if cached_digest is not None:
                    metadata_after_lookup = path.stat()
                    cache_entry_still_valid = (
                        metadata_after_lookup.st_size == metadata_before.st_size
                        and metadata_after_lookup.st_mtime_ns
                        == metadata_before.st_mtime_ns
                    )
                    if not cache_entry_still_valid:
                        cache[path] = None
                        return cache[path]
                    cache[path] = cached_digest
                    if on_cache_hit is not None:
                        on_cache_hit()
                    return cache[path]
            if on_bytes_hashed is None:
                cache[path] = file_content.sha256_digest(path)
            else:
                cache[path] = file_content.sha256_digest(
                    path, on_bytes_read=on_bytes_hashed
                )
            metadata_after = path.stat()
            unchanged = (
                metadata_after.st_size == metadata_before.st_size
                and metadata_after.st_mtime_ns == metadata_before.st_mtime_ns
            )
            if not unchanged:
                cache[path] = None
            elif persistent_cache is not None and cache[path] is not None:
                persistent_cache.store(
                    path,
                    metadata_after.st_size,
                    metadata_after.st_mtime_ns,
                    cache[path],
                )
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
