from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CreditWebTests(unittest.TestCase):
    def test_shell_exposes_credit_modes_and_ranges(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="credit-chart"', html)
        self.assertIn('data-credit-mode="real_growth"', html)
        self.assertIn('data-credit-mode="interest_rates"', html)
        self.assertIn('data-credit-mode="delinquency"', html)
        self.assertIn('data-credit-range="5"', html)

    def test_credit_contract_is_loaded_from_static_json(self) -> None:
        data = (ROOT / "web" / "js" / "data.js").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('./data/credit-transmission.json', data)
        self.assertIn('loadCreditTransmission', app)
        self.assertNotIn('api.bcb.gov.br', data)

    def test_copy_preserves_noncausal_boundary(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8").lower()
        view = (ROOT / "web" / "js" / "views" / "credit.js").read_text(encoding="utf-8").lower()
        self.assertIn("não atribui causalidade exclusivamente à selic", html)
        self.assertIn("composição e risco", view)


if __name__ == "__main__":
    unittest.main()
