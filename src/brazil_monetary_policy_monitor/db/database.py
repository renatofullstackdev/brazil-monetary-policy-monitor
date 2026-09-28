"""SQLite connection and forward-only schema migration support."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from typing import Iterable

_MIGRATION_RE = re.compile(r"^(?P<version>[0-9]{4})_(?P<name>[a-z0-9_]+)\.sql$")
_MIGRATIONS_DIR = Path(__file__).with_name("migrations")


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    path: Path


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a SQLite connection with the invariants required by this project."""

    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _discover_migrations(directory: Path = _MIGRATIONS_DIR) -> list[Migration]:
    migrations: list[Migration] = []

    for path in sorted(directory.glob("*.sql")):
        match = _MIGRATION_RE.fullmatch(path.name)
        if match is None:
            raise ValueError(f"invalid migration filename: {path.name}")
        migrations.append(
            Migration(
                version=int(match.group("version")),
                name=match.group("name"),
                path=path,
            )
        )

    versions = [migration.version for migration in migrations]
    expected = list(range(1, len(migrations) + 1))
    if versions != expected:
        raise ValueError(
            f"migration versions must be consecutive from 1; got {versions!r}"
        )

    return migrations


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY CHECK (version > 0),
            name TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


def _applied_versions(connection: sqlite3.Connection) -> set[int]:
    return {
        int(row["version"])
        for row in connection.execute("SELECT version FROM schema_migrations")
    }


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def migrate(
    connection: sqlite3.Connection,
    migrations: Iterable[Migration] | None = None,
) -> list[Migration]:
    """Apply pending migrations once, in order, and return those applied."""

    _ensure_migration_table(connection)
    available = list(migrations) if migrations is not None else _discover_migrations()
    applied_versions = _applied_versions(connection)
    applied_now: list[Migration] = []

    for migration in available:
        if migration.version in applied_versions:
            continue

        sql = migration.path.read_text(encoding="utf-8")
        name_literal = _sql_literal(migration.name)
        script = f"""
        BEGIN IMMEDIATE;
        {sql}
        INSERT INTO schema_migrations(version, name, applied_at)
        VALUES (
            {migration.version},
            {name_literal},
            strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        );
        PRAGMA user_version = {migration.version};
        COMMIT;
        """

        try:
            connection.executescript(script)
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise

        applied_now.append(migration)
        applied_versions.add(migration.version)

    return applied_now


def initialize_database(path: str | Path) -> sqlite3.Connection:
    """Create parent directories, open the database and apply all migrations."""

    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(database_path)
    migrate(connection)
    return connection
