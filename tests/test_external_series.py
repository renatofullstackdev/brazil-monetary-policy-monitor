from __future__ import annotations

import unittest

from brazil_monetary_policy_monitor.external_series import (
    EXTERNAL_DAILY_SERIES,
    EXTERNAL_MONTHLY_SERIES,
    EXTERNAL_SERIES,
    EXTERNAL_SERIES_BY_CODE,
)


class ExternalSeriesRegistryTests(unittest.TestCase):
    def test_registry_uses_expected_official_sgs_codes(self) -> None:
        self.assertEqual(
            set(EXTERNAL_SERIES_BY_CODE),
            {1, 11752, 23079, 23080, 22924, 13982},
        )

    def test_registry_keeps_daily_and_monthly_frequencies_explicit(self) -> None:
        self.assertEqual({spec.code for spec in EXTERNAL_DAILY_SERIES}, {1, 13982})
        self.assertEqual(
            {spec.code for spec in EXTERNAL_MONTHLY_SERIES},
            {11752, 23079, 23080, 22924},
        )
        self.assertTrue(all(spec.data_kind == "observed" for spec in EXTERNAL_SERIES))


if __name__ == "__main__":
    unittest.main()
