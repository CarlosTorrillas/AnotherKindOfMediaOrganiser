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
media-organiser organise /path/to/media --destination /separate/organised-media --move
media-organiser web
pytest
behave
```

The initial browser interface is server-rendered and strictly read-only. Start
it, then open `http://127.0.0.1:8080` in a browser:

```bash
media-organiser web
media-organiser web --host 127.0.0.1 --port 8080
```

It supports scans, repeatable relative exclusions, and lightweight Organisation
Proposals with Name Conflict review. Scans run synchronously, so the page shows
a working state and prevents duplicate submission while waiting. Proposal
requests rescan the collection instead of retaining server-side state.

From a proposal containing collisions, `Verify Collisions` starts the existing
deep, read-only verification workflow in a single background worker. Its opaque
status URL can be refreshed while the server remains running and reports
progress, cancellation, cache hits, bytes hashed, and at most five deterministic
examples. Cancellation stops cooperatively at a streamed hashing progress
callback; hashes from completed files remain in the persistent SQLite cache.
A server restart discards transient browser job status, but restarting
verification reuses valid completed hashes. Browser MOVE and file downloads
remain intentionally absent.

An accepted lightweight proposal can also run Capacity Preflight and COPY from
the browser. Preflight remains read-only, reports allocation-aware required
space and the separate safety reserve, and presents the same chronological
partial proposal when the full proposal does not fit. COPY requires an explicit
unchecked-by-default confirmation; capacity and destination conflicts are
revalidated at confirmation time before the accepted plan is queued. A single
background COPY worker provides a reconnectable progress/result page and
prevents confirmation replay from starting duplicate execution. Browser COPY
never invokes MOVE and never deletes source media.

Verified MOVE is available as a separate, visually distinct browser action and
is never the default. Its stronger confirmation states that source files will
be deleted and remains unchecked by default. After confirmation, the same
single execution queue invokes the existing MOVE mode, which alone enforces
`COPY → VERIFY → DELETE SOURCE`. Progress reports copied bytes, verified files,
and deleted sources. Verification or deletion failures preserve the current
source; completed verified moves remain completed without rollback.

The server binds only to localhost by default and does not use authentication.
A non-local bind such as `--host 0.0.0.0` must be explicit and displays a
warning because it makes the interface available beyond the current computer.

Every scanning command accepts repeatable exclusions relative to its scan root:

```bash
media-organiser scan /path/to/media --exclude old-backup
media-organiser propose /path/to/media --exclude "Lightroom Catalog"
media-organiser verify-collisions /path/to/media --exclude old-backup
media-organiser organise /path/to/media --destination /organised --move \
  --exclude old-backup --exclude "Lightroom Catalog"
```

At the scan-root level, the known macOS metadata directories
`.DocumentRevisions-V100`, `.Spotlight-V100`, `.TemporaryItems`, `.Trashes`, and
`.fseventsd` are excluded by default. Other hidden directories are scanned
normally. Encountered exclusions are reported separately from inaccessible
paths; an unexpected access failure still makes the scan incomplete.

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
a separate destination. Preflight rejects unsafe source/destination relationships and every
existing planned destination before the first copy. Completed files are kept if
a later runtime failure occurs; incomplete copies use distinguishable temporary
files and are cleaned up on a best-effort basis.

Before COPY or MOVE confirmation, Capacity Preflight reports required space,
available space, destination allocation unit, and a fixed 1 GiB safety reserve.
Required space rounds every planned file independently to the conservatively
reported filesystem allocation unit instead of assuming logical bytes consume
the same physical space. Directory metadata, concurrent filesystem activity,
and other filesystem-specific costs remain limitations covered by the separate
safety reserve. When the complete proposal does not fit, it can offer the
oldest complete Year/Month prefix that fits.
Planning stops at the first Year/Month that does not fit and never skips ahead
to a later month, even when that later month would fit the remaining capacity.
Declining that partial proposal writes nothing, and included placements always
retain their original proposed destinations.

Every scan reports `Scan complete: YES` or `Scan complete: NO`. Inaccessible
filesystem paths are counted and sampled rather than silently ignored.
`propose` and `verify-collisions` warn when their results cover only accessible
media. COPY remains the default. Explicit `--move` copies each file, verifies the
source and destination sizes and SHA-256 content, and only then deletes that source.
It does not use cached hashes as evidence for deletion. When an `organise` scan
is incomplete, confirmation identifies the inaccessible paths and warns that
COPY or MOVE cannot be complete. Declining writes nothing. Explicitly
continuing organises only the accessible eligible media through the normal
execution workflow, leaves inaccessible items untouched, and reports the
skipped inaccessible scope on completion.

Atomic copies preserve file content and the modification timestamp required by
the current Media Creation Date fallback. They deliberately do not copy Finder
metadata, unrelated extended attributes, resource forks, BSD flags, or other
platform metadata that can create AppleDouble (`._*`) sidecars on ExFAT.

The initial supported extensions are `.jpg`, `.jpeg`, `.png`, `.heic`, `.arw`, `.cr2`, `.nef`, `.mp4`, `.mov`, and `.m4v`, matched case-insensitively. Other files are reported as unsupported rather than silently ignored.

## Architecture

Production code uses a `src` layout. The package has lightweight `domain`,
`application`, and `infrastructure` namespaces. CLI and web adapters live in
the presentation boundary and call the same application workflows, keeping
scanning and proposal behaviour independent of HTTP and terminal rendering.
The browser adapter uses Flask and server-rendered Jinja templates; it does not
duplicate domain or filesystem behaviour.

Unit and integration tests live under `tests/`; Gherkin features and Behave step definitions live under `features/`.

The shared application vocabulary is defined in the [domain glossary](GLOSSARY.md).

## Development approach

Work proceeds in small, focused changes using BDD, TDD, and Red → Green → Refactor. Tests describe observable behaviour, production code uses type hints, and feature branches are reviewed through pull requests.

GitHub Actions installs the project under Python 3.13 and runs both pytest and Behave for pushes and pull requests.

Safety is foundational: scan before modification, analyse before acting, propose changes before performing them, copy before moving or deleting originals, and explicitly validate destructive operations. The current scanner only reads directory entries, file metadata, and supported filenames; it does not alter the scanned tree.
