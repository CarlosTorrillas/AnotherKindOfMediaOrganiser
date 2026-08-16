# AnotherKindOfMediaOrganiser

AnotherKindOfMediaOrganiser will help people inspect and safely organise photo and video collections into a predictable year, month, and media-type structure.

The project is in early development. It can recursively scan a media directory and report supported images, RAW files, videos, unsupported files, directories visited, and filesystem modification dates. Scanning is read-only and symbolic links are not followed.

## Requirements and setup

Python 3.13 is required (`>=3.13,<3.14`). Development is primarily on macOS, with Raspberry Pi OS / Debian Linux as the intended runtime environment.

Create and activate a virtual environment, then install the project and development tools:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run the application and test suites:

```bash
media-organiser
media-organiser scan /path/to/media
media-organiser propose /path/to/media
media-organiser verify-collisions /path/to/media
media-organiser organise /path/to/media --destination /separate/organised-media
pytest
behave
```

The `propose` command is lightweight and read-only: it calculates destinations
and reports naming conflicts without reading or hashing media content. Explicit
content-verification capabilities and their persistent SHA-256 cache are kept
separate from this default proposal workflow.

The explicitly expensive `verify-collisions` command inspects only Destination
Collisions. It classifies competing files as Exact Duplicates, Potential
Conflicts, or Unverified Conflicts using size-first, chunked SHA-256 comparison.
Completed hashes are cached outside the Media Collection and reused between
runs. Both commands produce read-only plans and never create their proposed
review directories.

The `organise` command is the only writing workflow. It displays the complete
lightweight execution summary and defaults confirmation to No before copying to
a separate destination. Source media is never moved, deleted, renamed, or
modified. Preflight rejects unsafe source/destination relationships and every
existing planned destination before the first copy. Completed files are kept if
a later runtime failure occurs; incomplete copies use distinguishable temporary
files and are cleaned up on a best-effort basis.

Every scan reports `Scan complete: YES` or `Scan complete: NO`. Inaccessible
filesystem paths are counted and sampled rather than silently ignored.
`propose` and `verify-collisions` warn when their results cover only accessible
media. `organise` refuses an incomplete source scan before creating or copying
anything; there is no override.

The initial supported extensions are `.jpg`, `.jpeg`, `.png`, `.heic`, `.arw`, `.cr2`, `.nef`, `.mp4`, `.mov`, and `.m4v`, matched case-insensitively. Other files are reported as unsupported rather than silently ignored.

## Architecture

Production code uses a `src` layout. The package has lightweight `domain`, `application`, and `infrastructure` namespaces so core organising behaviour can remain independent of presentation mechanisms such as the initial CLI or a future web UI. These namespaces intentionally contain no speculative abstractions yet.

Unit and integration tests live under `tests/`; Gherkin features and Behave step definitions live under `features/`.

The shared application vocabulary is defined in the [domain glossary](GLOSSARY.md).

## Development approach

Work proceeds in small, focused changes using BDD, TDD, and Red → Green → Refactor. Tests describe observable behaviour, production code uses type hints, and feature branches are reviewed through pull requests.

GitHub Actions installs the project under Python 3.13 and runs both pytest and Behave for pushes and pull requests.

Safety is foundational: scan before modification, analyse before acting, propose changes before performing them, copy before moving or deleting originals, and explicitly validate destructive operations. The current scanner only reads directory entries, file metadata, and supported filenames; it does not alter the scanned tree.
