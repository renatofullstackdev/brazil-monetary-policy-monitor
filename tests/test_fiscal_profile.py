from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.db.parameters import parameter_latest
from brazil_monetary_policy_monitor.fiscal_profile import FISCAL_PROFILE_INPUTS
from brazil_monetary_policy_monitor.ingestion import persist_fiscal_profile_inputs


class FiscalProfileTests(unittest.TestCase):
    def test_rmd_snapshot_is_versioned_with_documentary_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 22, 20, tzinfo=timezone.utc)
            inserted, unchanged = persist_fiscal_profile_inputs(connection, retrieved_at=now)
            self.assertEqual(inserted, len(FISCAL_PROFILE_INPUTS))
            self.assertEqual(unchanged, 0)
            row = parameter_latest(connection, "br.dpf.average_term_years")
            self.assertEqual(row["value"], 4.05)
            self.assertEqual(row["unit"], "years")
            self.assertEqual(row["source_provider"], "Tesouro Nacional")
            self.assertIn("Tabela 3.3", row["source_reference"])
            connection.close()

    def test_rmd_snapshot_recollection_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = initialize_database(Path(directory) / "monitor.sqlite3")
            now = datetime(2026, 9, 22, 20, tzinfo=timezone.utc)
            first = persist_fiscal_profile_inputs(connection, retrieved_at=now)
            second = persist_fiscal_profile_inputs(connection, retrieved_at=now)
            self.assertEqual(first, (len(FISCAL_PROFILE_INPUTS), 0))
            self.assertEqual(second, (0, len(FISCAL_PROFILE_INPUTS)))
            connection.close()

    def test_profile_keeps_stock_maturity_cost_and_liquidity_distinct(self) -> None:
        by_key = {item.key: item for item in FISCAL_PROFILE_INPUTS}
        self.assertEqual(by_key["br.dpf.maturing_12m_share"].unit, "percent")
        self.assertEqual(by_key["br.dpf.average_term_years"].unit, "years")
        self.assertEqual(by_key["br.dpf.average_cost_12m"].unit, "percent_per_year")
        self.assertEqual(by_key["br.dpf.liquidity_index_months"].unit, "months")


if __name__ == "__main__":
    unittest.main()
