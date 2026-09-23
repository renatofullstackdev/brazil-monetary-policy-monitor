from __future__ import annotations

from pathlib import Path
import unittest

from brazil_monetary_policy_monitor.collectors.tesouro_direto import (
    CURVE_INSTRUMENT_TYPES,
    parse_tesouro_direto_csv,
)


FIXTURE = Path(__file__).parent / "fixtures" / "tesouro_direto_rates.csv"


class TesouroDiretoCollectorTests(unittest.TestCase):
    def test_parser_accepts_official_brazilian_csv_contract(self) -> None:
        records = parse_tesouro_direto_csv(FIXTURE.read_bytes())
        self.assertEqual(len(records), 9)
        current = [row for row in records if row.reference_date.isoformat() == "2026-09-22"]
        self.assertEqual(len(current), 7)
        ipca = next(row for row in current if row.instrument_type == "Tesouro IPCA+")
        self.assertEqual(str(ipca.buy_yield), "6.80")
        self.assertEqual(str(ipca.buy_price), "3485.17")

    def test_curve_filter_excludes_selic_without_rejecting_source_row(self) -> None:
        records = parse_tesouro_direto_csv(FIXTURE.read_bytes())
        relevant = [row for row in records if row.instrument_type in CURVE_INSTRUMENT_TYPES]
        self.assertEqual(len(relevant), 8)
        self.assertTrue(all(row.instrument_type != "Tesouro Selic" for row in relevant))

    def test_parser_rejects_missing_required_columns(self) -> None:
        payload = b"Tipo Titulo;Data Base\nTesouro Prefixado;22/09/2026\n"
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            parse_tesouro_direto_csv(payload)
