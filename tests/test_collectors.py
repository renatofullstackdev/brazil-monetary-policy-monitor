from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import unittest

from brazil_monetary_policy_monitor.collectors.bcb_sgs import (
    build_sgs_url,
    iter_date_windows,
    parse_sgs_json,
)


FIXTURES = Path(__file__).with_name("fixtures")


class SGSCollectorTests(unittest.TestCase):
    def test_parse_valid_payload(self) -> None:
        records = parse_sgs_json((FIXTURES / "sgs_432_sample.json").read_bytes())

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].reference_date, date(2026, 9, 1))
        self.assertEqual(records[0].value, Decimal("15.00"))
        self.assertEqual(records[-1].value, Decimal("14.75"))

    def test_parse_rejects_duplicate_dates(self) -> None:
        payload = b'[{"data":"01/09/2026","valor":"15.00"},{"data":"01/09/2026","valor":"14.75"}]'
        with self.assertRaisesRegex(ValueError, "duplicate reference date"):
            parse_sgs_json(payload)

    def test_parse_rejects_invalid_shape(self) -> None:
        with self.assertRaisesRegex(ValueError, "root must be a JSON array"):
            parse_sgs_json(b'{"data":"01/09/2026","valor":"15.00"}')

    def test_historical_range_is_split_into_provider_safe_windows(self) -> None:
        windows = iter_date_windows(date(1999, 3, 5), date(2026, 9, 22))

        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0], (date(1999, 3, 5), date(2009, 3, 4)))
        self.assertEqual(windows[1], (date(2009, 3, 5), date(2019, 3, 4)))
        self.assertEqual(windows[2], (date(2019, 3, 5), date(2026, 9, 22)))
        for previous, current in zip(windows, windows[1:]):
            self.assertEqual(previous[1] + timedelta(days=1), current[0])

    def test_url_contains_explicit_date_filters(self) -> None:
        url = build_sgs_url(432, date(2026, 9, 1), date(2026, 9, 22))

        self.assertIn("bcdata.sgs.432", url)
        self.assertIn("dataInicial=01%2F09%2F2026", url)
        self.assertIn("dataFinal=22%2F09%2F2026", url)
        self.assertIn("formato=json", url)


if __name__ == "__main__":
    unittest.main()
