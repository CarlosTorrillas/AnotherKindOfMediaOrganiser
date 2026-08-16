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
    logical_bytes: int

    @property
    def key(self) -> YearMonth:
        return self.year, self.month


@dataclass(frozen=True)
class CapacityPreflight:
    requested_proposal: OrganisationProposal
    execution_proposal: OrganisationProposal | None
    required_bytes: int
    logical_required_bytes: int
    available_bytes: int
    allocation_unit: int
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
    allocation_unit: int,
    reserve_bytes: int = DEFAULT_SAFETY_RESERVE_BYTES,
) -> CapacityPreflight:
    """Select the oldest complete Year/Month prefix that fits usable capacity."""
    if available_bytes < 0 or reserve_bytes < 0 or allocation_unit <= 0:
        raise ValueError(
            "capacity and reserve must be non-negative and allocation unit positive"
        )

    placements_by_month: dict[YearMonth, list] = {}
    for placement in proposal.placements:
        key = placement.media_creation_date.year, placement.media_creation_date.month
        placements_by_month.setdefault(key, []).append(placement)

    group_list: list[CapacityMonth] = []
    for year, month in sorted(placements_by_month):
        logical_sizes = tuple(
            placement.source.path.stat().st_size
            for placement in placements_by_month[(year, month)]
        )
        group_list.append(
            CapacityMonth(
                year,
                month,
                len(logical_sizes),
                sum(_allocated_size(size, allocation_unit) for size in logical_sizes),
                sum(logical_sizes),
            )
        )
    groups = tuple(group_list)
    required = sum(group.required_bytes for group in groups)
    logical_required = sum(group.logical_bytes for group in groups)
    usable = max(0, available_bytes - reserve_bytes)
    if required <= usable:
        return CapacityPreflight(
            proposal,
            proposal,
            required,
            logical_required,
            available_bytes,
            allocation_unit,
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
        logical_required,
        available_bytes,
        allocation_unit,
        reserve_bytes,
        usable,
        selected_bytes,
        tuple(included),
        excluded,
    )


def _allocated_size(logical_size: int, allocation_unit: int) -> int:
    return ((logical_size + allocation_unit - 1) // allocation_unit) * allocation_unit
