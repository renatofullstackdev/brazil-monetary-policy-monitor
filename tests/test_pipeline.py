from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from brazil_monetary_policy_monitor.collectors.http import ProviderFetchError
from brazil_monetary_policy_monitor.db import connect
from brazil_monetary_policy_monitor.pipeline import resolve_incremental_start, update_selic


FIXTURES = Path(__file__).with_name("fixtures")
SAMPLE = (FIXTURES / "sgs_432_sample.json").read_bytes()


class AdvancingClock:
    def __init__(self, start: datetime) -> None:
        self.value = start

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "data" / "database" / "monitor.sqlite3"
        self.raw = self.root / "data" / "raw"
        self.output = self.root / "data" / "published" / "br-selic-target.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _clock(self, second: int = 0) -> AdvancingClock:
        return AdvancingClock(datetime(2026, 9, 22, 12, 0, second, tzinfo=timezone.utc))

    def test_successful_pipeline_snapshots_persists_and_publishes(self) -> None:
        requested_urls: list[str] = []

        def fetcher(url: str) -> bytes:
            requested_urls.append(url)
            return SAMPLE

        result = update_selic(
            database_path=self.database,
            raw_root=self.raw,
            published_path=self.output,
            start=date(2026, 9, 1),
            end=date(2026, 9, 3),
            fetcher=fetcher,
            clock=self._clock(),
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["records_received"], 3)
        self.assertEqual(result["records_inserted"], 3)
        self.assertEqual(result["records_unchanged"], 0)
        self.assertEqual(len(requested_urls), 1)

        document = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(document["series"]["key"], "br.selic.target")
        self.assertEqual(len(document["observations"]), 3)
        self.assertEqual(document["observations"][-1]["value"], 14.75)

        snapshot_dir = Path(str(result["snapshot_directory"]))
        self.assertEqual((snapshot_dir / "chunk-001.json").read_bytes(), SAMPLE)
        manifest = json.loads((snapshot_dir / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["records_received"], 3)
        self.assertEqual(len(manifest["chunks"][0]["sha256"]), 64)

        connection = connect(self.database)
        try:
            run = connection.execute(
                "SELECT status, records_received, records_inserted FROM ingestion_runs"
            ).fetchone()
            self.assertEqual(tuple(run), ("succeeded", 3, 3))
            count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            self.assertEqual(count, 3)
        finally:
            connection.close()

    def test_repeated_identical_collection_does_not_duplicate_observations(self) -> None:
        for second in (0, 20):
            result = update_selic(
                database_path=self.database,
                raw_root=self.raw,
                published_path=self.output,
                start=date(2026, 9, 1),
                end=date(2026, 9, 3),
                fetcher=lambda _url: SAMPLE,
                clock=self._clock(second),
            )

        self.assertEqual(result["records_inserted"], 0)
        self.assertEqual(result["records_unchanged"], 3)

        connection = connect(self.database)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
                3,
            )
        finally:
            connection.close()

    def test_changed_provider_value_is_preserved_as_new_revision(self) -> None:
        update_selic(
            database_path=self.database,
            raw_root=self.raw,
            published_path=self.output,
            start=date(2026, 9, 1),
            end=date(2026, 9, 3),
            fetcher=lambda _url: SAMPLE,
            clock=self._clock(),
        )
        revised = SAMPLE.replace(b'"14.75"', b'"14.50"')
        update_selic(
            database_path=self.database,
            raw_root=self.raw,
            published_path=self.output,
            start=date(2026, 9, 1),
            end=date(2026, 9, 3),
            fetcher=lambda _url: revised,
            clock=self._clock(20),
        )

        connection = connect(self.database)
        try:
            rows = connection.execute(
                """
                SELECT value, available_at
                FROM observations
                WHERE reference_period = '2026-09-03'
                ORDER BY available_at
                """
            ).fetchall()
            self.assertEqual([row["value"] for row in rows], [14.75, 14.5])
        finally:
            connection.close()

        document = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(document["observations"][-1]["value"], 14.5)

    def test_invalid_provider_payload_is_snapshotted_without_corrupting_publication(self) -> None:
        update_selic(
            database_path=self.database,
            raw_root=self.raw,
            published_path=self.output,
            start=date(2026, 9, 1),
            end=date(2026, 9, 3),
            fetcher=lambda _url: SAMPLE,
            clock=self._clock(),
        )
        previous_output = self.output.read_bytes()
        malformed = b'{"unexpected":"shape"}'

        with self.assertRaises(ValueError):
            update_selic(
                database_path=self.database,
                raw_root=self.raw,
                published_path=self.output,
                start=date(2026, 9, 1),
                end=date(2026, 9, 3),
                fetcher=lambda _url: malformed,
                clock=self._clock(20),
            )

        self.assertEqual(self.output.read_bytes(), previous_output)
        manifests = sorted(self.raw.glob("bcb/*/sgs-432/run-*/manifest.json"))
        failed_manifest = json.loads(manifests[-1].read_text())
        failed_dir = manifests[-1].parent
        self.assertEqual(failed_manifest["status"], "failed")
        self.assertEqual((failed_dir / "chunk-001.json").read_bytes(), malformed)

    def test_provider_failure_preserves_last_valid_database_and_json(self) -> None:
        update_selic(
            database_path=self.database,
            raw_root=self.raw,
            published_path=self.output,
            start=date(2026, 9, 1),
            end=date(2026, 9, 3),
            fetcher=lambda _url: SAMPLE,
            clock=self._clock(),
        )
        previous_output = self.output.read_bytes()

        def fail(_url: str) -> bytes:
            raise ProviderFetchError("simulated upstream outage")

        with self.assertRaises(ProviderFetchError):
            update_selic(
                database_path=self.database,
                raw_root=self.raw,
                published_path=self.output,
                start=date(2026, 9, 1),
                end=date(2026, 9, 3),
                fetcher=fail,
                clock=self._clock(20),
            )

        self.assertEqual(self.output.read_bytes(), previous_output)
        connection = connect(self.database)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
                3,
            )
            latest_run = connection.execute(
                "SELECT status, error_json FROM ingestion_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(latest_run["status"], "failed")
            self.assertIn("ProviderFetchError", latest_run["error_json"])
        finally:
            connection.close()

        manifests = sorted(self.raw.glob("bcb/*/sgs-432/run-*/manifest.json"))
        failed_manifest = json.loads(manifests[-1].read_text())
        self.assertEqual(failed_manifest["status"], "failed")
        self.assertEqual(failed_manifest["chunks"], [])


    def test_default_pipeline_uses_one_year_operational_windows(self) -> None:
        requested_urls: list[str] = []

        def fetcher(url: str) -> bytes:
            requested_urls.append(url)
            return b"[]"

        result = update_selic(
            database_path=self.database,
            raw_root=self.raw,
            published_path=self.output,
            start=date(1999, 3, 5),
            end=date(2001, 3, 4),
            fetcher=fetcher,
            clock=self._clock(),
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(requested_urls), 2)
        self.assertIn("dataInicial=05%2F03%2F1999", requested_urls[0])
        self.assertIn("dataFinal=04%2F03%2F2000", requested_urls[0])
        self.assertIn("dataInicial=05%2F03%2F2000", requested_urls[1])
        self.assertIn("dataFinal=04%2F03%2F2001", requested_urls[1])

    def test_pipeline_rejects_window_above_provider_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 10"):
            update_selic(
                database_path=self.database,
                raw_root=self.raw,
                published_path=self.output,
                start=date(2026, 9, 1),
                end=date(2026, 9, 3),
                fetcher=lambda _url: SAMPLE,
                clock=self._clock(),
                window_years=11,
            )

    def test_incremental_start_overlaps_recent_observations(self) -> None:
        update_selic(
            database_path=self.database,
            raw_root=self.raw,
            published_path=self.output,
            start=date(2026, 9, 1),
            end=date(2026, 9, 3),
            fetcher=lambda _url: SAMPLE,
            clock=self._clock(),
        )

        connection = connect(self.database)
        try:
            start = resolve_incremental_start(
                connection,
                end=date(2026, 9, 22),
                overlap_days=7,
            )
        finally:
            connection.close()

        self.assertEqual(start, date(2026, 8, 27))


if __name__ == "__main__":
    unittest.main()
