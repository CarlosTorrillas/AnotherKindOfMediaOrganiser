"""HTTP routes for scanning and reviewing organisation proposals."""

from collections import Counter
from pathlib import Path

from flask import Blueprint, render_template, request

from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.media import MediaCategory, ScanResult
from another_kind_of_media_organiser.domain.organisation import OrganisationProposal


browser = Blueprint("browser", __name__)
_MAX_EXAMPLES = 10


@browser.get("/")
def index() -> str:
    return render_template("index.html", source="", exclusions=())


@browser.post("/scan")
def scan() -> tuple[str, int] | str:
    prepared = _prepare_submission()
    if _is_error_response(prepared):
        return prepared
    source, exclusions = prepared
    result = _scan(source, exclusions)
    if isinstance(result, tuple):
        return result
    return _render_review(source, exclusions, result)


@browser.post("/proposal")
def proposal() -> tuple[str, int] | str:
    prepared = _prepare_submission()
    if _is_error_response(prepared):
        return prepared
    source, exclusions = prepared
    result = _scan(source, exclusions)
    if isinstance(result, tuple):
        return result
    organisation_proposal = generate_organisation_proposal(result)
    return _render_review(source, exclusions, result, organisation_proposal)


@browser.app_errorhandler(500)
def internal_error(_error: Exception) -> tuple[str, int]:
    return (
        render_template(
            "error.html",
            message="The request could not be completed safely.",
            source="",
            exclusions=(),
        ),
        500,
    )


def _prepare_submission() -> tuple[Path, tuple[Path, ...]] | tuple[str, int]:
    source_value = request.form.get("source", "").strip()
    exclusion_values = tuple(
        value.strip() for value in request.form.getlist("exclude") if value.strip()
    )
    try:
        exclusions = tuple(_safe_relative_exclusion(value) for value in exclusion_values)
    except ValueError as error:
        return _validation_error(str(error), source_value, exclusion_values)
    return Path(source_value), exclusions


def _is_error_response(
    result: tuple[Path, tuple[Path, ...]] | tuple[str, int],
) -> bool:
    return isinstance(result[1], int)


def _safe_relative_exclusion(value: str) -> Path:
    exclusion = Path(value)
    if exclusion.is_absolute() or ".." in exclusion.parts:
        raise ValueError(
            f"Exclusion '{value}' must remain inside the Media Collection."
        )
    return exclusion


def _scan(
    source: Path, exclusions: tuple[Path, ...]
) -> ScanResult | tuple[str, int]:
    try:
        if exclusions:
            return scan_media_collection(source, excluded_paths=exclusions)
        return scan_media_collection(source)
    except NotADirectoryError:
        return _validation_error(
            f"'{source}' is not a valid directory.",
            str(source),
            tuple(str(path) for path in exclusions),
        )
    except ValueError as error:
        return _validation_error(
            str(error), str(source), tuple(str(path) for path in exclusions)
        )


def _validation_error(
    message: str, source: str, exclusions: tuple[str, ...]
) -> tuple[str, int]:
    return (
        render_template(
            "index.html",
            error=message,
            source=source,
            exclusions=exclusions,
        ),
        400,
    )


def _render_review(
    source: Path,
    exclusions: tuple[Path, ...],
    result: ScanResult,
    proposal: OrganisationProposal | None = None,
) -> str:
    inaccessible = sorted(
        result.inaccessible_paths, key=lambda item: item.path.as_posix()
    )
    excluded = sorted(result.excluded_paths, key=lambda path: path.as_posix())
    year_counts = (
        sorted(
            Counter(
                placement.media_creation_date.year
                for placement in proposal.placements
            ).items()
        )
        if proposal
        else ()
    )
    collisions = (
        tuple(
            (
                destination,
                tuple(
                    sorted(
                        (
                            placement
                            for placement in proposal.placements
                            if placement.normal_destination == destination
                        ),
                        key=lambda placement: placement.source.path,
                    )
                ),
            )
            for destination in proposal.collision_destinations[:_MAX_EXAMPLES]
        )
        if proposal
        else ()
    )
    return render_template(
        "review.html",
        source=source,
        exclusions=exclusions,
        result=result,
        inaccessible=inaccessible,
        inaccessible_examples=inaccessible[:_MAX_EXAMPLES],
        excluded=excluded,
        excluded_examples=excluded[:_MAX_EXAMPLES],
        proposal=proposal,
        year_counts=year_counts,
        collisions=collisions,
        MediaCategory=MediaCategory,
    )
