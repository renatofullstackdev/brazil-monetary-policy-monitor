from __future__ import annotations

from datetime import date
import math
import unittest

from brazil_monetary_policy_monitor.models.term_structure import (
    B3_DI1_CURVE,
    MarketCurvePoint,
    adjacent_forwards,
    business_days_from_di_price,
    discount_factor,
    forward_rate_percent,
)


class TermStructureTests(unittest.TestCase):
    def test_di_business_day_tenor_is_recovered_from_price_and_rate(self) -> None:
        rate = 12.5
        du = 504
        price = 100000 * discount_factor(rate, du)
        self.assertEqual(business_days_from_di_price(rate_percent=rate, price_value=price), du)

    def test_forward_rate_uses_discount_factor_ratio(self) -> None:
        left = MarketCurvePoint(B3_DI1_CURVE, date(2026, 9, 24), "a", 12.0, 252)
        right = MarketCurvePoint(B3_DI1_CURVE, date(2026, 9, 24), "b", 13.0, 504)
        expected = ((discount_factor(12.0, 252) / discount_factor(13.0, 504)) ** 1 - 1) * 100
        self.assertAlmostEqual(forward_rate_percent(left, right), expected, places=12)

    def test_adjacent_forwards_are_sorted_by_tenor(self) -> None:
        points = [
            MarketCurvePoint(B3_DI1_CURVE, date(2026, 9, 24), "b", 13.0, 504, instrument_key="DI1F29"),
            MarketCurvePoint(B3_DI1_CURVE, date(2026, 9, 24), "a", 12.0, 252, instrument_key="DI1F28"),
        ]
        rows = adjacent_forwards(points)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["start_instrument"], "DI1F28")
        self.assertEqual(rows[0]["end_instrument"], "DI1F29")
        self.assertTrue(math.isfinite(rows[0]["rate_percent"]))
