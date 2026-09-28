from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class YieldCurveWebTests(unittest.TestCase):
    def test_shell_exposes_curve_family_and_comparison_controls(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="yield-curve-chart"', html)
        self.assertIn('data-curve-family="ettj"', html)
        self.assertIn('data-curve-family="di"', html)
        self.assertNotIn('data-curve-family="legacy"', html)
        self.assertIn('data-curve-kind="nominal"', html)
        self.assertIn('data-curve-kind="real"', html)
        self.assertIn('data-curve-kind="implicit"', html)
        self.assertIn('data-di-mode="rates"', html)
        self.assertIn('data-di-mode="forwards"', html)
        self.assertIn('id="yield-curve-guide"', html)
        self.assertIn('id="yield-curve-family-status"', html)
        self.assertIn('value="one_month"', html)
        self.assertIn('value="one_year"', html)
        self.assertIn('value="previous_copom"', html)
        self.assertIn('value="custom"', html)

    def test_copy_explains_how_to_read_di_and_breakeven(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8").lower()
        view = (ROOT / "web" / "js" / "views" / "yield_curve.js").read_text(encoding="utf-8").lower()
        self.assertIn("mercado está precificando juros menores ou maiores", html)
        self.assertIn("taxa até o vencimento", html)
        self.assertIn("taxa entre vencimentos", html)
        self.assertIn("não equivale a expectativa pura", view)
        self.assertIn("não deve ser lido como previsão pontual da selic", view)
        self.assertIn("selic atual", view)

    def test_unavailable_family_is_selectable_for_diagnostics(self) -> None:
        view = (ROOT / "web" / "js" / "views" / "yield_curve.js").read_text(encoding="utf-8")
        self.assertIn('button.disabled = false', view)
        self.assertIn('aria-disabled', view)
        self.assertIn('Selecione para ver o motivo da indisponibilidade.', view)
        self.assertIn('last_ingestion', view)

    def test_ingestion_diagnostics_do_not_leak_internal_status_or_error_message(self) -> None:
        view = (ROOT / "web" / "js" / "views" / "yield_curve.js").read_text(encoding="utf-8")
        self.assertIn("Última coleta parcialmente concluída", view)
        self.assertIn("A última coleta falhou", view)
        self.assertIn("A última coleta terminou parcialmente", view)
        self.assertNotIn("${run.status}", view)
        self.assertNotIn("run.message", view)

    def test_hidden_curve_controls_have_author_css_guard(self) -> None:
        css = (ROOT / "web" / "css" / "app.css").read_text(encoding="utf-8")
        self.assertIn('#curve-di-mode-controls[hidden]', css)
        self.assertIn('display: none !important;', css)

    def test_curve_contract_is_loaded_from_static_json_not_backend_api(self) -> None:
        data = (ROOT / "web" / "js" / "data.js").read_text(encoding="utf-8")
        self.assertIn('./data/yield-curve.json', data)
        self.assertNotIn("api.bcb.gov.br", data)
        self.assertNotIn("tesourotransparente.gov.br", data)
