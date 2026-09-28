from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.db.observations import observation_vintages, observations_as_known
from brazil_monetary_policy_monitor.db.parameters import parameter_for_reference_date, parameter_latest
from brazil_monetary_policy_monitor.ingestion.policy import (
    OUTPUT_GAP_SERIES_KEY,
    persist_output_gap_vintages,
    persist_policy_inputs,
)
from brazil_monetary_policy_monitor.policy_inputs import POLICY_INPUTS, OUTPUT_GAP_VINTAGES


class PolicyInputTests(unittest.TestCase):
    def test_documentary_regimes_are_versioned_with_explicit_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 28, 15, tzinfo=timezone.utc)
            inserted, unchanged = persist_policy_inputs(connection, retrieved_at=now)
            self.assertEqual((inserted, unchanged), (len(POLICY_INPUTS), 0))

            neutral = parameter_latest(connection, "br.neutral_real_rate.rpm", knowledge_cutoff=now.isoformat())
            self.assertIsNotNone(neutral)
            self.assertEqual(neutral["value"], 5.0)
            self.assertEqual(neutral["data_kind"], "estimated")
            self.assertIn("dezembro de 2024", neutral["source_reference"])
            self.assertEqual(neutral["effective_from"], "2024-12-17")
            connection.close()

    def test_repeated_sync_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            first = datetime(2026, 9, 28, 15, tzinfo=timezone.utc)
            second = datetime(2026, 9, 28, 16, tzinfo=timezone.utc)
            self.assertEqual(persist_policy_inputs(connection, retrieved_at=first), (len(POLICY_INPUTS), 0))
            self.assertEqual(persist_policy_inputs(connection, retrieved_at=second), (0, len(POLICY_INPUTS)))
            connection.close()

    def test_target_can_be_selected_for_future_reference_period_without_using_future_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 28, 15, tzinfo=timezone.utc)
            persist_policy_inputs(connection, retrieved_at=now)
            target_2024 = parameter_for_reference_date(
                connection, "br.inflation.target",
                reference_date="2024-06-30", knowledge_cutoff="2023-01-01T00:00:00Z",
            )
            self.assertIsNotNone(target_2024)
            self.assertEqual(target_2024["value"], 3.0)
            target_2025_too_early = parameter_for_reference_date(
                connection, "br.inflation.target",
                reference_date="2025-06-30", knowledge_cutoff="2024-06-25T23:59:59Z",
            )
            self.assertIsNone(target_2025_too_early)
            target_2025 = parameter_for_reference_date(
                connection, "br.inflation.target",
                reference_date="2025-06-30", knowledge_cutoff="2024-06-26T23:59:59Z",
            )
            self.assertEqual(target_2025["value"], 3.0)
            connection.close()

    def test_output_gap_preserves_revisions_as_document_vintages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 28, 15, tzinfo=timezone.utc)
            inserted, unchanged = persist_output_gap_vintages(connection, retrieved_at=now)
            self.assertEqual((inserted, unchanged), (len(OUTPUT_GAP_VINTAGES), 0))
            q2_2026 = observation_vintages(connection, OUTPUT_GAP_SERIES_KEY, reference_period="2026-Q2")
            self.assertEqual([row["value"] for row in q2_2026], [0.4, 0.5])
            known_in_june = observations_as_known(connection, OUTPUT_GAP_SERIES_KEY, "2026-06-30T23:59:59Z")
            by_period = {row["reference_period"]: row["value"] for row in known_in_june}
            self.assertEqual(by_period["2026-Q2"], 0.4)
            known_in_september = observations_as_known(connection, OUTPUT_GAP_SERIES_KEY, "2026-09-28T23:59:59Z")
            by_period = {row["reference_period"]: row["value"] for row in known_in_september}
            self.assertEqual(by_period["2026-Q2"], 0.5)
            connection.close()


    def test_default_catalog_removes_obsolete_policy_snapshot_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 28, 15, tzinfo=timezone.utc)
            from brazil_monetary_policy_monitor.ingestion.policy import ensure_policy_document_source
            source_id = ensure_policy_document_source(connection)
            with connection:
                connection.execute(
                    """INSERT INTO parameters(
                        key,value,unit,data_kind,effective_from,published_at,available_at,retrieved_at,
                        version_key,source_id,source_reference,methodology,metadata_json
                    ) VALUES('br.neutral_real_rate.rpm',5.0,'percent_per_year','estimated','2026-06-25',
                        '2026-06-25T23:59:59Z','2026-06-25T23:59:59Z','2026-06-25T23:59:59Z',
                        'obsolete',?,'legacy','legacy','{}')""",
                    (source_id,),
                )
                connection.execute(
                    """INSERT INTO parameters(
                        key,value,unit,data_kind,effective_from,published_at,available_at,retrieved_at,
                        version_key,source_id,source_reference,methodology,metadata_json
                    ) VALUES('br.output_gap.rpm',0.5,'percentage_points','estimated','2026-06-30',
                        '2026-06-30T23:59:59Z','2026-06-30T23:59:59Z','2026-06-30T23:59:59Z',
                        'legacy-gap',?,'legacy','legacy','{}')""",
                    (source_id,),
                )
            persist_policy_inputs(connection, retrieved_at=now)
            persist_output_gap_vintages(connection, retrieved_at=now)
            self.assertIsNone(connection.execute("SELECT 1 FROM parameters WHERE version_key='obsolete'").fetchone())
            self.assertIsNone(connection.execute("SELECT 1 FROM parameters WHERE key='br.output_gap.rpm'").fetchone())
            connection.close()

    def test_target_neutral_and_gap_keep_different_data_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 28, 15, tzinfo=timezone.utc)
            persist_policy_inputs(connection, retrieved_at=now)
            persist_output_gap_vintages(connection, retrieved_at=now)
            target = parameter_latest(connection, "br.inflation.target", knowledge_cutoff=now.isoformat())
            neutral = parameter_latest(connection, "br.neutral_real_rate.rpm", knowledge_cutoff=now.isoformat())
            gap_meta = connection.execute("SELECT data_kind FROM series WHERE key=?", (OUTPUT_GAP_SERIES_KEY,)).fetchone()
            self.assertEqual(target["data_kind"], "observed")
            self.assertEqual(neutral["data_kind"], "estimated")
            self.assertEqual(gap_meta["data_kind"], "estimated")
            connection.close()


if __name__ == "__main__":
    unittest.main()
