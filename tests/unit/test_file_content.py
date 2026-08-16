from pathlib import Path

from another_kind_of_media_organiser.infrastructure import file_content


class RecordingHash:
    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    def update(self, chunk: bytes) -> None:
        self.chunks.append(chunk)

    def hexdigest(self) -> str:
        return "digest"


def test_sha256_digest_streams_a_file_in_chunks(
    tmp_path: Path, monkeypatch
) -> None:
    media_path = tmp_path / "large-video.mp4"
    media_path.write_bytes(b"0123456789")
    recording_hash = RecordingHash()
    monkeypatch.setattr(file_content.hashlib, "sha256", lambda: recording_hash)

    digest = file_content.sha256_digest(media_path, chunk_size=3)

    assert digest == "digest"
    assert recording_hash.chunks == [b"012", b"345", b"678", b"9"]


def test_sha256_digest_reports_bytes_from_existing_read_chunks(
    tmp_path: Path,
) -> None:
    media_path = tmp_path / "large-video.mp4"
    media_path.write_bytes(b"0123456789")
    reported_bytes: list[int] = []

    file_content.sha256_digest(
        media_path,
        chunk_size=3,
        on_bytes_read=reported_bytes.append,
    )

    assert reported_bytes == [3, 3, 3, 1]
