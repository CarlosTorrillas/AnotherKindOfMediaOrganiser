"""Capacity-aware selection of an Organisation Proposal."""

from dataclasses import dataclass

from another_kind_of_media_organiser.domain.organisation import OrganisationProposal


DEFAULT_SAFETY_RESERVE_BYTES = 1024**3
YearMonth = tuple[int, int]


@dataclass(frozen=True)
class CapacityMonth:
    year: int
    month: int
    media_files: int
    required_bytes: int

    @property
    def key(self) -> YearMonth:
        return self.year, self.month


@dataclass(frozen=True)
class CapacityPreflight:
    requested_proposal: OrganisationProposal
    execution_proposal: OrganisationProposal | None
    required_bytes: int
    available_bytes: int
    reserve_bytes: int
    usable_bytes: int
    execution_required_bytes: int
    included_groups: tuple[CapacityMonth, ...]
    excluded_groups: tuple[CapacityMonth, ...]

    @property
    def is_partial(self) -> bool:
        return self.execution_proposal is not None and bool(self.excluded_groups)

    @property
    def included_months(self) -> tuple[YearMonth, ...]:
        return tuple(group.key for group in self.included_groups)

    @property
    def excluded_months(self) -> tuple[YearMonth, ...]:
        return tuple(group.key for group in self.excluded_groups)


def plan_organisation_capacity(
    proposal: OrganisationProposal,
    available_bytes: int,
    *,
    reserve_bytes: int = DEFAULT_SAFETY_RESERVE_BYTES,
) -> CapacityPreflight:
    """Select the oldest complete Year/Month prefix that fits usable capacity."""
    if available_bytes < 0 or reserve_bytes < 0:
        raise ValueError("capacity and reserve must not be negative")

    placements_by_month: dict[YearMonth, list] = {}
    for placement in proposal.placements:
        key = placement.media_creation_date.year, placement.media_creation_date.month
        placements_by_month.setdefault(key, []).append(placement)

    groups = tuple(
        CapacityMonth(
            year,
            month,
            len(placements_by_month[(year, month)]),
            sum(
                placement.source.path.stat().st_size
                for placement in placements_by_month[(year, month)]
            ),
        )
        for year, month in sorted(placements_by_month)
    )
    required = sum(group.required_bytes for group in groups)
    usable = max(0, available_bytes - reserve_bytes)
    if required <= usable:
        return CapacityPreflight(
            proposal,
            proposal,
            required,
            available_bytes,
            reserve_bytes,
            usable,
            required,
            groups,
            (),
        )

    included: list[CapacityMonth] = []
    selected_bytes = 0
    for group in groups:
        if selected_bytes + group.required_bytes > usable:
            break
        included.append(group)
        selected_bytes += group.required_bytes

    included_keys = {group.key for group in included}
    excluded = groups[len(included) :]
    if not included:
        selected_proposal = None
    else:
        selected_placements = tuple(
            placement
            for placement in proposal.placements
            if (
                placement.media_creation_date.year,
                placement.media_creation_date.month,
            )
            in included_keys
        )
        included_destinations = {
            placement.normal_destination for placement in selected_placements
        }
        selected_proposal = OrganisationProposal(
            selected_placements,
            tuple(
                destination
                for destination in proposal.collision_destinations
                if destination in included_destinations
            ),
        )

    return CapacityPreflight(
        proposal,
        selected_proposal,
        required,
        available_bytes,
        reserve_bytes,
        usable,
        selected_bytes,
        tuple(included),
        excluded,
    )
