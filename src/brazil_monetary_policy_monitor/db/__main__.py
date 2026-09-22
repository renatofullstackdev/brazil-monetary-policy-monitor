"""Initialize or migrate a project SQLite database from the command line."""

from __future__ import annotations

import argparse

from .database import initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", help="Path to the SQLite database file")
    args = parser.parse_args()

    connection = initialize_database(args.database)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        connection.close()

    print(f"database ready: {args.database} (schema version {version})")


if __name__ == "__main__":
    main()
