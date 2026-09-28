from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
import json
import unittest

from brazil_monetary_policy_monitor.collectors.bcb_focus import (
    build_focus_monthly_url,
    iter_focus_windows,
    parse_focus_monthly_json,
)
from brazil_monetary_policy_monitor.horizons import (
    derive_horizon_expectations,
    horizon_months,
    resolve_br_policy_horizon,
)

FIXTURES = Path(__file__).with_name("fixtures")
SAMPLE = (FIXTURES / "focus_ipca_monthly_sample.json").read_bytes()


class FocusCollectorTests(unittest.TestCase):
    def test_url_filters_ipca_and_date_window_without_server_side_base_filter(self) -> None:
        url = build_focus_monthly_url(date(2026, 9, 1), date(2026, 9, 30), top=50)
        self.assertIn("ExpectativaMercadoMensais", url)
        self.assertIn("%24top=50", url)
        self.assertNotIn("%24skip", url)
        self.assertNotIn("%24orderby", url)
        self.assertIn("Indicador%20eq%20%27IPCA%27", url)
        self.assertNotIn("Indicador+eq", url)
        self.assertIn("%20and%20Data%20ge%20", url)
        self.assertNotIn("baseCalculo%20eq", url)

    def test_focus_windows_cover_range_without_overlap(self) -> None:
        windows = list(
            iter_focus_windows(date(2026, 1, 1), date(2026, 7, 15), max_days=90)
        )
        self.assertEqual(windows[0], (date(2026, 1, 1), date(2026, 3, 31)))
        self.assertEqual(windows[-1][1], date(2026, 7, 15))
        for previous, current in zip(windows, windows[1:]):
            self.assertEqual(previous[1].toordinal() + 1, current[0].toordinal())


    def test_parser_accepts_boolean_base_false_and_discards_true(self) -> None:
        payload = json.loads(SAMPLE)
        current = dict(payload["value"][0])
        current["baseCalculo"] = False
        comparison = dict(current)
        comparison["baseCalculo"] = True
        comparison["Mediana"] = 99.9
        payload["value"] = [comparison, current]

        records = parse_focus_monthly_json(json.dumps(payload).encode())

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].median, Decimal(str(current["Mediana"])))
        self.assertEqual(records[0].base_calculation, 0)

    def test_parser_accepts_integer_base_zero_and_discards_one(self) -> None:
        payload = json.loads(SAMPLE)
        current = dict(payload["value"][0])
        current["baseCalculo"] = 0
        comparison = dict(current)
        comparison["baseCalculo"] = 1
        payload["value"] = [comparison, current]

        records = parse_focus_monthly_json(json.dumps(payload).encode())

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].base_calculation, 0)

    def test_parser_preserves_survey_date_target_month_and_median(self) -> None:
        records = parse_focus_monthly_json(SAMPLE)
        self.assertEqual(len(records), 24)
        self.assertEqual(records[0].survey_date, date(2026, 9, 11))
        self.assertEqual(records[0].target_month, date(2027, 4, 1))
        self.assertEqual(records[0].median, Decimal("0.3"))
        self.assertEqual(records[-1].survey_date, date(2026, 9, 18))
        self.assertEqual(records[-1].target_month, date(2028, 3, 1))

    def test_parser_rejects_wrong_indicator(self) -> None:
        payload = json.loads(SAMPLE)
        payload["value"][0]["Indicador"] = "IGP-M"
        with self.assertRaisesRegex(ValueError, "unexpected Focus indicator"):
            parse_focus_monthly_json(json.dumps(payload).encode())


class HorizonTests(unittest.TestCase):
    def test_current_configured_horizon_is_first_quarter_2028(self) -> None:
        horizon = resolve_br_policy_horizon(date(2026, 9, 22))
        self.assertEqual(horizon.key, "2028-Q1")
        self.assertEqual(horizon.window_start, date(2027, 4, 1))
        self.assertEqual(horizon.window_end, date(2028, 3, 31))
        self.assertEqual(len(horizon_months(horizon)), 12)

    def test_horizon_moves_explicitly_between_june_and_august(self) -> None:
        self.assertEqual(resolve_br_policy_horizon(date(2026, 7, 1)).key, "2027-Q4")
        self.assertEqual(resolve_br_policy_horizon(date(2026, 8, 10)).key, "2028-Q1")

    def test_compounds_only_complete_monthly_focus_windows(self) -> None:
        records = parse_focus_monthly_json(SAMPLE)
        horizon = resolve_br_policy_horizon(date(2026, 9, 22))
        results = derive_horizon_expectations(records, horizon=horizon)
        self.assertEqual([item.survey_date for item in results], [date(2026, 9, 11), date(2026, 9, 18)])
        expected = Decimal("1")
        for record in records[:12]:
            expected *= Decimal("1") + record.median / Decimal("100")
        expected = (expected - Decimal("1")) * Decimal("100")
        self.assertEqual(results[0].value, expected)

    def test_incomplete_monthly_window_is_not_published(self) -> None:
        records = parse_focus_monthly_json(SAMPLE)[:-1]
        horizon = resolve_br_policy_horizon(date(2026, 9, 22))
        results = derive_horizon_expectations(records, horizon=horizon)
        self.assertEqual(len(results), 1)
