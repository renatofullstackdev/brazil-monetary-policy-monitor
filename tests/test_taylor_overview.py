from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.collectors.bcb_sgs import parse_sgs_json
from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.ingestion import (
    ensure_bcb_focus_metadata,
    ensure_bcb_sgs_selic_metadata,
    persist_policy_inputs,
    persist_sgs_records,
    start_ingestion_run,
)
from brazil_monetary_policy_monitor.publish import build_overview_document


FIXTURES = Path(__file__).with_name("fixtures")


class TaylorOverviewTests(unittest.TestCase):
    def test_current_taylor_uses_documented_inputs_without_fabricating_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = initialize_database(root / "monitor.sqlite3")
            now = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)

            source_id, selic_id = ensure_bcb_sgs_selic_metadata(connection)
            run_id = start_ingestion_run(connection, source_id=source_id, started_at=now)
            records = parse_sgs_json((FIXTURES / "sgs_432_sample.json").read_bytes())
            persist_sgs_records(
                connection, series_id=selic_id, run_id=run_id,
                records=records, retrieved_at=now,
            )

            _, _, horizon_id = ensure_bcb_focus_metadata(connection)
            connection.execute(
                """
                INSERT INTO observations(
                    series_id, reference_period, reference_start, reference_end, value,
                    published_at, available_at, first_seen_at, last_seen_at,
                    vintage_key, source_revision, ingestion_run_id, quality_flags_json,
                    source_observation_at
                ) VALUES (?, '2028-Q1', '2027-04-01', '2028-03-31', 4.2,
                          NULL, ?, ?, ?, 'focus-test-v1', '2026-09-21', NULL, '[]', '2026-09-21')
                """,
                (horizon_id, now.isoformat().replace("+00:00", "Z"),
                 now.isoformat().replace("+00:00", "Z"), now.isoformat().replace("+00:00", "Z")),
            )
            connection.commit()
            persist_policy_inputs(connection, retrieved_at=now)

            document = build_overview_document(connection, generated_at=now)
            taylor = document["series"]["taylor_prospective"]
            self.assertEqual(taylor["status"], "available")
            self.assertAlmostEqual(taylor["latest"]["value"], 10.0)
            self.assertEqual(taylor["observations"], [])
            self.assertIn("não é uma série histórica reconstruída", taylor["note"])
            self.assertEqual(document["series"]["inflation_target"]["data_kind"], "observed")
            self.assertEqual(document["series"]["neutral_real_rate"]["data_kind"], "estimated")
            self.assertEqual(document["series"]["output_gap"]["data_kind"], "estimated")
            connection.close()


if __name__ == "__main__":
    unittest.main()
