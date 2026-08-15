"""Command-line interface for AnotherKindOfMediaOrganiser."""

import argparse
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from math import ceil
from pathlib import Path
from typing import TextIO

from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    CollisionClassificationProgress,
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


_NO_EXTENSION_LABEL = "[no extension]"
_MAX_COLLISION_EXAMPLES = 10
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
        line = self._format(progress, "Classifying destination collisions")
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
            self._format(progress, "Collision classification"),
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
            f"hashed {_format_bytes(progress.bytes_hashed)}"
        )


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
    propose_parser = subcommands.add_parser(
        "propose", help="propose how to organise a media collection"
    )
    propose_parser.add_argument("directory", type=Path)
    return parser


def _print_summary(result: ScanResult) -> None:
    print(f"Files scanned: {result.total_files}")
    print(f"Media files: {result.media_files}")
    print(f"Images: {result.counts_by_category[MediaCategory.IMAGE]}")
    print(f"RAW: {result.counts_by_category[MediaCategory.RAW]}")
    print(f"Videos: {result.counts_by_category[MediaCategory.VIDEO]}")
    print(f"Audio: {result.counts_by_category[MediaCategory.AUDIO]}")
    print(f"Unsupported: {result.unsupported_files}")
    print(f"Directories scanned: {result.directories_scanned}")
    _print_extension_breakdown("Recognised media", result.recognised_extension_counts)
    _print_extension_breakdown("Unsupported", result.unsupported_extension_counts)


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
    print(f"Exact duplicate files: {proposal.exact_duplicate_files}")
    print(f"Potential conflict files: {proposal.potential_conflict_files}")
    print(f"Unverified conflict files: {proposal.unverified_conflict_files}")
    print("\nYears:")
    year_counts = Counter(
        placement.media_creation_date.year for placement in proposal.placements
    )
    for year, count in sorted(year_counts.items()):
        print(f"{year}: {count}")
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
    if parsed_arguments.command in {"scan", "propose"}:
        try:
            result = scan_media_collection(parsed_arguments.directory)
        except NotADirectoryError:
            print(
                f"Error: '{parsed_arguments.directory}' is not a valid directory.",
                file=sys.stderr,
            )
            return 2
        except KeyboardInterrupt:
            if parsed_arguments.command != "propose":
                raise
            _print_proposal_cancellation()
            return 130
        if parsed_arguments.command == "scan":
            _print_summary(result)
        else:
            progress_reporter = _CollisionProgressReporter(sys.stderr)
            try:
                proposal = generate_organisation_proposal(result, progress_reporter)
            except KeyboardInterrupt:
                progress_reporter.cancel()
                _print_proposal_cancellation()
                return 130
            _print_proposal_summary(proposal)
    else:
        print("AnotherKindOfMediaOrganiser")
    return 0


def _print_proposal_cancellation() -> None:
    print("Proposal generation cancelled.", file=sys.stderr)
    print("No files have been changed.", file=sys.stderr)
