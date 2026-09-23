from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from brazil_monetary_policy_monitor.db import (
    connect,
    initialize_database,
    migrate,
    observations_as_known,
    observations_latest,
)


class DatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = connect()
        migrate(self.connection)
        self.source_id = self._insert_source()
        self.series_id = self._insert_series()

    def tearDown(self) -> None:
        self.connection.close()

    def _insert_source(self, key: str = "bcb.sgs") -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO sources(key, provider, name)
            VALUES (?, ?, ?)
            """,
            (key, "BCB", "Sistema Gerenciador de Séries Temporais"),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def _insert_series(
        self,
        *,
        key: str = "br.selic.target",
        source_id: int | None = None,
        data_kind: str = "observed",
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO series(
                key, source_id, source_series_id, title,
                unit_normalized, frequency, data_kind
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                self.source_id if source_id is None else source_id,
                "432",
                "Meta Selic",
                "percent_per_year",
                "daily",
                data_kind,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def _insert_observation(
        self,
        *,
        value: float,
        vintage_key: str,
        available_at: str,
        first_seen_at: str,
        last_seen_at: str | None = None,
        reference_period: str = "2026-01-31",
        series_id: int | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO observations(
                series_id,
                reference_period,
                reference_start,
                reference_end,
                value,
                published_at,
                available_at,
                first_seen_at,
                last_seen_at,
                vintage_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.series_id if series_id is None else series_id,
                reference_period,
                "2026-01-01",
                "2026-01-31",
                value,
                available_at,
                available_at,
                first_seen_at,
                last_seen_at or first_seen_at,
                vintage_key,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)


class MigrationTests(unittest.TestCase):
    def test_migrate_is_idempotent_and_sets_schema_version(self) -> None:
        connection = connect()
        try:
            first = migrate(connection)
            second = migrate(connection)

            self.assertEqual([migration.version for migration in first], [1, 2, 3])
            self.assertEqual(second, [])
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                3,
            )
            rows = connection.execute(
                "SELECT version, name FROM schema_migrations"
            ).fetchall()
            self.assertEqual(
                [(row[0], row[1]) for row in rows],
                [(1, "initial_schema"), (2, "source_observation_timestamp"), (3, "yield_curve_quotes")],
            )
        finally:
            connection.close()

    def test_initialize_database_creates_parent_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "monitor.sqlite3"
            connection = initialize_database(path)
            connection.close()

            self.assertTrue(path.is_file())


class ConstraintTests(DatabaseTestCase):
    def test_foreign_keys_are_enabled(self) -> None:
        enabled = self.connection.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(enabled, 1)

        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_series(key="invalid.source", source_id=999_999)

    def test_source_keys_are_unique(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_source()

    def test_simulated_values_are_not_persisted_as_source_series(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_series(key="simulation", data_kind="simulated")

    def test_observation_period_must_be_ordered(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO observations(
                    series_id, reference_period, reference_start, reference_end,
                    value, available_at, first_seen_at, last_seen_at, vintage_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.series_id,
                    "2026-Q1",
                    "2026-03-31",
                    "2026-01-01",
                    1.0,
                    "2026-04-01T12:00:00Z",
                    "2026-04-01T12:00:00Z",
                    "2026-04-01T12:00:00Z",
                    "bad-period",
                ),
            )

    def test_same_vintage_cannot_be_inserted_twice(self) -> None:
        kwargs = {
            "value": 10.0,
            "vintage_key": "release-1",
            "available_at": "2026-02-01T12:00:00Z",
            "first_seen_at": "2026-02-01T12:05:00Z",
        }
        self._insert_observation(**kwargs)

        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_observation(**kwargs)

    def test_distinct_revisions_can_coexist_for_same_period(self) -> None:
        first_id = self._insert_observation(
            value=10.0,
            vintage_key="release-1",
            available_at="2026-02-01T12:00:00Z",
            first_seen_at="2026-02-01T12:05:00Z",
        )
        second_id = self._insert_observation(
            value=10.25,
            vintage_key="release-2",
            available_at="2026-03-01T12:00:00Z",
            first_seen_at="2026-03-01T12:05:00Z",
        )

        self.assertNotEqual(first_id, second_id)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM observations WHERE series_id = ?",
            (self.series_id,),
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_available_at_cannot_be_after_first_seen(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_observation(
                value=10.0,
                vintage_key="impossible-knowledge-time",
                available_at="2026-02-02T12:00:00Z",
                first_seen_at="2026-02-01T12:00:00Z",
            )

    def test_finished_ingestion_run_requires_finished_at(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO ingestion_runs(provider, started_at, status)
                VALUES ('BCB', '2026-09-22T10:00:00Z', 'succeeded')
                """
            )


class VintageQueryTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._insert_observation(
            value=10.0,
            vintage_key="release-1",
            available_at="2026-02-01T12:00:00Z",
            first_seen_at="2026-02-01T12:05:00Z",
        )
        self._insert_observation(
            value=10.25,
            vintage_key="release-2",
            available_at="2026-03-01T12:00:00Z",
            first_seen_at="2026-03-01T12:05:00Z",
        )

    def test_latest_returns_newest_revision(self) -> None:
        rows = observations_latest(self.connection, "br.selic.target")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], 10.25)
        self.assertEqual(rows[0]["vintage_key"], "release-2")

    def test_as_known_excludes_future_revision(self) -> None:
        rows = observations_as_known(
            self.connection,
            "br.selic.target",
            "2026-02-15T23:59:59Z",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], 10.0)
        self.assertEqual(rows[0]["vintage_key"], "release-1")

    def test_as_known_returns_no_value_before_first_availability(self) -> None:
        rows = observations_as_known(
            self.connection,
            "br.selic.target",
            "2026-01-31T23:59:59Z",
        )
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
