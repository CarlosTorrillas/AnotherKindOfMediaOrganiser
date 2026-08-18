from datetime import datetime, timezone
from pathlib import Path

from another_kind_of_media_organiser.domain.media import (
    InaccessiblePath,
    MediaCategory,
    MediaEntry,
    ScanResult,
)
from another_kind_of_media_organiser.domain.organisation import (
    OrganisationProposal,
    PlacementClassification,
    ProposedPlacement,
)
from another_kind_of_media_organiser.presentation.web import create_app


def test_incomplete_scan_is_prominently_reported_in_deterministic_order(
    monkeypatch,
) -> None:
    import another_kind_of_media_organiser.presentation.web.routes as routes

    result = ScanResult(
        total_files=0,
        unsupported_files=0,
        directories_scanned=1,
        counts_by_category={category: 0 for category in MediaCategory},
        recognised_extension_counts={},
        unsupported_extension_counts={},
        media_entries=(),
        inaccessible_paths=(
            InaccessiblePath(Path("z-last"), "denied"),
            InaccessiblePath(Path("a-first"), "denied"),
        ),
    )
    monkeypatch.setattr(routes, "scan_media_collection", lambda *_a, **_k: result)
    client = create_app({"TESTING": True}).test_client()

    response = client.post("/scan", data={"source": "/collection"})
    page = response.data.decode()

    assert "WARNING: Scan is incomplete." in page
    assert "> Incomplete</span>" in page
    assert page.index("a-first") < page.index("z-last")


def test_incomplete_proposal_warns_that_only_accessible_media_is_included(
    monkeypatch,
) -> None:
    import another_kind_of_media_organiser.presentation.web.routes as routes

    result = ScanResult(
        total_files=0,
        unsupported_files=0,
        directories_scanned=1,
        counts_by_category={category: 0 for category in MediaCategory},
        recognised_extension_counts={},
        unsupported_extension_counts={},
        media_entries=(),
        inaccessible_paths=(InaccessiblePath(Path("private"), "denied"),),
    )
    monkeypatch.setattr(routes, "scan_media_collection", lambda *_a, **_k: result)
    client = create_app({"TESTING": True}).test_client()

    response = client.post("/proposal", data={"source": "/collection"})

    assert b"WARNING: Scan is incomplete." in response.data
    assert b"Proposal includes accessible media only." in response.data


def test_proposal_shows_only_five_of_many_collision_examples(monkeypatch) -> None:
    import another_kind_of_media_organiser.presentation.web.routes as routes

    result = ScanResult(
        total_files=5,
        unsupported_files=0,
        directories_scanned=1,
        counts_by_category={
            category: 5 if category is MediaCategory.IMAGE else 0
            for category in MediaCategory
        },
        recognised_extension_counts={".jpg": 5},
        unsupported_extension_counts={},
        media_entries=(),
    )
    creation_date = datetime(2025, 2, 3, tzinfo=timezone.utc)
    destinations = tuple(
        Path(f"2025/02-February/IMAGE/photo-{number:04d}.jpg")
        for number in range(1_640)
    )
    placements = tuple(
        ProposedPlacement(
            source=MediaEntry(
                Path(f"/collection/photo-{number:04d}.jpg"),
                MediaCategory.IMAGE,
                creation_date,
            ),
            destination=destination,
            normal_destination=destination,
            category=MediaCategory.IMAGE,
            media_creation_date=creation_date,
            has_collision=True,
            classification=PlacementClassification.CANONICAL,
        )
        for number, destination in enumerate(destinations)
    )
    proposal = OrganisationProposal(placements, destinations)
    monkeypatch.setattr(routes, "scan_media_collection", lambda *_a, **_k: result)
    monkeypatch.setattr(
        routes, "generate_organisation_proposal", lambda _result: proposal
    )
    client = create_app({"TESTING": True}).test_client()

    response = client.post("/proposal", data={"source": "/collection"})
    page = response.data.decode()

    assert "Showing 5 of 1,640 collisions" in page
    assert "photo-0004.jpg" in page
    assert "photo-0005.jpg" not in page
