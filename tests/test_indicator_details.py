from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class IndicatorDetailsTests(unittest.TestCase):
    def test_all_metric_modules_use_shared_indicator_details_component(self) -> None:
        modules = [
            ROOT / "web/js/views/overview.js",
            ROOT / "web/js/views/credit.js",
            ROOT / "web/js/views/fiscal.js",
            ROOT / "web/js/views/yield_curve.js",
        ]
        for path in modules:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn("openIndicatorDetails", source)

    def test_details_component_exposes_history_only_from_real_observations(self) -> None:
        source = (ROOT / "web/js/indicator_details.js").read_text(encoding="utf-8")
        self.assertIn('indicator.observations.length >= 2', source)
        self.assertIn('Ver série histórica', source)
        self.assertIn('Série histórica ainda não publicada para este indicador', source)
        self.assertIn('data-indicator-range', source)
        self.assertNotIn('localStorage', source)
        self.assertNotIn('fetch(', source)

    def test_rmd_cards_explain_why_history_is_not_fabricated(self) -> None:
        source = (ROOT / "web/js/views/fiscal.js").read_text(encoding="utf-8")
        self.assertIn("snapshot documental", source)
        self.assertIn("séries históricas oficiais do Tesouro", source)

    def test_yield_curve_cards_build_history_from_anbima_snapshots(self) -> None:
        source = (ROOT / "web/js/views/yield_curve.js").read_text(encoding="utf-8")
        self.assertIn("curve.history", source)
        self.assertIn("curveHistory", source)
        self.assertIn("Detalhes e histórico", source)
        self.assertNotIn("Histórico legado", source)

    def test_macro_overview_publishes_available_histories(self) -> None:
        source = (ROOT / "src/brazil_monetary_policy_monitor/publish/overview.py").read_text(encoding="utf-8")
        self.assertIn('"observations": history', source)
        self.assertIn('for row in rows', source)
        self.assertIn('variações percentuais mensais acumuladas dos últimos 12 meses', source)


class SeriesIdentityTests(unittest.TestCase):
    def test_palette_has_distinct_persistent_series_tokens(self) -> None:
        css = (ROOT / "web/css/app.css").read_text(encoding="utf-8")
        for marker in ("--series-1:", "--series-2:", "--series-3:", "--series-4:"):
            self.assertIn(marker, css)
        self.assertIn(".chart .fiscal-series-1", css)
        self.assertIn(".chart .fiscal-series-2", css)
        self.assertIn(".chart .fiscal-series-3", css)
        self.assertIn("stroke-dasharray", css)

    def test_fiscal_legend_uses_same_series_identity_classes_as_chart(self) -> None:
        source = (ROOT / "web/js/views/fiscal.js").read_text(encoding="utf-8")
        self.assertIn("legend-series-${index + 1}", source)
        chart = (ROOT / "web/js/charts/fiscal.js").read_text(encoding="utf-8")
        self.assertIn("fiscal-series-${index + 1}", chart)


if __name__ == "__main__":
    unittest.main()
