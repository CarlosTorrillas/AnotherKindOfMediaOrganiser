import pytest

from another_kind_of_media_organiser.domain.media import MediaCategory, classify_media


@pytest.mark.parametrize(
    ("filename", "expected_category"),
    [
        ("photo.jpg", MediaCategory.IMAGE),
        ("photo.jpeg", MediaCategory.IMAGE),
        ("photo.png", MediaCategory.IMAGE),
        ("photo.heic", MediaCategory.IMAGE),
        ("photo.webp", MediaCategory.IMAGE),
        ("photo.tif", MediaCategory.IMAGE),
        ("photo.tiff", MediaCategory.IMAGE),
        ("photo.arw", MediaCategory.RAW),
        ("photo.cr2", MediaCategory.RAW),
        ("photo.nef", MediaCategory.RAW),
        ("photo.dng", MediaCategory.RAW),
        ("clip.mp4", MediaCategory.VIDEO),
        ("clip.mov", MediaCategory.VIDEO),
        ("clip.m4v", MediaCategory.VIDEO),
        ("clip.3gp", MediaCategory.VIDEO),
        ("sound.mp3", MediaCategory.AUDIO),
        ("sound.aac", MediaCategory.AUDIO),
        ("sound.opus", MediaCategory.AUDIO),
        ("sound.amr", MediaCategory.AUDIO),
        ("stereo.mpo", MediaCategory.UNSUPPORTED),
        ("graphic.svg", MediaCategory.UNSUPPORTED),
        ("notes.txt", MediaCategory.UNSUPPORTED),
        ("no-extension", MediaCategory.UNSUPPORTED),
    ],
)
def test_classifies_files_by_supported_extension(filename, expected_category) -> None:
    assert classify_media(filename) is expected_category


def test_classification_is_case_insensitive() -> None:
    assert classify_media("PHOTO.JpEg") is MediaCategory.IMAGE


@pytest.mark.parametrize(
    ("filename", "expected_category"),
    [
        ("PHOTO.WeBp", MediaCategory.IMAGE),
        ("CAMERA.DnG", MediaCategory.RAW),
        ("VIDEO.3Gp", MediaCategory.VIDEO),
        ("VOICE.OpUs", MediaCategory.AUDIO),
    ],
)
def test_new_media_formats_are_case_insensitive(
    filename, expected_category
) -> None:
    assert classify_media(filename) is expected_category
