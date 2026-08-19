"""HTTP routes for scanning and reviewing organisation proposals."""

from collections import Counter
from pathlib import Path
import calendar

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
from another_kind_of_media_organiser.presentation.web.copy_jobs import (
    CopyCoordinator,
    CopyRecord,
    CopyState,
)
from another_kind_of_media_organiser.application.execute_organisation_proposal import (
    OrganisationExecutionMode,
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


@browser.post("/copy-preflights")
def start_copy_preflight() -> tuple[str, int] | str:
    return _start_execution_preflight(OrganisationExecutionMode.COPY)


@browser.post("/move-preflights")
def start_move_preflight() -> tuple[str, int] | str:
    return _start_execution_preflight(OrganisationExecutionMode.MOVE)


def _start_execution_preflight(
    mode: OrganisationExecutionMode,
) -> tuple[str, int] | str:
    prepared = _prepare_submission()
    if _is_error_response(prepared):
        return prepared
    source, exclusions = prepared
    destination_value = request.form.get("destination", "").strip()
    if not destination_value:
        return _validation_error(
            "A Destination Collection path is required.",
            str(source),
            tuple(str(path) for path in exclusions),
        )
    try:
        record = _copy_coordinator().prepare(
            source, Path(destination_value), exclusions, mode=mode
        )
    except (OSError, ValueError) as error:
        return (
            render_template(
                "error.html",
                message=str(error),
                source=source,
                exclusions=exclusions,
            ),
            400,
        )
    return redirect(
        url_for(
            "browser.move_preflight"
            if mode is OrganisationExecutionMode.MOVE
            else "browser.copy_preflight",
            copy_id=record.copy_id,
        ),
        code=303,
    )


@browser.get("/copy-preflights/<copy_id>")
def copy_preflight(copy_id: str) -> str:
    record = _copy_coordinator().get(copy_id)
    if record is None or record.mode is not OrganisationExecutionMode.COPY:
        abort(404)
    return _render_copy_preflight(record)


@browser.get("/move-preflights/<copy_id>")
def move_preflight(copy_id: str) -> str:
    record = _copy_coordinator().get(copy_id)
    if record is None or record.mode is not OrganisationExecutionMode.MOVE:
        abort(404)
    return _render_copy_preflight(record)


@browser.post("/copy-preflights/<copy_id>/decision")
def decide_copy(copy_id: str) -> tuple[str, int]:
    return _decide_execution(copy_id, OrganisationExecutionMode.COPY)


@browser.post("/move-preflights/<copy_id>/decision")
def decide_move(copy_id: str) -> tuple[str, int]:
    return _decide_execution(copy_id, OrganisationExecutionMode.MOVE)


def _decide_execution(
    copy_id: str, mode: OrganisationExecutionMode
) -> tuple[str, int]:
    coordinator = _copy_coordinator()
    existing = coordinator.get(copy_id)
    if existing is None or existing.mode is not mode:
        abort(404)
    if request.form.get("decision") == "confirm":
        record = coordinator.confirm(
            copy_id, acceptance=request.form.get("acceptance", "")
        )
        if record is None:
            record = coordinator.decline(copy_id)
    else:
        record = coordinator.decline(copy_id)
    if record is None:
        abort(404)
    endpoint = (
        "browser.move_status"
        if mode is OrganisationExecutionMode.MOVE
        else "browser.copy_status"
    )
    return redirect(url_for(endpoint, copy_id=copy_id), code=303)


@browser.get("/copies/<copy_id>")
def copy_status(copy_id: str) -> str:
    record = _copy_coordinator().get(copy_id)
    if record is None or record.mode is not OrganisationExecutionMode.COPY:
        abort(404)
    return _render_copy_status(record)


@browser.get("/moves/<copy_id>")
def move_status(copy_id: str) -> str:
    record = _copy_coordinator().get(copy_id)
    if record is None or record.mode is not OrganisationExecutionMode.MOVE:
        abort(404)
    return _render_copy_status(record)


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


def _copy_coordinator() -> CopyCoordinator:
    return current_app.extensions["copy_coordinator"]


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


def _render_copy_preflight(record: CopyRecord) -> str:
    capacity = record.capacity
    estimated_remaining = (
        capacity.usable_bytes - capacity.execution_required_bytes
        if capacity.execution_proposal is not None
        else capacity.usable_bytes
    )
    return render_template(
        "copy_preflight.html",
        record=record,
        capacity=capacity,
        state=CopyState,
        logical_size=_format_bytes(capacity.logical_required_bytes),
        required_space=_format_bytes(capacity.required_bytes),
        available_space=_format_bytes(capacity.available_bytes),
        reserve=_format_bytes(capacity.reserve_bytes),
        estimated_remaining=_format_bytes(estimated_remaining),
        execution_required=_format_bytes(capacity.execution_required_bytes),
        month_range=(
            _format_month_range(capacity.included_months)
            if capacity.included_months
            else None
        ),
        execution_data=_format_bytes(
            sum(group.logical_bytes for group in capacity.included_groups)
        ),
        mode=OrganisationExecutionMode,
        inaccessible_examples=record.inaccessible_paths[:_MAX_PATH_EXAMPLES],
    )


def _render_copy_status(record: CopyRecord) -> str:
    progress = record.progress
    return render_template(
        "copy_status.html",
        record=record,
        state=CopyState,
        progress=progress,
        bytes_copied=(
            _format_bytes(progress.bytes_copied) if progress else "0 B"
        ),
        month_range=(
            _format_month_range(record.capacity.included_months)
            if record.capacity.included_months
            else None
        ),
        mode=OrganisationExecutionMode,
        inaccessible_examples=record.inaccessible_paths[:_MAX_PATH_EXAMPLES],
    )


def _format_month_range(months: tuple[tuple[int, int], ...]) -> str:
    first_year, first_month = months[0]
    last_year, last_month = months[-1]
    first = f"{first_year} {calendar.month_name[first_month]}"
    last = f"{last_year} {calendar.month_name[last_month]}"
    return first if first == last else f"{first} → {last}"
