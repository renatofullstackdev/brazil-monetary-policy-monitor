from __future__ import annotations

import math
import unittest

from brazil_monetary_policy_monitor.models.credit import real_balance_growth_percent


class CreditModelTests(unittest.TestCase):
    def test_real_growth_deflates_nominal_balance_growth(self) -> None:
        value = real_balance_growth_percent(110.0, 100.0, 5.0)
        self.assertAlmostEqual(value, (1.10 / 1.05 - 1.0) * 100.0, places=10)

    def test_zero_real_growth_when_nominal_balance_matches_inflation(self) -> None:
        self.assertAlmostEqual(real_balance_growth_percent(105.0, 100.0, 5.0), 0.0, places=10)

    def test_invalid_inputs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            real_balance_growth_percent(100.0, 0.0, 5.0)
        with self.assertRaises(ValueError):
            real_balance_growth_percent(math.inf, 100.0, 5.0)
        with self.assertRaises(ValueError):
            real_balance_growth_percent(100.0, 100.0, -100.0)


if __name__ == "__main__":
    unittest.main()
