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
from brazil_monetary_policy_monitor.publish import publish_series_json


FIXTURES = Path(__file__).with_name("fixtures")


class PublisherTests(unittest.TestCase):
    def test_publication_contains_normalized_metadata_and_latest_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = initialize_database(root / "monitor.sqlite3")
            try:
                source_id, series_id = ensure_bcb_sgs_selic_metadata(connection)
                timestamp = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
                run_id = start_ingestion_run(
                    connection, source_id=source_id, started_at=timestamp
                )
                records = parse_sgs_json(
                    (FIXTURES / "sgs_432_sample.json").read_bytes()
                )
                persist_sgs_records(
                    connection,
                    series_id=series_id,
                    run_id=run_id,
                    records=records,
                    retrieved_at=timestamp,
                )
                target = publish_series_json(
                    connection,
                    series_key="br.selic.target",
                    output_path=root / "published" / "selic.json",
                    generated_at=timestamp,
                )
            finally:
                connection.close()

            payload = json.loads(target.read_text())
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["series"]["source_series_id"], "432")
            self.assertEqual(payload["series"]["data_kind"], "observed")
            self.assertEqual(payload["series"]["unit_normalized"], "percent_per_year")
            self.assertEqual(len(payload["observations"]), 3)


if __name__ == "__main__":
    unittest.main()
