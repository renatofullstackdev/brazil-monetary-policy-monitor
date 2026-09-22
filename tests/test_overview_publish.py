from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.collectors.bcb_sgs import parse_sgs_json
from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.ingestion import (
    ensure_bcb_sgs_selic_metadata,
    persist_sgs_records,
    start_ingestion_run,
)
from brazil_monetary_policy_monitor.publish import (
    build_overview_document,
    publish_overview_json,
)


FIXTURES = Path(__file__).with_name("fixtures")


class OverviewPublisherTests(unittest.TestCase):
    def _database_with_selic(self, root: Path):
        connection = initialize_database(root / "monitor.sqlite3")
        source_id, series_id = ensure_bcb_sgs_selic_metadata(connection)
        timestamp = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
        run_id = start_ingestion_run(
            connection,
            source_id=source_id,
            started_at=timestamp,
        )
        persist_sgs_records(
            connection,
            series_id=series_id,
            run_id=run_id,
            records=parse_sgs_json((FIXTURES / "sgs_432_sample.json").read_bytes()),
            retrieved_at=timestamp,
        )
        return connection, timestamp

    def test_contract_exposes_real_selic_and_explicitly_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection, timestamp = self._database_with_selic(root)
            try:
                document = build_overview_document(
                    connection,
                    generated_at=timestamp,
                )
            finally:
                connection.close()

        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["view"], "overview")
        self.assertEqual(document["knowledge_mode"], "latest_revision")
        self.assertEqual(document["availability"]["status"], "partial")

        selic = document["series"]["selic"]
        self.assertEqual(selic["status"], "available")
        self.assertEqual(selic["data_kind"], "observed")
        self.assertEqual(len(selic["observations"]), 3)
        self.assertEqual(selic["latest"]["date"], "2026-09-03")

        taylor = document["series"]["taylor_prospective"]
        self.assertEqual(taylor["status"], "unavailable")
        self.assertIsNone(taylor["latest"])
        self.assertEqual(taylor["observations"], [])
        self.assertIn("expected_inflation", taylor["required_inputs"])
        self.assertIn("output_gap", taylor["required_inputs"])

    def test_empty_database_never_fabricates_selic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            try:
                document = build_overview_document(
                    connection,
                    generated_at=datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
                )
            finally:
                connection.close()

        self.assertEqual(document["series"]["selic"]["status"], "unavailable")
        self.assertIsNone(document["series"]["selic"]["latest"])

    def test_publication_writes_valid_static_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection, timestamp = self._database_with_selic(root)
            try:
                target = publish_overview_json(
                    connection,
                    output_path=root / "web" / "data" / "overview.json",
                    generated_at=timestamp,
                )
            finally:
                connection.close()

            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["series"]["selic"]["status"], "available")
            self.assertFalse(any(target.parent.glob(".*.tmp")))


if __name__ == "__main__":
    unittest.main()
