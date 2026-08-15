# AnotherKindOfMediaOrganiser

AnotherKindOfMediaOrganiser will help people inspect and safely organise photo and video collections into a predictable year, month, and media-type structure.

The project is currently at the bootstrap stage. It does not scan or modify media. The only application behaviour is a small CLI that identifies the application.

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
pytest
behave
```

## Architecture

Production code uses a `src` layout. The package has lightweight `domain`, `application`, and `infrastructure` namespaces so core organising behaviour can remain independent of presentation mechanisms such as the initial CLI or a future web UI. These namespaces intentionally contain no speculative abstractions yet.

Unit and integration tests live under `tests/`; Gherkin features and Behave step definitions live under `features/`.

## Development approach

Work proceeds in small, focused changes using BDD, TDD, and Red → Green → Refactor. Tests describe observable behaviour, production code uses type hints, and feature branches are reviewed through pull requests.

Safety is foundational: scan before modification, analyse before acting, propose changes before performing them, copy before moving or deleting originals, and explicitly validate destructive operations. The application currently performs no filesystem or media operations.

