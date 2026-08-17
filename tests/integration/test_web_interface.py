import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from another_kind_of_media_organiser.presentation.web import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


def _dated_file(path: Path, contents: bytes = b"media") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    timestamp = datetime(2025, 2, 3, tzinfo=timezone.utc).timestamp()
    os.utime(path, (timestamp, timestamp))


def test_root_displays_media_collection_form(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert b"AnotherKindOfMediaOrganiser" in response.data
    assert b"Media Collection path" in response.data
    assert b"Start scan" in response.data


def test_complete_scan_displays_counts_and_proposal_action(client, tmp_path: Path) -> None:
    _dated_file(tmp_path / "photo.jpg")
    (tmp_path / "notes.txt").write_text("notes")

    response = client.post("/scan", data={"source": str(tmp_path)})

    assert response.status_code == 200
    assert b"Scan Result" in response.data
    assert b"Scan complete: YES" in response.data
    assert b"Recognised media" in response.data
    assert b"Unsupported files" in response.data
    assert b"Directories scanned" in response.data
    assert b"Generate Organisation Proposal" in response.data


def test_exclusions_are_reported_and_media_is_not_scanned(client, tmp_path: Path) -> None:
    _dated_file(tmp_path / "included.jpg")
    _dated_file(tmp_path / "archive" / "excluded.jpg")

    response = client.post(
        "/scan", data={"source": str(tmp_path), "exclude": "archive"}
    )

    assert b"Recognised media</dt><dd>1" in response.data
    assert b"Excluded paths</dt><dd>1" in response.data
    assert b"archive" in response.data
    assert b"Inaccessible paths</dt><dd>0" in response.data


def test_proposal_displays_deterministic_name_conflicts(client, tmp_path: Path) -> None:
    _dated_file(tmp_path / "camera-a" / "IMG_001.jpg", b"first")
    _dated_file(tmp_path / "camera-b" / "IMG_001.jpg", b"second")

    response = client.post("/proposal", data={"source": str(tmp_path)})

    assert response.status_code == 200
    assert b"Organisation Proposal" in response.data
    assert b"Destination collisions</dt><dd>1" in response.data
    assert b"Name Conflict files</dt><dd>1" in response.data
    assert b"2025/02-February/IMAGE/IMG_001.jpg" in response.data
    assert b"camera-a" in response.data
    assert b"camera-b" in response.data
    assert b"Verify Collisions" in response.data


def test_missing_source_is_a_friendly_error_without_traceback(client, tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    response = client.post("/scan", data={"source": str(missing)})

    assert response.status_code == 400
    assert b"is not a valid directory" in response.data
    assert b"Traceback" not in response.data


@pytest.mark.parametrize("exclusion", ["../outside", "/absolute/path"])
def test_unsafe_exclusion_is_rejected_before_scanning(
    client, tmp_path: Path, exclusion: str, monkeypatch
) -> None:
    import another_kind_of_media_organiser.presentation.web.routes as routes

    def unexpected_scan(*args, **kwargs):
        raise AssertionError("unsafe exclusion must be rejected before scanning")

    monkeypatch.setattr(routes, "scan_media_collection", unexpected_scan)

    response = client.post(
        "/scan", data={"source": str(tmp_path), "exclude": exclusion}
    )

    assert response.status_code == 400
    assert b"must remain inside the Media Collection" in response.data


def test_browser_controlled_values_are_escaped(client) -> None:
    response = client.post(
        "/scan", data={"source": '<script>alert("unsafe")</script>'}
    )

    assert b"&lt;script&gt;" in response.data
    assert b'<script>alert("unsafe")</script>' not in response.data


def test_proposal_uses_lightweight_workflow_without_hash_or_cache(
    client, tmp_path: Path, monkeypatch
) -> None:
    import another_kind_of_media_organiser.presentation.web.routes as routes

    _dated_file(tmp_path / "a" / "same.jpg", b"one")
    _dated_file(tmp_path / "b" / "same.jpg", b"two")
    calls = 0
    real_generate = routes.generate_organisation_proposal

    def tracked_generate(result):
        nonlocal calls
        calls += 1
        return real_generate(result)

    monkeypatch.setattr(routes, "generate_organisation_proposal", tracked_generate)
    monkeypatch.setattr(
        "another_kind_of_media_organiser.infrastructure.file_content.sha256_digest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("hashed")),
    )

    response = client.post("/proposal", data={"source": str(tmp_path)})

    assert response.status_code == 200
    assert calls == 1


def test_web_routes_expose_no_write_operations(client) -> None:
    for path in ("/organise", "/copy", "/move", "/verify-collisions"):
        assert client.post(path).status_code == 404
