from pathlib import Path

from another_kind_of_media_organiser.domain.media import (
    InaccessiblePath,
    MediaCategory,
    ScanResult,
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
    assert "Scan complete: NO" in page
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
