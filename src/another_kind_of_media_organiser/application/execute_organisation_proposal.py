"""Application use case for executing an accepted proposal by copying."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from another_kind_of_media_organiser.domain.organisation import OrganisationProposal
from another_kind_of_media_organiser.infrastructure.atomic_copy import copy_file
from another_kind_of_media_organiser.infrastructure.file_content import (
    delete_file,
    verify_identical,
)


class OrganisationExecutionMode(Enum):
    COPY = "copy"
    MOVE = "move"


@dataclass(frozen=True)
class OrganisationExecutionItem:
    source: Path
    destination: Path
    size: int


@dataclass(frozen=True)
class OrganisationExecutionPlan:
    source_root: Path
    destination_root: Path
    items: tuple[OrganisationExecutionItem, ...]
    name_conflict_files: int
    destination_is_inside_source: bool = False


@dataclass(frozen=True)
class OrganisationExecutionProgress:
    files_copied: int
    total_files: int
    bytes_copied: int
    files_verified: int = 0
    source_files_deleted: int = 0


@dataclass(frozen=True)
class OrganisationExecutionResult:
    files_copied: int
    total_files: int
    bytes_copied: int
    files_verified: int = 0
    source_files_deleted: int = 0


class UnsafeDestinationError(ValueError):
    pass


class DestinationConflictError(ValueError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"Destination file already exists: {path}")
        self.path = path


class OrganisationCopyError(OSError):
    def __init__(
        self,
        source: Path,
        destination: Path,
        files_copied: int,
        total_files: int,
        cause: Exception,
    ) -> None:
        super().__init__(str(cause))
        self.source = source
        self.destination = destination
        self.files_copied = files_copied
        self.total_files = total_files
        self.cause = cause


class OrganisationVerificationError(OrganisationCopyError):
    pass


class OrganisationDeletionError(OrganisationCopyError):
    def __init__(self, *args, files_verified: int, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.files_verified = files_verified


ProgressCallback = Callable[[OrganisationExecutionProgress], None]
CopyFile = Callable[[Path, Path, Callable[[int], None]], None]
VerifyFile = Callable[[Path, Path], None]
DeleteFile = Callable[[Path], None]


def prepare_organisation_execution(
    proposal: OrganisationProposal,
    source_root: Path,
    destination_root: Path,
) -> OrganisationExecutionPlan:
    """Validate the complete copy plan without creating destination content."""
    source = source_root.resolve(strict=True)
    destination = destination_root.resolve(strict=False)
    destination_is_inside_source = (
        destination_exclusion(source, destination) is not None
    )
    if _path_exists(destination) and not destination.is_dir():
        raise UnsafeDestinationError(
            f"Destination Collection is not a directory: {destination}"
        )

    items = []
    planned_destinations: set[Path] = set()
    for placement in proposal.placements:
        source_path = placement.source.path.resolve(strict=True)
        if not source_path.is_relative_to(source) or not source_path.is_file():
            raise UnsafeDestinationError(
                f"Media Entry is outside the source Media Collection: {source_path}"
            )

        relative_destination = placement.destination
        if relative_destination.is_absolute():
            raise UnsafeDestinationError(
                f"Proposed destination must be relative: {relative_destination}"
            )
        final_destination = (destination / relative_destination).resolve(strict=False)
        if (
            final_destination == destination
            or not final_destination.is_relative_to(destination)
        ):
            raise UnsafeDestinationError(
                f"Proposed destination escapes Destination Collection: "
                f"{relative_destination}"
            )
        _validate_destination_parents(final_destination, destination)
        if final_destination in planned_destinations:
            raise UnsafeDestinationError(
                f"Multiple placements target destination: {final_destination}"
            )
        if _path_exists(final_destination):
            raise DestinationConflictError(final_destination)
        planned_destinations.add(final_destination)
        items.append(
            OrganisationExecutionItem(
                source_path,
                final_destination,
                source_path.stat().st_size,
            )
        )

    return OrganisationExecutionPlan(
        source,
        destination,
        tuple(items),
        proposal.name_conflict_files,
        destination_is_inside_source,
    )


def execute_organisation_plan(
    plan: OrganisationExecutionPlan,
    progress_callback: ProgressCallback | None = None,
    *,
    mode: OrganisationExecutionMode = OrganisationExecutionMode.COPY,
    copy_file: CopyFile = copy_file,
    verify_file: VerifyFile = verify_identical,
    delete_file: DeleteFile = delete_file,
) -> OrganisationExecutionResult:
    """Execute each placement, optionally verifying before deleting its source."""
    files_copied = 0
    bytes_copied = 0
    files_verified = 0
    source_files_deleted = 0

    def report() -> None:
        if progress_callback is not None:
            progress_callback(
                OrganisationExecutionProgress(
                    files_copied,
                    len(plan.items),
                    bytes_copied,
                    files_verified,
                    source_files_deleted,
                )
            )

    def add_bytes(count: int) -> None:
        nonlocal bytes_copied
        bytes_copied += count
        report()

    report()
    for item in plan.items:
        try:
            copy_file(item.source, item.destination, add_bytes)
        except KeyboardInterrupt:
            raise
        except Exception as error:
            raise OrganisationCopyError(
                item.source,
                item.destination,
                files_copied,
                len(plan.items),
                error,
            ) from error
        files_copied += 1
        report()
        if mode is OrganisationExecutionMode.MOVE:
            try:
                verify_file(item.source, item.destination)
            except KeyboardInterrupt:
                raise
            except Exception as error:
                raise OrganisationVerificationError(
                    item.source,
                    item.destination,
                    files_copied,
                    len(plan.items),
                    error,
                ) from error
            files_verified += 1
            report()
            try:
                delete_file(item.source)
            except KeyboardInterrupt:
                raise
            except Exception as error:
                raise OrganisationDeletionError(
                    item.source,
                    item.destination,
                    files_copied,
                    len(plan.items),
                    error,
                    files_verified=files_verified,
                ) from error
            source_files_deleted += 1
            report()

    return OrganisationExecutionResult(
        files_copied,
        len(plan.items),
        bytes_copied,
        files_verified,
        source_files_deleted,
    )


def destination_exclusion(source_root: Path, destination_root: Path) -> Path | None:
    """Return the relative destination subtree to exclude, rejecting unsafe roots."""
    source = source_root.resolve(strict=False)
    destination = destination_root.resolve(strict=False)
    if source == destination:
        raise UnsafeDestinationError("Source and destination must be different")
    if destination.is_relative_to(source):
        return destination.relative_to(source)
    if source.is_relative_to(destination):
        raise UnsafeDestinationError(
            "Source Media Collection cannot be inside destination"
        )
    return None


def _validate_destination_parents(path: Path, root: Path) -> None:
    parent = path.parent
    while parent != root:
        if _path_exists(parent) and not parent.is_dir():
            raise UnsafeDestinationError(
                f"Destination path cannot be represented safely: {parent}"
            )
        parent = parent.parent


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()
