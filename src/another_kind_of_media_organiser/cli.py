"""Command-line interface for AnotherKindOfMediaOrganiser."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.media import MediaCategory, ScanResult


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="media-organiser")
    subcommands = parser.add_subparsers(dest="command")
    scan_parser = subcommands.add_parser("scan", help="scan a media collection")
    scan_parser.add_argument("directory", type=Path)
    return parser


def _print_summary(result: ScanResult) -> None:
    print(f"Files scanned: {result.total_files}")
    print(f"Media files: {result.media_files}")
    print(f"Images: {result.counts_by_category[MediaCategory.IMAGE]}")
    print(f"RAW: {result.counts_by_category[MediaCategory.RAW]}")
    print(f"Videos: {result.counts_by_category[MediaCategory.VIDEO]}")
    print(f"Unsupported: {result.unsupported_files}")
    print(f"Directories scanned: {result.directories_scanned}")


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parsed_arguments = _build_parser().parse_args(arguments)
    if parsed_arguments.command == "scan":
        result = scan_media_collection(parsed_arguments.directory)
        _print_summary(result)
    else:
        print("AnotherKindOfMediaOrganiser")
    return 0
