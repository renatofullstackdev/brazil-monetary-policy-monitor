from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


class AnalyticalUXShellTests(unittest.TestCase):
    def test_sections_follow_the_analysis_sequence(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        markers = [
            'id="situacao-title"',
            'id="contexto-title"',
            'id="simulador-title"',
            'id="historico-title"',
            'id="curva-title"',
            'id="credito-title"',
            'id="fiscal-title"',
            'id="external-title"',
            'id="us-title"',
            'id="explorer-title"',
            'id="copom-title"',
        ]
        positions = [html.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_primary_surface_is_question_driven_and_uses_portuguese_labels(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('aria-label="Perguntas de análise"', html)
        self.assertIn("Como a Selic se compara às referências?", html)
        self.assertIn("O que precisaria mudar para essa leitura mudar?", html)
        self.assertIn("Como dois indicadores se movem juntos?", html)
        self.assertNotIn("Brazil Monetary Policy Monitor", html)
        self.assertNotIn(">Vintage<", html)
        self.assertNotIn(">Treasuries<", html)
        self.assertNotIn("snapshot documental", html)

    def test_progressive_disclosure_limits_policy_communication_by_default(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        view = (ROOT / "web" / "js" / "views" / "copom.js").read_text(encoding="utf-8")
        css = (ROOT / "web" / "css" / "app.css").read_text(encoding="utf-8")
        self.assertIn('id="copom-recent-toggle"', html)
        self.assertIn('id="copom-upcoming-toggle"', html)
        self.assertIn("RECENT_LIMIT = 4", view)
        self.assertIn("UPCOMING_LIMIT = 3", view)
        self.assertIn("policy-event-list-expanded", css)
        self.assertIn("overflow-y: auto", css)

    def test_sensitivity_curve_change_fiscal_reconciliation_and_relation_explorer_exist(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        yield_view = (ROOT / "web" / "js" / "views" / "yield_curve.js").read_text(encoding="utf-8")
        fiscal_view = (ROOT / "web" / "js" / "views" / "fiscal.js").read_text(encoding="utf-8")
        external_view = (ROOT / "web" / "js" / "views" / "external.js").read_text(encoding="utf-8")
        for marker in (
            'id="simulator-sensitivity"',
            'id="simulator-advanced-controls"',
            'data-curve-view="changes"',
            'id="fiscal-reconciliation"',
            'id="explorer-series-a"',
            'id="explorer-series-b"',
            'data-explorer-view="scatter"',
        ):
            self.assertIn(marker, html)
        self.assertIn("renderYieldCurveDeltaChart", yield_view)
        self.assertIn("renderFiscalReconciliation", fiscal_view)
        self.assertIn('geometry: mode === "portfolio" ? "bar" : "line"', external_view)

    def test_relation_explorer_keeps_noncausal_boundary_visible(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8").lower()
        view = (ROOT / "web" / "js" / "views" / "explorer.js").read_text(encoding="utf-8").lower()
        self.assertIn("não implica causalidade", html)
        self.assertIn("não causalidade", view)
        self.assertNotIn("r²", view)
        self.assertNotIn("regression", view)


@unittest.skipUnless(NODE, "Node.js is optional; relation-transform tests skipped")
class RelationshipExplorerTransformTests(unittest.TestCase):
    def run_js(self, script: str, payload: object) -> object:
        completed = subprocess.run(
            [NODE, "--input-type=module", "-e", script, json.dumps(payload)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_monthly_series_uses_last_observation_in_each_month(self) -> None:
        script = """
import { monthlySeries } from './web/js/views/explorer.js';
console.log(JSON.stringify(monthlySeries(JSON.parse(process.argv[1]))));
"""
        result = self.run_js(script, [
            {"date": "2026-01-02", "value": 10},
            {"date": "2026-01-31", "value": 11},
            {"date": "2026-02-15", "value": 12},
        ])
        self.assertEqual(result, [
            {"date": "2026-01", "value": 11},
            {"date": "2026-02", "value": 12},
        ])

    def test_index_100_uses_first_common_month_after_lag(self) -> None:
        script = """
import { monthlySeries, lagSeries, rebaseToCommonStart } from './web/js/views/explorer.js';
const payload = JSON.parse(process.argv[1]);
const a = monthlySeries(payload.a);
const b = lagSeries(monthlySeries(payload.b), payload.lag);
console.log(JSON.stringify(rebaseToCommonStart(a, b)));
"""
        result = self.run_js(script, {
            "lag": 1,
            "a": [
                {"date": "2026-01-31", "value": 20},
                {"date": "2026-02-28", "value": 22},
                {"date": "2026-03-31", "value": 24},
            ],
            "b": [
                {"date": "2025-12-31", "value": 50},
                {"date": "2026-01-31", "value": 55},
                {"date": "2026-02-28", "value": 60},
            ],
        })
        self.assertEqual(result[0][0], {"date": "2026-01", "value": 100})
        self.assertEqual(result[1][0], {"date": "2026-01", "value": 100})
        self.assertAlmostEqual(result[0][-1]["value"], 120)
        self.assertAlmostEqual(result[1][-1]["value"], 120)

    def test_change_12m_is_an_absolute_change_in_the_original_unit(self) -> None:
        script = """
import { transformSeries } from './web/js/views/explorer.js';
console.log(JSON.stringify(transformSeries(JSON.parse(process.argv[1]), 'change12m')));
"""
        result = self.run_js(script, [
            {"date": "2025-01-31", "value": 5.0},
            {"date": "2026-01-31", "value": 6.25},
        ])
        self.assertEqual(result, [{"date": "2026-01", "value": 1.25}])

    def test_pair_series_requires_exact_aligned_months(self) -> None:
        script = """
import { pairSeries } from './web/js/views/explorer.js';
const payload = JSON.parse(process.argv[1]);
console.log(JSON.stringify(pairSeries(payload.a, payload.b)));
"""
        result = self.run_js(script, {
            "a": [{"date": "2026-01", "value": 1}, {"date": "2026-02", "value": 2}],
            "b": [{"date": "2026-02", "value": 20}, {"date": "2026-03", "value": 30}],
        })
        self.assertEqual(result, [{"date": "2026-02", "a": 2, "b": 20}])


if __name__ == "__main__":
    unittest.main()
