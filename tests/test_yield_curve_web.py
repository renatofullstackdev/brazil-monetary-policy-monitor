from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class YieldCurveWebTests(unittest.TestCase):
    def test_shell_exposes_curve_family_and_comparison_controls(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="yield-curve-chart"', html)
        self.assertIn('data-curve-kind="nominal"', html)
        self.assertIn('data-curve-kind="real"', html)
        self.assertIn('data-curve-kind="implicit"', html)
        self.assertIn('value="one_month"', html)
        self.assertIn('value="one_year"', html)
        self.assertIn('value="previous_copom"', html)
        self.assertIn('value="custom"', html)

    def test_copy_does_not_call_breakeven_a_pure_inflation_expectation(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8").lower()
        view = (ROOT / "web" / "js" / "views" / "yield_curve.js").read_text(encoding="utf-8").lower()
        self.assertIn("não é uma curva zero-cupom", html)
        self.assertIn("não equivale a expectativa pura", view)

    def test_curve_contract_is_loaded_from_static_json_not_backend_api(self) -> None:
        data = (ROOT / "web" / "js" / "data.js").read_text(encoding="utf-8")
        self.assertIn('./data/yield-curve.json', data)
        self.assertNotIn("api.bcb.gov.br", data)
        self.assertNotIn("tesourotransparente.gov.br", data)
