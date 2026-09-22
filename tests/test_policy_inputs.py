from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.db.parameters import parameter_latest
from brazil_monetary_policy_monitor.ingestion import persist_policy_inputs


class PolicyInputTests(unittest.TestCase):
    def test_documentary_inputs_are_versioned_with_explicit_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
            inserted, unchanged = persist_policy_inputs(connection, retrieved_at=now)
            self.assertEqual((inserted, unchanged), (3, 0))

            neutral = parameter_latest(connection, "br.neutral_real_rate.rpm", knowledge_cutoff=now.isoformat())
            self.assertIsNotNone(neutral)
            self.assertEqual(neutral["value"], 5.0)
            self.assertEqual(neutral["data_kind"], "estimated")
            self.assertEqual(neutral["source_reference"], "RPM junho/2026, p. 65")
            metadata = json.loads(neutral["metadata_json"])
            self.assertEqual(metadata["publication_time_precision"], "day")
            self.assertIn("rpm202606p.pdf", metadata["source_url"])
            connection.close()

    def test_repeated_sync_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            first = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
            second = datetime(2026, 9, 22, 16, tzinfo=timezone.utc)
            self.assertEqual(persist_policy_inputs(connection, retrieved_at=first), (3, 0))
            self.assertEqual(persist_policy_inputs(connection, retrieved_at=second), (0, 3))
            count = connection.execute("SELECT COUNT(*) FROM parameters").fetchone()[0]
            self.assertEqual(count, 3)
            connection.close()

    def test_future_effective_parameter_is_not_used_early(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
            persist_policy_inputs(connection, retrieved_at=now)
            connection.execute(
                """
                INSERT INTO parameters(
                    key, value, unit, data_kind, effective_from, published_at,
                    available_at, retrieved_at, version_key, methodology, metadata_json
                ) VALUES ('test.future', 7, 'percent', 'estimated', '2027-01-01',
                          '2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z',
                          '2026-09-22T15:00:00Z', 'future-v1', 'test', '{}')
                """
            )
            connection.commit()
            self.assertIsNone(
                parameter_latest(connection, "test.future", knowledge_cutoff="2026-09-22T15:00:00Z")
            )
            connection.close()

    def test_target_neutral_and_gap_keep_different_data_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
            persist_policy_inputs(connection, retrieved_at=now)
            target = parameter_latest(connection, "br.inflation.target", knowledge_cutoff=now.isoformat())
            neutral = parameter_latest(connection, "br.neutral_real_rate.rpm", knowledge_cutoff=now.isoformat())
            gap = parameter_latest(connection, "br.output_gap.rpm", knowledge_cutoff=now.isoformat())
            self.assertEqual(target["data_kind"], "observed")
            self.assertEqual(neutral["data_kind"], "estimated")
            self.assertEqual(gap["data_kind"], "estimated")
            connection.close()


if __name__ == "__main__":
    unittest.main()
