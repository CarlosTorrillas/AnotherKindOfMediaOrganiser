"""Persistent storage for completed file-content digests."""

import os
import sqlite3
import sys
from pathlib import Path


_DATABASE_FILENAME = "hash-cache.sqlite3"


def default_digest_cache_path() -> Path:
    """Return the platform-appropriate per-user cache database path."""
    if sys.platform == "darwin":
        cache_root = Path.home() / "Library" / "Caches"
        return cache_root / "AnotherKindOfMediaOrganiser" / _DATABASE_FILENAME

    configured_root = os.environ.get("XDG_CACHE_HOME")
    cache_root = Path(configured_root) if configured_root else Path.home() / ".cache"
    return cache_root / "another-kind-of-media-organiser" / _DATABASE_FILENAME


class SqliteDigestCache:
    """Store verified SHA-256 results and commit each completed result."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS file_digests (
                absolute_path TEXT PRIMARY KEY,
                file_size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                sha256 TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def lookup(self, path: Path, file_size: int, mtime_ns: int) -> str | None:
        """Return a valid digest for exactly matching file identity metadata."""
        try:
            row = self._connection.execute(
                """
                SELECT sha256
                FROM file_digests
                WHERE absolute_path = ? AND file_size = ? AND mtime_ns = ?
                """,
                (str(path.absolute()), file_size, mtime_ns),
            ).fetchone()
        except sqlite3.Error:
            return None
        if row is None or not _is_sha256(row[0]):
            return None
        return row[0]

    def store(self, path: Path, file_size: int, mtime_ns: int, digest: str) -> None:
        """Persist one completed digest atomically; cache errors remain non-fatal."""
        if not _is_sha256(digest):
            return
        try:
            self._connection.execute(
                """
                INSERT INTO file_digests (
                    absolute_path, file_size, mtime_ns, sha256
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(absolute_path) DO UPDATE SET
                    file_size = excluded.file_size,
                    mtime_ns = excluded.mtime_ns,
                    sha256 = excluded.sha256
                """,
                (str(path.absolute()), file_size, mtime_ns, digest),
            )
            self._connection.commit()
        except sqlite3.Error:
            try:
                self._connection.rollback()
            except sqlite3.Error:
                pass

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SqliteDigestCache":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
