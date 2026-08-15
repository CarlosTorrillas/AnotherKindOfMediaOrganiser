import tempfile
from pathlib import Path

from behave import given, then, when

from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.domain.media import MediaCategory


def _make_directory(context) -> Path:
    temporary_directory = tempfile.TemporaryDirectory()
    context.add_cleanup(temporary_directory.cleanup)
    context.scan_root = Path(temporary_directory.name) / "collection"
    context.scan_root.mkdir()
    return context.scan_root


def _create_file(root: Path, relative_path: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test fixture")


@given("a directory containing these supported media files:")
def step_supported_media_files(context) -> None:
    root = _make_directory(context)
    for row in context.table:
        _create_file(root, row["filename"])


@given("a directory containing media files in two nested directories")
def step_nested_media_files(context) -> None:
    root = _make_directory(context)
    _create_file(root, "first/photo.jpg")
    _create_file(root, "first/second/video.mov")


@given("a directory containing 1 supported media file and 2 unsupported files")
def step_supported_and_unsupported_files(context) -> None:
    root = _make_directory(context)
    for filename in ("photo.png", "notes.txt", ".DS_Store"):
        _create_file(root, filename)


@given("a directory containing mixed-case media extensions")
def step_mixed_case_extensions(context) -> None:
    root = _make_directory(context)
    for filename in ("photo.JpEg", "negative.NeF", "movie.MOV"):
        _create_file(root, filename)


@given("an empty directory")
def step_empty_directory(context) -> None:
    _make_directory(context)


@given("a directory containing a symbolic link to an external directory")
def step_directory_symlink(context) -> None:
    root = _make_directory(context)
    external = root.parent / "external"
    external.mkdir()
    _create_file(external, "outside.jpg")
    try:
        (root / "external-link").symlink_to(external, target_is_directory=True)
    except OSError as error:
        context.scenario.skip(f"Symbolic links are unavailable: {error}")


@when("the user scans the directory")
def step_scan_directory(context) -> None:
    context.result = scan_media_collection(context.scan_root)


@then("the scan reports {count:d} total files")
def step_total_files(context, count: int) -> None:
    assert context.result.total_files == count


@then("the scan reports {count:d} recognised media files")
def step_media_files(context, count: int) -> None:
    assert context.result.media_files == count


@then("the scan reports {count:d} recognised media file")
def step_single_media_file(context, count: int) -> None:
    step_media_files(context, count)


@then("the scan reports {count:d} unsupported files")
def step_unsupported_files(context, count: int) -> None:
    assert context.result.unsupported_files == count


@then("the scan reports {count:d} directories scanned")
def step_directories_scanned(context, count: int) -> None:
    assert context.result.directories_scanned == count


@then("the nested media files are included in the result")
def step_nested_files_included(context) -> None:
    relative_paths = {
        entry.path.relative_to(context.scan_root).as_posix()
        for entry in context.result.media_entries
    }
    assert relative_paths == {"first/photo.jpg", "first/second/video.mov"}


@then("the media counts are {images:d} images, {raw:d} RAW file, and {videos:d} video")
def step_media_counts(context, images: int, raw: int, videos: int) -> None:
    assert context.result.counts_by_category == {
        MediaCategory.IMAGE: images,
        MediaCategory.RAW: raw,
        MediaCategory.VIDEO: videos,
    }


@then("the media counts are {images:d} image, {raw:d} RAW file, and {videos:d} video")
def step_singular_media_counts(context, images: int, raw: int, videos: int) -> None:
    step_media_counts(context, images, raw, videos)


@then("the symbolic link is not recursively followed")
def step_symlink_not_followed(context) -> None:
    assert context.result.total_files == 0
    assert context.result.directories_scanned == 1
