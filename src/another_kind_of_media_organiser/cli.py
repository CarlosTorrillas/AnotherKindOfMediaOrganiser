"""Command-line interface for AnotherKindOfMediaOrganiser."""

import argparse
import calendar
import sqlite3
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from math import ceil
from pathlib import Path
from typing import TextIO

from another_kind_of_media_organiser.application.execute_organisation_proposal import (
    DestinationConflictError,
    OrganisationCopyError,
    OrganisationDeletionError,
    OrganisationExecutionMode,
    OrganisationExecutionPlan,
    OrganisationExecutionProgress,
    OrganisationVerificationError,
    UnsafeDestinationError,
    execute_organisation_plan,
    prepare_organisation_execution,
)
from another_kind_of_media_organiser.application.capacity_preflight import (
    DEFAULT_SAFETY_RESERVE_BYTES,
    CapacityPreflight,
    plan_organisation_capacity,
)
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    CollisionClassificationProgress,
    generate_content_verified_organisation_proposal,
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.media import MediaCategory, ScanResult
from another_kind_of_media_organiser.domain.organisation import (
    OrganisationProposal,
    PlacementClassification,
)
from another_kind_of_media_organiser.infrastructure.digest_cache import (
    SqliteDigestCache,
    default_digest_cache_path,
)
from another_kind_of_media_organiser.infrastructure.filesystem_capacity import (
    available_capacity,
)


_NO_EXTENSION_LABEL = "[no extension]"
_MAX_COLLISION_EXAMPLES = 10
_MAX_INACCESSIBLE_EXAMPLES = 10
_INTERACTIVE_UPDATE_INTERVAL_SECONDS = 0.2
_NON_INTERACTIVE_BYTE_MILESTONE = 1024 * 1024 * 1024


class _CollisionProgressReporter:
    def __init__(
        self,
        output: TextIO = sys.stderr,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.output = output
        self.clock = clock
        self.interactive = output.isatty()
        self.last_update = float("-inf")
        self.max_line_length = 0
        self.next_candidate_milestone = 0
        self.next_byte_milestone = _NON_INTERACTIVE_BYTE_MILESTONE
        self.has_output = False

    def __call__(self, progress: CollisionClassificationProgress) -> None:
        if self.interactive:
            now = self.clock()
            is_boundary = progress.processed_candidates in {
                0,
                progress.total_candidates,
            }
            update_due = (
                now - self.last_update >= _INTERACTIVE_UPDATE_INTERVAL_SECONDS
            )
            if not is_boundary and not update_due:
                return
            self.last_update = now
            self._write_interactive(progress)
            return

        if not self.has_output:
            self.next_candidate_milestone = max(
                1, ceil(progress.total_candidates / 20)
            )
            self._write_line(progress)
            return

        reached_candidate_milestone = (
            progress.processed_candidates >= self.next_candidate_milestone
        )
        reached_byte_milestone = progress.bytes_hashed >= self.next_byte_milestone
        completed = progress.processed_candidates == progress.total_candidates
        if reached_candidate_milestone or reached_byte_milestone or completed:
            self._write_line(progress)
            while self.next_candidate_milestone <= progress.processed_candidates:
                self.next_candidate_milestone += max(
                    1, ceil(progress.total_candidates / 20)
                )
            while self.next_byte_milestone <= progress.bytes_hashed:
                self.next_byte_milestone += _NON_INTERACTIVE_BYTE_MILESTONE

    def cancel(self) -> None:
        if self.interactive and self.has_output:
            print(file=self.output)

    def _write_interactive(self, progress: CollisionClassificationProgress) -> None:
        line = self._format(progress, "Verifying destination collisions")
        self.max_line_length = max(self.max_line_length, len(line))
        completed = progress.processed_candidates == progress.total_candidates
        ending = "\n" if completed else ""
        print(
            f"\r{line.ljust(self.max_line_length)}",
            end=ending,
            file=self.output,
            flush=True,
        )
        self.has_output = True

    def _write_line(self, progress: CollisionClassificationProgress) -> None:
        print(
            self._format(progress, "Collision verification"),
            file=self.output,
            flush=True,
        )
        self.has_output = True

    @staticmethod
    def _format(progress: CollisionClassificationProgress, label: str) -> str:
        percentage = progress.processed_candidates * 100 // progress.total_candidates
        return (
            f"{label}: {progress.processed_candidates}/"
            f"{progress.total_candidates} files "
            f"({percentage}%) | exact {progress.exact_duplicate_files} | "
            f"potential {progress.potential_conflict_files} | "
            f"unverified {progress.unverified_conflict_files} | "
            f"cache hits {progress.cache_hits} | "
            f"hashed this run {_format_bytes(progress.bytes_hashed)}"
        )


class _CopyProgressReporter:
    def __init__(self, total_files: int, output: TextIO = sys.stderr, *, move: bool = False) -> None:
        self.output = output
        self.interactive = output.isatty()
        self.last_progress = OrganisationExecutionProgress(0, total_files, 0)
        self.file_milestone = max(1, ceil(total_files / 20))
        self.next_file_milestone = 0
        self.next_byte_milestone = _NON_INTERACTIVE_BYTE_MILESTONE
        self.max_line_length = 0
        self.move = move

    def __call__(self, progress: OrganisationExecutionProgress) -> None:
        self.last_progress = progress
        if self.move:
            line = (
                f"Moving media: Files {progress.files_copied} / {progress.total_files} | "
                f"Moved {_format_bytes(progress.bytes_copied)} | "
                f"Verified {progress.files_verified} | "
                f"Source files deleted {progress.source_files_deleted}"
            )
        else:
            line = (
                f"Copying media: Files {progress.files_copied} / "
                f"{progress.total_files} | Copied {_format_bytes(progress.bytes_copied)}"
            )
        if self.interactive:
            self.max_line_length = max(self.max_line_length, len(line))
            ending = "\n" if progress.files_copied == progress.total_files else ""
            print(
                f"\r{line.ljust(self.max_line_length)}",
                end=ending,
                file=self.output,
                flush=True,
            )
            return

        reached_byte_milestone = progress.bytes_copied >= self.next_byte_milestone
        reached_file_milestone = (
            progress.files_copied >= self.next_file_milestone
        )
        move_completed = (
            self.move
            and progress.source_files_deleted == progress.total_files
        )
        if reached_file_milestone or reached_byte_milestone or move_completed:
            print(line, file=self.output, flush=True)
            while self.next_file_milestone <= progress.files_copied:
                self.next_file_milestone += self.file_milestone
            while self.next_byte_milestone <= progress.bytes_copied:
                self.next_byte_milestone += _NON_INTERACTIVE_BYTE_MILESTONE

    def cancel(self) -> None:
        if self.interactive:
            print(file=self.output)


def _format_bytes(count: int) -> str:
    value = float(count)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="media-organiser")
    subcommands = parser.add_subparsers(dest="command")
    scan_parser = subcommands.add_parser("scan", help="scan a media collection")
    scan_parser.add_argument("directory", type=Path)
    _add_exclusions(scan_parser)
    propose_parser = subcommands.add_parser(
        "propose", help="quickly propose how to organise a media collection"
    )
    propose_parser.add_argument("directory", type=Path)
    _add_exclusions(propose_parser)
    verify_parser = subcommands.add_parser(
        "verify-collisions",
        help="deeply verify the content of destination collisions",
    )
    verify_parser.add_argument("directory", type=Path)
    _add_exclusions(verify_parser)
    organise_parser = subcommands.add_parser(
        "organise",
        help="copy an accepted lightweight proposal to a separate destination",
    )
    organise_parser.add_argument("directory", type=Path, metavar="SOURCE")
    _add_exclusions(organise_parser)
    organise_parser.add_argument(
        "--destination", required=True, type=Path, metavar="DESTINATION"
    )
    organise_parser.add_argument(
        "--move",
        action="store_true",
        help="copy, verify, then delete each source file (default: copy)",
    )
    return parser


def _add_exclusions(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="exclude a path relative to the scan root (repeatable)",
    )


def _print_summary(result: ScanResult) -> None:
    print(f"Files scanned: {result.total_files}")
    print(f"Media files: {result.media_files}")
    print(f"Images: {result.counts_by_category[MediaCategory.IMAGE]}")
    print(f"RAW: {result.counts_by_category[MediaCategory.RAW]}")
    print(f"Videos: {result.counts_by_category[MediaCategory.VIDEO]}")
    print(f"Audio: {result.counts_by_category[MediaCategory.AUDIO]}")
    print(f"Unsupported: {result.unsupported_files}")
    print(f"Directories scanned: {result.directories_scanned}")
    print(f"Scan complete: {'YES' if result.is_complete else 'NO'}")
    _print_excluded_paths(result)
    if not result.is_complete:
        _print_inaccessible_paths(result)
    else:
        print("Inaccessible paths: 0")
    _print_extension_breakdown("Recognised media", result.recognised_extension_counts)
    _print_extension_breakdown("Unsupported", result.unsupported_extension_counts)


def _print_inaccessible_paths(
    result: ScanResult,
    *,
    output: TextIO | None = None,
) -> None:
    output = output or sys.stdout
    inaccessible = sorted(
        result.inaccessible_paths, key=lambda item: item.path.as_posix()
    )
    examples = inaccessible[:_MAX_INACCESSIBLE_EXAMPLES]
    print(f"Inaccessible paths: {len(inaccessible)}", file=output)
    print("Inaccessible path examples:", file=output)
    for item in examples:
        print(f"  {item.path} ({item.reason})", file=output)
    print(
        f"Showing {len(examples)} of {len(inaccessible)} inaccessible paths",
        file=output,
    )


def _print_excluded_paths(result: ScanResult) -> None:
    excluded = sorted(result.excluded_paths, key=lambda path: path.as_posix())
    print(f"Excluded paths: {len(excluded)}")
    if not excluded:
        return
    examples = excluded[:_MAX_INACCESSIBLE_EXAMPLES]
    print("Excluded path examples:")
    for path in examples:
        print(f"  {path}")
    print(f"Showing {len(examples)} of {len(excluded)} excluded paths")


def _warn_incomplete_scan(result: ScanResult, message: str) -> None:
    print("WARNING: Scan is incomplete.", file=sys.stderr)
    _print_inaccessible_paths(result, output=sys.stderr)
    print(message, file=sys.stderr)


def _print_extension_breakdown(title: str, counts: Mapping[str, int]) -> None:
    print(f"\n{title}:")
    labelled_counts = [
        (extension or _NO_EXTENSION_LABEL, count)
        for extension, count in counts.items()
    ]
    for label, count in sorted(labelled_counts, key=lambda item: (-item[1], item[0])):
        print(f"{label}: {count}")


def _print_proposal_summary(proposal: OrganisationProposal) -> None:
    print("Organisation proposal")
    print("No files have been changed.")
    print(f"\nMedia files: {len(proposal.placements)}")
    print(f"Proposed destinations: {len(proposal.placements)}")
    print(f"Destination collisions: {len(proposal.collision_destinations)}")
    print(f"Name conflict files: {proposal.name_conflict_files}")
    print("\nYears:")
    year_counts = Counter(
        placement.media_creation_date.year for placement in proposal.placements
    )
    for year, count in sorted(year_counts.items()):
        print(f"{year}: {count}")
    _print_collision_examples(proposal)


def _print_verification_summary(proposal: OrganisationProposal) -> None:
    print("Collision verification")
    if not proposal.collision_destinations:
        print("No destination collisions require verification.")
        print("No files have been changed.")
        return

    print(f"\nDestination collisions: {len(proposal.collision_destinations)}")
    print(f"Exact duplicate files: {proposal.exact_duplicate_files}")
    print(f"Potential conflict files: {proposal.potential_conflict_files}")
    print(f"Unverified conflict files: {proposal.unverified_conflict_files}")
    print("\nNo files have been changed.")
    _print_collision_examples(proposal)


def _print_collision_examples(proposal: OrganisationProposal) -> None:
    total_collisions = len(proposal.collision_destinations)
    if total_collisions == 0:
        return

    displayed_destinations = proposal.collision_destinations[
        :_MAX_COLLISION_EXAMPLES
    ]
    print("\nCollision examples:")
    for destination in displayed_destinations:
        print(f"\n{destination}")
        collision_placements = sorted(
            (
                placement
                for placement in proposal.placements
                if placement.normal_destination == destination
            ),
            key=lambda placement: placement.source.path,
        )
        for placement in collision_placements:
            label = {
                PlacementClassification.CANONICAL: "canonical",
                PlacementClassification.NAME_CONFLICT: "name conflict",
                PlacementClassification.EXACT_DUPLICATE: "exact duplicate",
                PlacementClassification.POTENTIAL_CONFLICT: "potential conflict",
                PlacementClassification.UNVERIFIED_CONFLICT: "unverified conflict",
            }[placement.classification]
            print(f"  {label}:")
            print(f"    {placement.source.path}")
    print(
        f"\nShowing {len(displayed_destinations)} of {total_collisions} collisions"
    )


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parsed_arguments = _build_parser().parse_args(arguments)
    if parsed_arguments.command in {
        "scan",
        "propose",
        "verify-collisions",
        "organise",
    }:
        try:
            if parsed_arguments.exclude:
                result = scan_media_collection(
                    parsed_arguments.directory,
                    excluded_paths=tuple(parsed_arguments.exclude),
                )
            else:
                result = scan_media_collection(parsed_arguments.directory)
        except NotADirectoryError:
            print(
                f"Error: '{parsed_arguments.directory}' is not a valid directory.",
                file=sys.stderr,
            )
            return 2
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            if parsed_arguments.command == "scan":
                raise
            if parsed_arguments.command == "organise":
                _print_organisation_cancellation(
                    0, 0, move=parsed_arguments.move
                )
                return 130
            _print_cancellation(parsed_arguments.command)
            return 130
        if not result.is_complete:
            if parsed_arguments.command == "organise":
                print(
                    "Organisation refused: source scan is incomplete.",
                    file=sys.stderr,
                )
                _print_inaccessible_paths(result, output=sys.stderr)
                print(
                    "No destination files or directories have been created.",
                    file=sys.stderr,
                )
                return 2
            if parsed_arguments.command == "propose":
                _warn_incomplete_scan(
                    result, "Proposal includes accessible media only."
                )
            elif parsed_arguments.command == "verify-collisions":
                _warn_incomplete_scan(
                    result, "Verification covers accessible media only."
                )
        if parsed_arguments.command != "scan" and result.excluded_paths:
            _print_excluded_paths(result)
        if parsed_arguments.command == "scan":
            _print_summary(result)
        elif parsed_arguments.command == "propose":
            try:
                proposal = generate_organisation_proposal(result)
            except KeyboardInterrupt:
                _print_cancellation(parsed_arguments.command)
                return 130
            _print_proposal_summary(proposal)
        elif parsed_arguments.command == "verify-collisions":
            print("Verifying destination collisions...")
            print("This may take a long time for large collections.\n")
            try:
                proposal = _verify_collisions(result)
            except KeyboardInterrupt:
                _print_cancellation(parsed_arguments.command)
                return 130
            _print_verification_summary(proposal)
        else:
            try:
                proposal = generate_organisation_proposal(result)
                full_plan = prepare_organisation_execution(
                    proposal,
                    parsed_arguments.directory,
                    parsed_arguments.destination,
                )
                capacity = plan_organisation_capacity(
                    proposal,
                    available_capacity(parsed_arguments.destination),
                )
                if capacity.execution_proposal is None:
                    _print_capacity_preflight(capacity)
                    print(
                        "No complete Year/Month group fits usable capacity.",
                        file=sys.stderr,
                    )
                    print("No media files have been copied.", file=sys.stderr)
                    return 2
                plan = (
                    prepare_organisation_execution(
                        capacity.execution_proposal,
                        parsed_arguments.directory,
                        parsed_arguments.destination,
                    )
                    if capacity.is_partial
                    else full_plan
                )
            except (UnsafeDestinationError, DestinationConflictError, OSError) as error:
                print(f"Organisation preflight failed: {error}", file=sys.stderr)
                print("No media files have been copied.", file=sys.stderr)
                return 2
            return _confirm_and_execute(
                plan, move=parsed_arguments.move, capacity=capacity
            )
    else:
        print("AnotherKindOfMediaOrganiser")
    return 0


def _verify_collisions(result: ScanResult) -> OrganisationProposal:
    progress_reporter = _CollisionProgressReporter(sys.stderr)
    digest_cache = _open_digest_cache()
    try:
        return generate_content_verified_organisation_proposal(
            result,
            progress_reporter,
            digest_cache=digest_cache,
        )
    except KeyboardInterrupt:
        progress_reporter.cancel()
        raise
    finally:
        if digest_cache is not None:
            digest_cache.close()


def _confirm_and_execute(
    plan: OrganisationExecutionPlan,
    *,
    move: bool = False,
    capacity: CapacityPreflight | None = None,
) -> int:
    if capacity is not None:
        _print_capacity_preflight(capacity)
    print("Organisation execution")
    print(f"\nSource:\n  {plan.source_root}")
    print(f"\nDestination:\n  {plan.destination_root}")
    action = "move" if move else "copy"
    print(f"\nMedia files to {action}: {len(plan.items)}")
    print(f"Name conflicts: {plan.name_conflict_files}")
    print(f"\nOperation: {'MOVE' if move else 'COPY'}")
    if move:
        print("\nEach file will be copied and verified before its original is deleted.")
        print("\nTHIS OPERATION WILL DELETE SOURCE FILES.")
    else:
        print("\nSource files will NOT be modified or deleted.")
    try:
        if capacity is not None and capacity.is_partial:
            print("\nContinue with this partial organisation? [y/N] ", end="")
            answer = input("")
        else:
            answer = input("\nContinue? [y/N] ")
    except EOFError:
        answer = ""
    except KeyboardInterrupt:
        print(f"\nOrganisation cancelled before {'moving' if move else 'copying'}.")
        return 130
    if answer.strip().lower() not in {"y", "yes"}:
        print(f"Organisation cancelled before {'moving' if move else 'copying'}.")
        return 0

    reporter = _CopyProgressReporter(len(plan.items), sys.stderr, move=move)
    try:
        if move:
            result = execute_organisation_plan(
                plan, reporter, mode=OrganisationExecutionMode.MOVE
            )
        else:
            result = execute_organisation_plan(plan, reporter)
    except KeyboardInterrupt:
        reporter.cancel()
        _print_organisation_cancellation(
            reporter.last_progress.files_copied,
            reporter.last_progress.total_files,
            move=move,
            files_verified=reporter.last_progress.files_verified,
            source_files_deleted=reporter.last_progress.source_files_deleted,
        )
        return 130
    except OrganisationVerificationError as error:
        reporter.cancel()
        print("Organisation verification failed.", file=sys.stderr)
        print(f"Failed source: {error.source}", file=sys.stderr)
        print(f"Failed destination: {error.destination}", file=sys.stderr)
        print("Source file was not deleted.", file=sys.stderr)
        return 1
    except OrganisationDeletionError as error:
        reporter.cancel()
        print("Source deletion failed after COPY+VERIFY succeeded.", file=sys.stderr)
        print(f"Source remains: {error.source}", file=sys.stderr)
        print(f"Verified destination remains: {error.destination}", file=sys.stderr)
        return 1
    except OrganisationCopyError as error:
        reporter.cancel()
        print("Organisation execution failed.", file=sys.stderr)
        print(f"Failed source: {error.source}", file=sys.stderr)
        print(f"Failed destination: {error.destination}", file=sys.stderr)
        print(
            f"Files copied: {error.files_copied} / {error.total_files}",
            file=sys.stderr,
        )
        if move:
            print("The failed source file was not deleted.", file=sys.stderr)
            print("Previously completed verified moves remain completed.", file=sys.stderr)
            print("No rollback was attempted.", file=sys.stderr)
        else:
            print("Source files have not been modified.", file=sys.stderr)
        print(
            "Destination may contain successfully completed copies.",
            file=sys.stderr,
        )
        return 1

    print(
        "\nPartial organisation completed."
        if capacity is not None and capacity.is_partial
        else "\nOrganisation completed."
    )
    if capacity is not None and capacity.is_partial:
        print(f"\nOrganised:\n  {_format_month_range(capacity.included_months)}")
    print(f"Files copied: {result.files_copied} / {result.total_files}")
    print(f"Data copied: {_format_bytes(result.bytes_copied)}")
    if move:
        print(f"Verified: {result.files_verified}")
        print(f"Source files deleted: {result.source_files_deleted}")
    else:
        print("Source files have not been modified.")
    if capacity is not None and capacity.is_partial:
        print("Remaining media was not modified.")
    return 0


def _print_capacity_preflight(capacity: CapacityPreflight) -> None:
    print("Organisation preflight")
    print(f"\nMedia files: {len(capacity.requested_proposal.placements)}")
    print(f"Required space: {_format_bytes(capacity.required_bytes)}")
    print(f"Available space: {_format_bytes(capacity.available_bytes)}")
    print(f"Safety reserve: {_format_bytes(capacity.reserve_bytes)}")
    print(f"Usable capacity: {_format_bytes(capacity.usable_bytes)}")
    if not capacity.excluded_groups:
        print(
            f"Estimated remaining: "
            f"{_format_bytes(capacity.usable_bytes - capacity.required_bytes)}"
        )
        print("\nSpace check: OK\n")
        return

    print("\nThe complete organisation does not fit.")
    if capacity.execution_proposal is None:
        print("\nA partial organisation is not possible.")
    else:
        print("\nA partial organisation is possible:")
        print(f"  {_format_month_range(capacity.included_months)}")
        print(
            f"  Media files: {len(capacity.execution_proposal.placements)}"
        )
        print(f"  Required: {_format_bytes(capacity.execution_required_bytes)}")
        print(
            f"  Estimated remaining: "
            f"{_format_bytes(capacity.usable_bytes - capacity.execution_required_bytes)}"
        )
    print("\nNot included:")
    for group in capacity.excluded_groups:
        print(
            f"  {group.year}/{group.month:02d} "
            f"({_format_bytes(group.required_bytes)})"
        )
    print()


def _format_month_range(months: tuple[tuple[int, int], ...]) -> str:
    first_year, first_month = months[0]
    last_year, last_month = months[-1]
    first = f"{first_year} {calendar.month_name[first_month]}"
    last = f"{last_year} {calendar.month_name[last_month]}"
    return first if first == last else f"{first} → {last}"


def _print_organisation_cancellation(
    files_copied: int,
    total_files: int,
    *,
    move: bool = False,
    files_verified: int = 0,
    source_files_deleted: int = 0,
) -> None:
    print("Organisation cancelled.", file=sys.stderr)
    print(f"Files copied: {files_copied} / {total_files}", file=sys.stderr)
    if move:
        print(f"Files verified: {files_verified}", file=sys.stderr)
        print(f"Source files deleted: {source_files_deleted}", file=sys.stderr)
        print("No rollback was attempted.", file=sys.stderr)
    else:
        print("Source files have not been modified.", file=sys.stderr)
    print(
        "Destination contains successfully completed copies.",
        file=sys.stderr,
    )


def _print_cancellation(command: str) -> None:
    message = (
        "Proposal generation cancelled."
        if command == "propose"
        else "Collision verification cancelled."
    )
    print(message, file=sys.stderr)
    print("No files have been changed.", file=sys.stderr)


def _open_digest_cache() -> SqliteDigestCache | None:
    try:
        return SqliteDigestCache(default_digest_cache_path())
    except (OSError, sqlite3.Error):
        return None
