# AKOMO working agreement

This repository contains AnotherKindOfMediaOrganiser (AKOMO), a Python 3.13
application for inspecting and safely organising valuable personal media. This
file records durable engineering conventions for automated contributors. Read
`README.md`, `GLOSSARY.md`, and the relevant tests before changing behaviour.

## Start with evidence

- Inspect the current branch, working tree, relevant documentation, production
  code, tests, and recent Git history before editing.
- Preserve unrelated user changes. Keep each task focused on the requested
  behaviour; do not add adjacent improvements merely because they are convenient.
- Do not invent unspecified product behaviour. Resolve uncertainty from agreed
  terminology, tests, documentation, or established code. Ask when a material
  product decision remains ambiguous.
- Use the ubiquitous language in `GLOSSARY.md`. Update the glossary when an
  agreed story introduces or materially changes a domain concept; do not create
  casual synonyms for established terms.

## Behaviour-first development

Express the required behaviour before implementing it. Select the smallest test
level that proves the behaviour effectively: domain, application, API,
presentation/component, integration, end-to-end, or acceptance.

Gherkin is not mandatory. Use `features/` and Behave when Gherkin is the clearest
executable specification for user-facing or acceptance-level behaviour. Prefer
a focused pytest test when it communicates the requirement better. Tests should
describe observable behaviour rather than implementation details.

For behaviour changes, normally preserve a visible progression:

1. **RED** — add a focused test or executable specification that fails for the
   missing or incorrect behaviour, and confirm the expected failure.
2. **GREEN** — implement only what is needed and run the relevant focused tests.
3. **REFACTOR** — improve the design only when meaningful refactoring is needed,
   keeping behaviour green. Do not manufacture this stage.

Run broader validation after focused tests pass. A documentation-only change
does not require an artificial failing test.

## Architecture and dependency boundaries

Production code uses a `src` layout under
`src/another_kind_of_media_organiser/`:

- `domain/` owns business vocabulary and value/result types. Keep it independent
  of CLI, HTTP, Flask, and filesystem presentation concerns.
- `application/` owns use cases: scanning, proposal generation, collision
  verification, capacity planning, and organisation execution. Reuse these
  workflows rather than recreating their decisions elsewhere.
- `infrastructure/` owns filesystem traversal, atomic copying, content hashing,
  persistent digest caching, and filesystem-capacity details.
- `cli.py` and `presentation/web/` are presentation adapters. They parse user
  intent and render progress/results; they must not reimplement domain,
  classification, capacity, hashing, copy, verification, or deletion logic.

The core application must remain independent of its presentation mechanism so
CLI and browser behaviour can evolve without duplicating the organising rules.
Keep the server-rendered Flask/Jinja and small vanilla-JS approach lightweight;
do not introduce a frontend framework or infrastructure speculatively.

Use type hints in production code. Prefer simple functions and data structures
over abstractions created only for possible future use.

## Filesystem safety model

Treat the Media Collection as valuable and default to non-destructive behaviour.
Preserve these established distinctions and invariants:

### Inspection and planning

- A Scan is read-only, does not follow directory symlinks, reports unsupported
  files, and records inaccessible paths instead of silently ignoring them.
- An explicitly Excluded Path is outside the effective Media Collection and is
  reported separately. An unexpected inaccessible path makes the Scan
  incomplete. Do not turn access failures into implicit exclusions.
- The standard Organisation Proposal is lightweight and read-only. It does not
  hash content and does not create proposed directories.
- Collision Verification is an explicit, potentially expensive, read-only
  workflow. It may use size checks, streamed SHA-256, and the persistent cache,
  but it never modifies media.
- An incomplete Scan may support an explicitly warned proposal or verification.
  It may support Organisation Execution only after the inaccessible scope and
  incomplete outcome are clearly warned and the user explicitly accepts
  organising the accessible eligible media. Inaccessible items remain untouched.

### Organisation Execution

- Organisation Execution is the writing boundary and requires an accepted
  proposal, a separate Destination Collection, capacity preflight, destination
  conflict checks, and explicit user confirmation.
- COPY is always the default. It leaves every source file unchanged.
- MOVE is explicitly selected and must preserve this order for each file:
  **COPY → byte-for-byte VERIFY → DELETE SOURCE**. Never use a cached digest as
  evidence authorising source deletion.
- Never overwrite an existing destination. Reject source/destination overlap,
  destinations inside the source, and sources inside the destination.
- Atomic copies use a distinguishable same-directory temporary file, clean an
  incomplete temporary copy where safe, and preserve only the required
  modification timestamp rather than broad macOS metadata.
- On copy or verification failure, the current source remains. On deletion
  failure, both the verified destination and source remain. Previously completed
  copies or verified moves remain completed; do not claim or attempt rollback
  unless a future story explicitly defines it.
- Preserve real filesystem causes in error reporting when available. Do not
  reinterpret a recoverable filesystem condition as permission to delete,
  overwrite, skip, or assume cancellation.

Capacity estimation rounds each planned file independently to the destination
allocation unit and keeps the 1 GiB safety reserve separate. A Partial
Organisation Proposal is the oldest-first continuous prefix of complete
Year/Month groups. Planning stops at the first group that does not fit and does
not skip ahead. Unsupported and excluded files do not participate in execution.

## Determinism and collision terminology

- Sort stable filesystem-facing results by path where established. Proposal
  canonical selection, conflict numbering, review names, samples, and partial
  planning must remain deterministic across runs.
- A Destination Collision means multiple Media Entries compete for the same
  normal proposed destination; it says nothing about content.
- The lightweight proposal selects a deterministic Canonical Placement and
  routes other entries as Name Conflicts.
- Only explicit Collision Verification may classify Exact Duplicates, Potential
  Conflicts, or Unverified Conflicts. A failed comparison must never imply
  different content or an Exact Duplicate.
- The SQLite digest cache lives outside the Media Collection, stores only
  completed SHA-256 results, and conservatively revalidates absolute path, size,
  and `mtime_ns`. Cache failure must not produce an Exact Duplicate.

## Tests, commands, and tooling

The supported interpreter is Python `>=3.13,<3.14`. Development targets macOS;
runtime behaviour must remain compatible with Raspberry Pi OS / Debian Linux.
Avoid platform-specific dependencies unless explicitly justified.

Use the existing `.venv`; never recreate or commit it. Install locally with:

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run focused tests while developing, then normally run both complete suites:

```bash
pytest
behave
git diff --check
```

Tests live in `tests/unit/`, `tests/integration/`, and `features/`. Use temporary
directories and controlled fakes/monkeypatching for filesystem failures; do not
depend solely on Unix permission bits because tests run across platforms and may
run with elevated permissions. Never point automated tests at real media.

Useful local commands are:

```bash
media-organiser scan /path/to/media
media-organiser propose /path/to/media
media-organiser verify-collisions /path/to/media
media-organiser organise /path/to/media --destination /separate/destination
media-organiser web
```

GitHub Actions uses Python 3.13 and runs `git diff --check`, pytest, and Behave.
Keep CI green and do not add dependencies without a concrete need.

## Git and review workflow

- Start work from updated `main` and use a focused feature or chore branch.
- Commits are deliberate units of review. Make small, logically ordered local
  commits; for behaviour changes, retain useful RED → GREEN → REFACTOR history
  where applicable. Do not squash away useful development evidence.
- A local commit is a normal completion step even before user review.
- Do not push unless explicitly requested.
- Do not open or update a Pull Request unless explicitly requested.
- Never merge unless explicitly requested.
- Do not create artificial commits merely to satisfy a count or label.

At handoff, report the behaviour or documentation changed, focused and full
validation performed, branch/commit status, and any remaining uncertainty. Do
not claim checks, pushes, PRs, or merges that were not actually completed.
