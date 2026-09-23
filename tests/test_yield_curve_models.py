from __future__ import annotations

from datetime import date
import unittest

from brazil_monetary_policy_monitor.models.yield_curve import (
    CurvePoint,
    build_curve_snapshot,
    fisher_breakeven,
    interpolate_curve,
)


class YieldCurveModelTests(unittest.TestCase):
    def test_interpolation_is_linear_only_inside_observed_range(self) -> None:
        points = [
            CurvePoint(3.0, 12.0, "2029-01-01", "Tesouro Prefixado"),
            CurvePoint(7.0, 14.0, "2033-01-01", "Tesouro Prefixado"),
        ]
        self.assertAlmostEqual(interpolate_curve(points, 5.0), 13.0)
        self.assertIsNone(interpolate_curve(points, 2.0))
        self.assertIsNone(interpolate_curve(points, 10.0))

    def test_breakeven_uses_exact_fisher_relation_not_simple_spread(self) -> None:
        value = fisher_breakeven(12.0, 6.0)
        self.assertAlmostEqual(value, (1.12 / 1.06 - 1.0) * 100.0, places=10)
        self.assertNotAlmostEqual(value, 6.0, places=4)

    def test_snapshot_uses_previous_trading_day_and_does_not_extrapolate(self) -> None:
        rows = [
            {"reference_date": "2026-09-21", "instrument_type": "Tesouro Prefixado", "maturity_date": "2029-09-21", "buy_yield": 12.0},
            {"reference_date": "2026-09-21", "instrument_type": "Tesouro Prefixado", "maturity_date": "2036-09-21", "buy_yield": 13.0},
            {"reference_date": "2026-09-21", "instrument_type": "Tesouro IPCA+", "maturity_date": "2029-09-21", "buy_yield": 6.0},
            {"reference_date": "2026-09-21", "instrument_type": "Tesouro IPCA+", "maturity_date": "2041-09-21", "buy_yield": 6.5},
        ]
        snapshot = build_curve_snapshot(rows, requested_date=date(2026, 9, 22))
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["effective_date"], "2026-09-21")
        two_year = next(item for item in snapshot["tenors"] if item["tenor_years"] == 2.0)
        self.assertIsNone(two_year["nominal"])
        self.assertIsNone(two_year["real"])
        ten_year = next(item for item in snapshot["tenors"] if item["tenor_years"] == 10.0)
        self.assertIsNotNone(ten_year["nominal"])
        self.assertIsNotNone(ten_year["real"])
        self.assertIsNotNone(ten_year["implicit_inflation"])
