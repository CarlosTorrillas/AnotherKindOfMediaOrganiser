"""HTTP routes for scanning and reviewing organisation proposals."""

from collections import Counter
from pathlib import Path

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from another_kind_of_media_organiser.application.generate_organisation_proposal import (
    generate_organisation_proposal,
)
from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.media import MediaCategory, ScanResult
from another_kind_of_media_organiser.domain.organisation import OrganisationProposal
from another_kind_of_media_organiser.presentation.web.verification_jobs import (
    VerificationCoordinator,
    VerificationJob,
    VerificationState,
)


browser = Blueprint("browser", __name__)
_MAX_PATH_EXAMPLES = 10
_MAX_COLLISION_EXAMPLES = 5


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


@browser.post("/verifications")
def start_verification() -> tuple[str, int] | str:
    prepared = _prepare_submission()
    if _is_error_response(prepared):
        return prepared
    source, exclusions = prepared
    job = _verification_coordinator().submit(source, exclusions)
    return redirect(
        url_for("browser.verification_status", job_id=job.job_id),
        code=303,
    )


@browser.get("/verifications/<job_id>")
def verification_status(job_id: str) -> str:
    job = _verification_coordinator().get(job_id)
    if job is None:
        abort(404)
    return _render_verification(job)


@browser.post("/verifications/<job_id>/cancel")
def cancel_verification(job_id: str) -> tuple[str, int]:
    job = _verification_coordinator().cancel(job_id)
    if job is None:
        abort(404)
    return redirect(
        url_for("browser.verification_status", job_id=job_id),
        code=303,
    )


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
    collisions = _collision_examples(proposal) if proposal else ()
    return render_template(
        "review.html",
        source=source,
        exclusions=exclusions,
        result=result,
        inaccessible=inaccessible,
        inaccessible_examples=inaccessible[:_MAX_PATH_EXAMPLES],
        excluded=excluded,
        excluded_examples=excluded[:_MAX_PATH_EXAMPLES],
        proposal=proposal,
        year_counts=year_counts,
        collisions=collisions,
        collision_total=(
            f"{len(proposal.collision_destinations):,}" if proposal else "0"
        ),
        MediaCategory=MediaCategory,
    )


def _verification_coordinator() -> VerificationCoordinator:
    return current_app.extensions["verification_coordinator"]


def _render_verification(job: VerificationJob) -> str:
    proposal = job.proposal
    collisions = _collision_examples(proposal) if proposal else ()
    progress = job.progress
    percentage = (
        progress.processed_candidates * 100 // progress.total_candidates
        if progress is not None and progress.total_candidates
        else 0
    )
    return render_template(
        "verification.html",
        job=job,
        state=VerificationState,
        progress=progress,
        percentage=percentage,
        proposal=proposal,
        collisions=collisions,
        collision_total=(
            f"{len(proposal.collision_destinations):,}" if proposal else "0"
        ),
        hashed_bytes=_format_bytes(progress.bytes_hashed) if progress else "0 B",
    )


def _collision_examples(
    proposal: OrganisationProposal,
) -> tuple[tuple[Path, tuple], ...]:
    return tuple(
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
        for destination in proposal.collision_destinations[:_MAX_COLLISION_EXAMPLES]
    )


def _format_bytes(count: int) -> str:
    value = float(count)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")
