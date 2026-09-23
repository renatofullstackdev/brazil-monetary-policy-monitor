from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.pipeline import update_yield_curve


FIXTURE = (Path(__file__).parent / "fixtures" / "tesouro_direto_rates.csv").read_bytes()
NOW = datetime(2026, 9, 22, 18, 0, tzinfo=timezone.utc)


class YieldCurvePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.database = root / "monitor.sqlite3"
        self.raw = root / "raw"
        self.output = root / "web" / "data" / "yield-curve.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self):
        return update_yield_curve(
            database_path=self.database,
            raw_root=self.raw,
            published_path=self.output,
            start=date(2026, 9, 1),
            end=date(2026, 9, 22),
            fetcher=lambda _url: FIXTURE,
            clock=lambda: NOW,
        )

    def test_pipeline_snapshots_persists_and_publishes_curve_contract(self) -> None:
        result = self._run()
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["records_in_file"], 9)
        self.assertEqual(result["records_received"], 8)
        self.assertTrue(self.output.is_file())
        payload = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(payload["view"], "yield_curve")
        self.assertEqual(payload["latest"]["effective_date"], "2026-09-22")
        self.assertEqual(payload["methodology"]["curve_type"], "offered_title_yield_proxy")
        self.assertIn("não deve ser interpretada", payload["methodology"]["caveat"])
        snapshot_dir = Path(result["snapshot_directory"])
        self.assertTrue((snapshot_dir / "manifest.json").is_file())
        self.assertTrue(any(path.name.startswith("chunk-") for path in snapshot_dir.iterdir()))

    def test_recollection_is_idempotent_and_preserves_revisions_table(self) -> None:
        first = self._run()
        second = self._run()
        self.assertEqual(first["records_inserted"], 8)
        self.assertEqual(second["records_inserted"], 0)
        self.assertEqual(second["records_unchanged"], 8)
        connection = initialize_database(self.database)
        try:
            count = connection.execute("SELECT COUNT(*) FROM yield_curve_quotes").fetchone()[0]
            provider = connection.execute(
                "SELECT provider FROM ingestion_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 8)
        self.assertEqual(provider, "Tesouro Nacional")

    def test_previous_copom_preset_is_explicitly_unavailable_without_events(self) -> None:
        self._run()
        payload = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(payload["presets"]["previous_copom"]["status"], "unavailable")
