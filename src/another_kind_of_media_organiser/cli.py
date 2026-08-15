"""Command-line interface for AnotherKindOfMediaOrganiser."""

import argparse
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.domain.media import MediaCategory, ScanResult
from another_kind_of_media_organiser.domain.organisation import OrganisationProposal


_NO_EXTENSION_LABEL = "[no extension]"
_MAX_COLLISION_EXAMPLES = 10


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
    print(f"Collisions: {len(proposal.collision_destinations)}")
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
        source_paths = sorted(
            placement.source.path
            for placement in proposal.placements
            if placement.destination == destination
        )
        for source_path in source_paths:
            print(f"  - {source_path}")
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
        if parsed_arguments.command == "scan":
            _print_summary(result)
        else:
            _print_proposal_summary(generate_organisation_proposal(result))
    else:
        print("AnotherKindOfMediaOrganiser")
    return 0
