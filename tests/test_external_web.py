from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ExternalWebTests(unittest.TestCase):
    def test_shell_exposes_external_modes_and_history_ranges(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        for mode in ["fx_nominal", "fx_real", "external_balance", "portfolio", "reserves"]:
            self.assertIn(f'data-external-mode="{mode}"', html)
        for value in ["1", "3", "5", "10", "all"]:
            self.assertIn(f'data-external-range="{value}"', html)
        self.assertIn('id="external-chart"', html)
        self.assertIn('id="external-metrics"', html)

    def test_external_contract_is_loaded_from_static_json(self) -> None:
        data = (ROOT / "web" / "js" / "data.js").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('./data/external-sector.json', data)
        self.assertIn('payload.view !== "external_sector"', data)
        self.assertIn("loadExternalSector", app)
        self.assertNotIn("api.bcb.gov.br", app)

    def test_copy_rejects_fair_fx_and_single_cause_story(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8").lower()
        view = (ROOT / "web" / "js" / "views" / "external.js").read_text(encoding="utf-8").lower()
        publisher = (ROOT / "src" / "brazil_monetary_policy_monitor" / "publish" / "external.py").read_text(encoding="utf-8").lower()
        self.assertIn("não estima câmbio justo", html)
        self.assertIn("não atribui movimentos cambiais a uma única causa", view)
        self.assertIn("does not estimate a fair exchange rate", publisher)

    def test_external_metrics_use_shared_indicator_details_component(self) -> None:
        view = (ROOT / "web" / "js" / "views" / "external.js").read_text(encoding="utf-8")
        self.assertIn('from "../indicator_details.js"', view)
        self.assertIn("openIndicatorDetails", view)

    def test_external_layout_contains_long_labels_and_values(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "web" / "css" / "app.css").read_text(encoding="utf-8")
        view = (ROOT / "web" / "js" / "views" / "external.js").read_text(encoding="utf-8")
        chart = (ROOT / "web" / "js" / "charts" / "external.js").read_text(encoding="utf-8")

        self.assertIn("external-toolbar", html)
        self.assertIn("external-chart-panel", html)
        self.assertIn("external-metric", view)
        self.assertIn("axisValueFormatter", view)
        self.assertIn(".external-chart svg { overflow: hidden; }", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("const xIntervals = width < 520 ? 2 : 4;", chart)
        self.assertIn("const tooltipX = clamp", chart)


if __name__ == "__main__":
    unittest.main()
