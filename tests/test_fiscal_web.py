from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FiscalWebTests(unittest.TestCase):
    def test_shell_exposes_fiscal_flow_debt_and_profile_sections(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="fiscal-chart"', html)
        self.assertIn('data-fiscal-mode="flows"', html)
        self.assertIn('data-fiscal-mode="debt"', html)
        self.assertIn('id="fiscal-profile-metrics"', html)
        self.assertIn('id="fiscal-composition"', html)

    def test_fiscal_contract_is_loaded_as_static_json(self) -> None:
        data = (ROOT / "web" / "js" / "data.js").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('./data/fiscal.json', data)
        self.assertIn('loadFiscal', app)
        self.assertNotIn('api.bcb.gov.br', data)

    def test_copy_keeps_dbgg_dpf_and_causality_distinct(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8").lower()
        view = (ROOT / "web" / "js" / "views" / "fiscal.js").read_text(encoding="utf-8").lower()
        self.assertIn("não atribui o resultado nominal exclusivamente à selic", html)
        self.assertIn("dpf e dbgg têm coberturas institucionais diferentes", html)
        self.assertIn("não deve ser confundida com a dpf", view)


if __name__ == "__main__":
    unittest.main()
