from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.db import connect
from brazil_monetary_policy_monitor.pipeline import update_focus_ipca

FIXTURES = Path(__file__).with_name("fixtures")
SAMPLE = (FIXTURES / "focus_ipca_monthly_sample.json").read_bytes()
EMPTY = b'{"value":[]}'


class AdvancingClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)

    def __call__(self):
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class FocusPipelineTests(unittest.TestCase):
    def test_pipeline_persists_raw_focus_and_horizon_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = 0
            def fetcher(url: str) -> bytes:
                nonlocal calls
                calls += 1
                return SAMPLE if calls == 1 else EMPTY

            result = update_focus_ipca(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_path=root / "focus.json",
                overview_path=root / "overview.json",
                start=date(2026, 9, 1),
                end=date(2026, 9, 30),
                fetcher=fetcher,
                clock=AdvancingClock(),
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["horizon"], "2028-Q1")
            self.assertEqual(result["horizon_expectations"], 2)
            self.assertEqual(result["records_received"], 24)

            connection = connect(root / "monitor.sqlite3")
            try:
                raw_count = connection.execute(
                    """SELECT COUNT(*) FROM observations o JOIN series s ON s.id=o.series_id
                       WHERE s.key='br.focus.ipca.monthly_median'"""
                ).fetchone()[0]
                derived_count = connection.execute(
                    """SELECT COUNT(*) FROM observations o JOIN series s ON s.id=o.series_id
                       WHERE s.key='br.focus.ipca.policy_horizon'"""
                ).fetchone()[0]
                row = connection.execute(
                    """SELECT published_at, available_at, source_observation_at
                       FROM observations o JOIN series s ON s.id=o.series_id
                       WHERE s.key='br.focus.ipca.monthly_median'
                       ORDER BY o.id LIMIT 1"""
                ).fetchone()
                self.assertEqual(raw_count, 24)
                self.assertEqual(derived_count, 2)
                self.assertIsNone(row["published_at"])
                self.assertEqual(row["source_observation_at"], "2026-09-11")
                self.assertTrue(row["available_at"].startswith("2026-09-22T"))
            finally:
                connection.close()

            overview = json.loads((root / "overview.json").read_text())
            self.assertEqual(overview["policy_horizon"]["reference"], "2028-Q1")
            self.assertEqual(overview["series"]["expected_inflation"]["status"], "available")
            self.assertEqual(overview["series"]["expected_inflation"]["data_kind"], "derived")
            self.assertEqual(overview["series"]["ex_ante_real_rate"]["status"], "unavailable")

    def test_identical_recollection_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for _ in range(2):
                calls = 0
                def fetcher(url: str) -> bytes:
                    nonlocal calls
                    calls += 1
                    return SAMPLE if calls == 1 else EMPTY
                result = update_focus_ipca(
                    database_path=root / "monitor.sqlite3",
                    raw_root=root / "raw",
                    published_path=root / "focus.json",
                    overview_path=root / "overview.json",
                    start=date(2026, 9, 1), end=date(2026, 9, 30),
                    fetcher=fetcher, clock=AdvancingClock(),
                )
            self.assertEqual(result["records_inserted"], 0)
            self.assertEqual(result["records_unchanged"], 26)

    def test_focus_refresh_makes_expected_inflation_and_real_rate_available_when_selic_exists(self) -> None:
        from brazil_monetary_policy_monitor.pipeline import update_selic
        from brazil_monetary_policy_monitor.publish import build_overview_document
        from brazil_monetary_policy_monitor.db import initialize_database

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sgs = (FIXTURES / "sgs_432_sample.json").read_bytes()
            update_selic(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_path=root / "selic.json",
                start=date(2026, 9, 1), end=date(2026, 9, 3),
                fetcher=lambda _url: sgs, clock=AdvancingClock(),
            )
            update_focus_ipca(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_path=root / "focus.json",
                overview_path=root / "overview.json",
                start=date(2026, 9, 1), end=date(2026, 9, 30),
                fetcher=lambda _url: SAMPLE, clock=AdvancingClock(),
            )
            connection = initialize_database(root / "monitor.sqlite3")
            try:
                overview = build_overview_document(
                    connection,
                    generated_at=datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
                )
            finally:
                connection.close()
            expectation = overview["series"]["expected_inflation"]
            real_rate = overview["series"]["ex_ante_real_rate"]
            self.assertEqual(expectation["status"], "available")
            self.assertEqual(expectation["latest"]["date"], "2028-Q1")
            self.assertEqual(real_rate["status"], "available")
            self.assertEqual(real_rate["unit"], "percent_per_year")
            self.assertAlmostEqual(
                real_rate["latest"]["value"],
                overview["series"]["selic"]["latest"]["value"] - expectation["latest"]["value"],
            )
