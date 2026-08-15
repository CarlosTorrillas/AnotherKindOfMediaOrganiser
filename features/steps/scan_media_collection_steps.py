import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from behave import given, then, when

from another_kind_of_media_organiser.application.scan_media_collection import (
    scan_media_collection,
)
from another_kind_of_media_organiser.cli import main
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


@given("a Media Collection containing these files:")
def step_media_collection_files(context) -> None:
    root = _make_directory(context)
    for row in context.table:
        _create_file(root, row["filename"])


@given("a Media Collection location that does not exist")
def step_missing_media_collection(context) -> None:
    root = _make_directory(context)
    context.scan_location = root / "missing"


@given("a Media Collection location that refers to a file")
def step_file_media_collection(context) -> None:
    root = _make_directory(context)
    context.scan_location = root / "photo.jpg"
    context.scan_location.touch()


@given("a Media Collection containing WEBP and TIFF images")
def step_additional_image_formats(context) -> None:
    root = _make_directory(context)
    for filename in ("photo.webp", "scan.tif", "archive.tiff"):
        _create_file(root, filename)


@given("a Media Collection containing a DNG file")
def step_dng_file(context) -> None:
    root = _make_directory(context)
    _create_file(root, "negative.dng")


@given("a Media Collection containing a 3GP file")
def step_3gp_file(context) -> None:
    root = _make_directory(context)
    _create_file(root, "recording.3gp")


@given("a Media Collection containing MP3, AAC, OPUS and AMR files")
def step_audio_formats(context) -> None:
    root = _make_directory(context)
    for filename in ("song.mp3", "sound.aac", "voice.opus", "message.amr"):
        _create_file(root, filename)


@given("a Media Collection containing mixed-case new media formats")
def step_mixed_case_new_formats(context) -> None:
    root = _make_directory(context)
    for filename in ("photo.WeBp", "negative.DnG", "clip.3Gp", "voice.OpUs"):
        _create_file(root, filename)


@given("a Media Collection containing deliberately unsupported formats")
def step_deliberately_unsupported_formats(context) -> None:
    root = _make_directory(context)
    for filename in ("stereo.mpo", "graphic.svg", "sidecar.xmp", "cloud.icloud"):
        _create_file(root, filename)


@when("the user scans the directory")
def step_scan_directory(context) -> None:
    context.result = scan_media_collection(context.scan_root)


@when("the user scans the Media Collection")
def step_scan_media_collection(context) -> None:
    step_scan_directory(context)


@when("the user attempts to scan the location")
def step_attempt_scan_location(context) -> None:
    standard_output = StringIO()
    standard_error = StringIO()
    with redirect_stdout(standard_output), redirect_stderr(standard_error):
        context.exit_code = main(["scan", str(context.scan_location)])
    context.standard_output = standard_output.getvalue()
    context.standard_error = standard_error.getvalue()


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
    assert context.result.counts_by_category[MediaCategory.IMAGE] == images
    assert context.result.counts_by_category[MediaCategory.RAW] == raw
    assert context.result.counts_by_category[MediaCategory.VIDEO] == videos


@then("the media counts are {images:d} image, {raw:d} RAW file, and {videos:d} video")
def step_singular_media_counts(context, images: int, raw: int, videos: int) -> None:
    step_media_counts(context, images, raw, videos)


@then("the symbolic link is not recursively followed")
def step_symlink_not_followed(context) -> None:
    assert context.result.total_files == 0
    assert context.result.directories_scanned == 1


def _extension_counts_from_table(context) -> dict[str, int]:
    return {
        "" if row["extension"] == "[no extension]" else row["extension"]: int(
            row["count"]
        )
        for row in context.table
    }


@then("the recognised extension breakdown is:")
def step_recognised_extension_breakdown(context) -> None:
    assert context.result.recognised_extension_counts == _extension_counts_from_table(
        context
    )


@then("the unsupported extension breakdown is:")
def step_unsupported_extension_breakdown(context) -> None:
    assert context.result.unsupported_extension_counts == _extension_counts_from_table(
        context
    )


@then("recognised extension counts equal recognised media files")
def step_recognised_extension_invariant(context) -> None:
    assert sum(context.result.recognised_extension_counts.values()) == (
        context.result.media_files
    )


@then("unsupported extension counts equal unsupported files")
def step_unsupported_extension_invariant(context) -> None:
    assert sum(context.result.unsupported_extension_counts.values()) == (
        context.result.unsupported_files
    )


@then("all extension counts equal total files")
def step_all_extension_invariant(context) -> None:
    assert (
        sum(context.result.recognised_extension_counts.values())
        + sum(context.result.unsupported_extension_counts.values())
        == context.result.total_files
    )


@then("the error reports that the location is not a valid directory")
def step_invalid_directory_error(context) -> None:
    assert context.standard_error == (
        f"Error: '{context.scan_location}' is not a valid directory.\n"
    )
    assert context.standard_output == ""


@then("no Python traceback is shown")
def step_no_traceback(context) -> None:
    assert "Traceback" not in context.standard_error


@then("the scan command returns a non-zero exit code")
def step_nonzero_exit_code(context) -> None:
    assert context.exit_code != 0


@then("{count:d} files are recognised as {category} media")
def step_files_recognised_as_category(context, count: int, category: str) -> None:
    assert context.result.counts_by_category[MediaCategory[category]] == count


@then("{count:d} file is recognised as {category} media")
def step_file_recognised_as_category(context, count: int, category: str) -> None:
    step_files_recognised_as_category(context, count, category)


@then("the scan reports {count:d} audio files")
def step_audio_file_count(context, count: int) -> None:
    assert context.result.counts_by_category[MediaCategory.AUDIO] == count


@then("the recognised extension breakdown is empty")
def step_empty_recognised_extension_breakdown(context) -> None:
    assert context.result.recognised_extension_counts == {}
