from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.collectors.bcb_sgs import SGSRecord
from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.ingestion.focus import ensure_bcb_focus_metadata
from brazil_monetary_policy_monitor.ingestion.policy import (
    persist_output_gap_vintages,
    persist_policy_inputs,
)
from brazil_monetary_policy_monitor.ingestion.runs import start_ingestion_run
from brazil_monetary_policy_monitor.ingestion.sgs import (
    ensure_bcb_sgs_selic_metadata,
    persist_sgs_records,
)
from brazil_monetary_policy_monitor.monetary_history import build_monetary_posture_history
from brazil_monetary_policy_monitor.vintages import build_knowledge_context


class MonetaryHistoryTests(unittest.TestCase):
    def _database(self):
        temporary = tempfile.TemporaryDirectory()
        connection = initialize_database(Path(temporary.name) / "monitor.sqlite3")
        retrieved = datetime(2026, 9, 28, 15, tzinfo=timezone.utc)

        source_id, selic_id = ensure_bcb_sgs_selic_metadata(connection)
        run_id = start_ingestion_run(
            connection,
            source_id=source_id,
            started_at=retrieved,
            collector_version="test",
            provider="BCB",
        )
        persist_sgs_records(
            connection,
            series_id=selic_id,
            run_id=run_id,
            records=[
                SGSRecord(date(2024, 10, 1), Decimal("10.50")),
                SGSRecord(date(2024, 10, 2), Decimal("10.50")),
                SGSRecord(date(2024, 10, 8), Decimal("10.75")),
                SGSRecord(date(2024, 12, 20), Decimal("12.25")),
            ],
            retrieved_at=retrieved,
        )

        _, _, horizon_id = ensure_bcb_focus_metadata(connection)
        focus_points = [
            ("2024-09-24", "2024-10-01T23:59:59Z", 4.0, "f1"),
            ("2024-09-25", "2024-10-02T23:59:59Z", 4.1, "f2"),
            ("2024-10-01", "2024-10-08T23:59:59Z", 4.2, "f3"),
            ("2024-12-13", "2024-12-20T23:59:59Z", 4.0, "f4"),
        ]
        with connection:
            for source_date, available_at, value, vintage_key in focus_points:
                connection.execute(
                    """
                    INSERT INTO observations(
                        series_id, reference_period, reference_start, reference_end,
                        value, published_at, available_at, first_seen_at, last_seen_at,
                        vintage_key, source_revision, ingestion_run_id,
                        quality_flags_json, source_observation_at
                    ) VALUES (?, '2026-Q1', '2025-04-01', '2026-03-31', ?,
                              NULL, ?, ?, ?, ?, ?, NULL, '[]', ?)
                    """,
                    (
                        horizon_id,
                        value,
                        available_at,
                        retrieved.isoformat().replace("+00:00", "Z"),
                        retrieved.isoformat().replace("+00:00", "Z"),
                        vintage_key,
                        source_date,
                        source_date,
                    ),
                )

        persist_policy_inputs(connection, retrieved_at=retrieved)
        persist_output_gap_vintages(connection, retrieved_at=retrieved)
        return temporary, connection, retrieved

    def test_weekly_history_keeps_last_focus_vintage_per_iso_week(self) -> None:
        temporary, connection, retrieved = self._database()
        try:
            context = build_knowledge_context(generated_at=retrieved)
            history = build_monetary_posture_history(connection, context=context)
        finally:
            connection.close()
            temporary.cleanup()

        taylor = history["taylor_prospective"]
        self.assertEqual([point["date"] for point in taylor], [
            "2024-10-02", "2024-10-08", "2024-12-20",
        ])
        self.assertAlmostEqual(taylor[0]["value"], 9.65)
        self.assertEqual(taylor[0]["lineage"]["expected_inflation"]["value"], 4.1)

    def test_as_of_join_never_uses_future_neutral_rate_or_output_gap_revision(self) -> None:
        temporary, connection, retrieved = self._database()
        try:
            context = build_knowledge_context(generated_at=retrieved)
            history = build_monetary_posture_history(connection, context=context)
        finally:
            connection.close()
            temporary.cleanup()

        first = history["taylor_prospective"][0]
        self.assertEqual(first["lineage"]["neutral_real_rate"]["value"], 4.75)
        self.assertEqual(first["lineage"]["output_gap"]["source_revision"], "RI-2024-09")
        self.assertEqual(first["lineage"]["output_gap"]["reference_period"], "2024-Q3")

        december = history["taylor_prospective"][-1]
        self.assertEqual(december["lineage"]["neutral_real_rate"]["value"], 5.0)
        self.assertEqual(december["lineage"]["output_gap"]["source_revision"], "RI-2024-12")
        self.assertEqual(december["lineage"]["output_gap"]["reference_period"], "2024-Q4")

    def test_target_is_selected_for_expectation_horizon_not_evaluation_date(self) -> None:
        temporary, connection, retrieved = self._database()
        try:
            context = build_knowledge_context(generated_at=retrieved)
            history = build_monetary_posture_history(connection, context=context)
        finally:
            connection.close()
            temporary.cleanup()

        target = history["taylor_prospective"][0]["lineage"]["inflation_target"]
        self.assertEqual(target["value"], 3.0)
        self.assertEqual(target["effective_from"], "2025-01-01")
        self.assertLessEqual(target["available_at"], history["taylor_prospective"][0]["available_at"])

    def test_real_rate_and_gaps_share_the_same_weekly_knowledge_cut(self) -> None:
        temporary, connection, retrieved = self._database()
        try:
            context = build_knowledge_context(generated_at=retrieved)
            history = build_monetary_posture_history(connection, context=context)
        finally:
            connection.close()
            temporary.cleanup()

        ex_ante = history["ex_ante_real_rate"][0]
        real_gap = history["real_monetary_gap"][0]
        selic_gap = history["selic_minus_taylor"][0]
        self.assertAlmostEqual(ex_ante["value"], 6.4)
        self.assertAlmostEqual(real_gap["value"], 1.65)
        self.assertAlmostEqual(selic_gap["value"], 0.85)
        self.assertEqual(ex_ante["available_at"], real_gap["available_at"])
        self.assertEqual(ex_ante["available_at"], selic_gap["available_at"])

    def test_global_as_known_cutoff_truncates_reconstruction(self) -> None:
        temporary, connection, retrieved = self._database()
        try:
            context = build_knowledge_context(
                generated_at=retrieved,
                knowledge_mode="as_known",
                knowledge_cutoff="2024-10-05T23:59:59Z",
            )
            history = build_monetary_posture_history(connection, context=context)
        finally:
            connection.close()
            temporary.cleanup()

        self.assertEqual(len(history["taylor_prospective"]), 1)
        self.assertEqual(history["taylor_prospective"][0]["date"], "2024-10-02")


if __name__ == "__main__":
    unittest.main()
