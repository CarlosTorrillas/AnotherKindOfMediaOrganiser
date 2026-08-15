import pytest

from another_kind_of_media_organiser.domain.media import MediaCategory, classify_media


@pytest.mark.parametrize(
    ("filename", "expected_category"),
    [
        ("photo.jpg", MediaCategory.IMAGE),
        ("photo.jpeg", MediaCategory.IMAGE),
        ("photo.png", MediaCategory.IMAGE),
        ("photo.heic", MediaCategory.IMAGE),
        ("photo.arw", MediaCategory.RAW),
        ("photo.cr2", MediaCategory.RAW),
        ("photo.nef", MediaCategory.RAW),
        ("clip.mp4", MediaCategory.VIDEO),
        ("clip.mov", MediaCategory.VIDEO),
        ("clip.m4v", MediaCategory.VIDEO),
        ("notes.txt", MediaCategory.UNSUPPORTED),
        ("no-extension", MediaCategory.UNSUPPORTED),
    ],
)
def test_classifies_files_by_supported_extension(filename, expected_category) -> None:
    assert classify_media(filename) is expected_category


def test_classification_is_case_insensitive() -> None:
    assert classify_media("PHOTO.JpEg") is MediaCategory.IMAGE

