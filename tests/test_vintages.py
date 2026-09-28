from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.db import connect, initialize_database, migrate
from brazil_monetary_policy_monitor.publish.overview import build_overview_document
from brazil_monetary_policy_monitor.publish.vintages import publish_vintage_archive
from brazil_monetary_policy_monitor.vintages import (
    build_knowledge_context,
    end_of_day_cutoff,
    known_dates,
)


class VintagePublicationTests(unittest.TestCase):
    def _seed_selic_revisions(self, connection) -> None:
        source_id = connection.execute(
            "INSERT INTO sources(key, provider, name) VALUES ('bcb.sgs', 'BCB', 'SGS')"
        ).lastrowid
        series_id = connection.execute(
            """
            INSERT INTO series(
                key, source_id, source_series_id, title, unit_normalized,
                frequency, data_kind
            ) VALUES ('br.selic.target', ?, '432', 'Meta Selic', 'percent_per_year', 'daily', 'observed')
            """,
            (source_id,),
        ).lastrowid
        for value, available, vintage in (
            (10.0, "2026-09-22T12:00:00Z", "v1"),
            (10.5, "2026-09-23T12:00:00Z", "v2"),
        ):
            connection.execute(
                """
                INSERT INTO observations(
                    series_id, reference_period, reference_start, reference_end,
                    value, published_at, available_at, first_seen_at, last_seen_at,
                    vintage_key
                ) VALUES (?, '2026-09-20', '2026-09-20', '2026-09-20', ?, ?, ?, ?, ?, ?)
                """,
                (series_id, value, available, available, available, available, vintage),
            )
        connection.commit()

    def test_as_known_overview_excludes_future_revision(self) -> None:
        connection = connect()
        migrate(connection)
        try:
            self._seed_selic_revisions(connection)
            generated = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
            latest = build_overview_document(connection, generated_at=generated)
            historical = build_overview_document(
                connection,
                generated_at=generated,
                knowledge_mode="as_known",
                knowledge_cutoff=end_of_day_cutoff(date(2026, 9, 22)),
            )
        finally:
            connection.close()

        self.assertEqual(latest["series"]["selic"]["latest"]["value"], 10.5)
        self.assertEqual(historical["series"]["selic"]["latest"]["value"], 10.0)
        self.assertEqual(historical["knowledge_mode"], "as_known")
        self.assertTrue(historical["knowledge_cutoff"].startswith("2026-09-22T"))

    def test_as_known_before_first_availability_does_not_backdate_reference_period(self) -> None:
        connection = connect()
        migrate(connection)
        try:
            self._seed_selic_revisions(connection)
            historical = build_overview_document(
                connection,
                generated_at=datetime(2026, 9, 24, 12, tzinfo=timezone.utc),
                knowledge_mode="as_known",
                knowledge_cutoff=end_of_day_cutoff(date(2026, 9, 21)),
            )
        finally:
            connection.close()

        self.assertEqual(historical["series"]["selic"]["status"], "unavailable")
        self.assertIsNone(historical["series"]["selic"]["latest"])

    def test_archive_publishes_static_bundle_and_index_for_selected_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = initialize_database(root / "monitor.sqlite3")
            try:
                self._seed_selic_revisions(connection)
                target = publish_vintage_archive(
                    connection,
                    root=root / "web" / "data" / "vintages",
                    generated_at=datetime(2026, 9, 24, 12, tzinfo=timezone.utc),
                    selected_dates=[date(2026, 9, 22)],
                )
            finally:
                connection.close()

            index = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual([entry["date"] for entry in index["entries"]], ["2026-09-22"])
            bundle = root / "web" / "data" / "vintages" / "2026-09-22"
            expected_files = (
                "overview.json",
                "copom-events.json",
                "credit-transmission.json",
                "fiscal.json",
                "external-sector.json",
                "us-benchmark.json",
                "yield-curve.json",
            )
            for filename in expected_files:
                with self.subTest(filename=filename):
                    contract = json.loads((bundle / filename).read_text(encoding="utf-8"))
                    self.assertEqual(contract["knowledge_mode"], "as_known")
                    self.assertTrue(contract["knowledge_cutoff"].startswith("2026-09-22T"))
            overview = json.loads((bundle / "overview.json").read_text(encoding="utf-8"))
            self.assertEqual(overview["series"]["selic"]["latest"]["value"], 10.0)

    def test_known_dates_are_local_availability_dates_not_reference_dates(self) -> None:
        connection = connect()
        migrate(connection)
        try:
            self._seed_selic_revisions(connection)
            self.assertEqual(known_dates(connection), [date(2026, 9, 22), date(2026, 9, 23)])
        finally:
            connection.close()

    def test_context_requires_explicit_cutoff_for_as_known(self) -> None:
        now = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            build_knowledge_context(generated_at=now, knowledge_mode="as_known")
        with self.assertRaises(ValueError):
            build_knowledge_context(
                generated_at=now,
                knowledge_mode="latest_revision",
                knowledge_cutoff=end_of_day_cutoff(date(2026, 9, 22)),
            )


class VintageWebTests(unittest.TestCase):
    def test_shell_exposes_global_knowledge_controls(self) -> None:
        html = Path("web/index.html").read_text(encoding="utf-8")
        self.assertIn('id="knowledge-select"', html)
        self.assertIn('value="latest_revision"', html)
        self.assertIn('value="as_known"', html)
        self.assertIn('id="knowledge-date"', html)
        self.assertIn('id="knowledge-apply"', html)

    def test_frontend_routes_as_known_through_static_vintage_files(self) -> None:
        script = Path("web/js/vintage.js").read_text(encoding="utf-8")
        app = Path("web/js/app.js").read_text(encoding="utf-8")
        self.assertIn("./data/vintages/index.json", script)
        self.assertIn("./data/vintages/${entry.date}", script)
        self.assertNotIn("fetch('/api", script)
        self.assertIn("resolveKnowledgeSelection", app)
        self.assertIn("knowledge.urls.overview", app)


if __name__ == "__main__":
    unittest.main()
