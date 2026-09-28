from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.pipelines.market_curves import update_market_curves
from tests.test_market_curve_collectors import anbima_fixture, b3_fixture

NOW = datetime(2026, 9, 24, 21, 0, tzinfo=timezone.utc)


class MarketCurvesPipelineTests(unittest.TestCase):
    def test_pipeline_persists_both_sources_and_publishes_schema_v4(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "web" / "data" / "yield-curve.json"
            result = update_market_curves(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_path=output,
                start=date(2026, 9, 24),
                end=date(2026, 9, 24),
                get_fetcher=lambda _url: b3_fixture(),
                post_fetcher=lambda _url, _fields: anbima_fixture(),
                clock=lambda: NOW,
            )
            self.assertEqual(result["status"], "succeeded")
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 4)
            self.assertEqual(payload["market"]["ettj"]["status"], "available")
            self.assertEqual(payload["market"]["di"]["status"], "available")
            self.assertEqual(payload["market"]["ettj"]["latest"]["effective_date"], "2026-09-24")
            self.assertEqual(len(payload["market"]["di"]["latest"]["forwards"]), 1)
            self.assertEqual(payload["market"]["di"]["last_ingestion"]["records_received"], 2)
            self.assertIn("previsão pura da Selic", payload["market"]["methodology"]["caveat"])

    def test_malformed_provider_payload_fails_loudly_instead_of_being_treated_as_missing_day(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "web" / "data" / "yield-curve.json"
            with self.assertRaisesRegex(ValueError, "not a valid ZIP archive"):
                update_market_curves(
                    database_path=root / "monitor.sqlite3",
                    raw_root=root / "raw",
                    published_path=output,
                    start=date(2026, 9, 24),
                    end=date(2026, 9, 24),
                    get_fetcher=lambda _url: b"not-a-zip",
                    post_fetcher=lambda _url, _fields: anbima_fixture(),
                    clock=lambda: NOW,
                )
            self.assertFalse(output.exists())
