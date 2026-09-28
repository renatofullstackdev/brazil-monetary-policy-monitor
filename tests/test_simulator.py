from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest

from brazil_monetary_policy_monitor.models.monetary import inertial_taylor, prospective_taylor, taylor_rule


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


class SimulatorShellTests(unittest.TestCase):
    def test_simulator_exposes_only_the_four_primary_controls(self) -> None:
        source = (ROOT / "web" / "js" / "views" / "simulator.js").read_text(encoding="utf-8")
        for key in (
            'key: "expected_inflation"',
            'key: "inflation_target"',
            'key: "neutral_real_rate"',
            'key: "output_gap"',
        ):
            self.assertIn(key, source)
        primary = source.split("const ADVANCED_DEFINITIONS", 1)[0]
        self.assertEqual(primary.count('key: "'), 4)
        for advanced_key in ('key: "alpha"', 'key: "beta"', 'key: "rho"', 'key: "previous_policy_rate"'):
            self.assertIn(advanced_key, source)

    def test_inertial_rule_uses_explicit_previous_policy_rate(self) -> None:
        source = (ROOT / "web" / "js" / "views" / "simulator.js").read_text(encoding="utf-8")
        self.assertIn('label: "Selic anterior (iₜ₋₁)"', source)
        self.assertIn("previousDistinctPolicyRate", source)
        self.assertIn("previousPolicyRate: previousRate", source)
        self.assertNotIn("previousPolicyRate: selic", source)

    def test_simulation_is_not_persisted_or_sent_to_a_backend(self) -> None:
        source = (ROOT / "web" / "js" / "views" / "simulator.js").read_text(encoding="utf-8")
        for forbidden in ("localStorage", "sessionStorage", "fetch(", "XMLHttpRequest", "indexedDB"):
            self.assertNotIn(forbidden, source)

    def test_accessible_simulator_landmarks_are_present(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        for marker in (
            'id="simulador-title"',
            'id="simulator-controls"',
            'id="simulator-reset"',
            'id="simulator-status"',
            'aria-live="polite"',
            'data-decomposition="total"',
        ):
            self.assertIn(marker, html)

    def test_missing_published_inputs_are_not_replaced_with_defaults(self) -> None:
        source = (ROOT / "web" / "js" / "views" / "simulator.js").read_text(encoding="utf-8")
        self.assertIn('number.value = ""', source)
        self.assertIn('"Base: indisponível"', source)
        self.assertNotIn("example", source.lower())
        self.assertNotIn("fixture", source.lower())


@unittest.skipUnless(NODE, "Node.js is optional; browser-model parity test skipped")
class SimulatorModelParityTests(unittest.TestCase):
    def test_javascript_model_matches_python_reference_scenarios(self) -> None:
        scenarios = [
            {
                "expectedInflation": 4.72,
                "inflationTarget": 3.0,
                "neutralRealRate": 5.0,
                "outputGap": 0.4,
            },
            {
                "expectedInflation": 3.0,
                "inflationTarget": 3.0,
                "neutralRealRate": 4.5,
                "outputGap": -1.2,
            },
            {
                "expectedInflation": 7.5,
                "inflationTarget": 4.0,
                "neutralRealRate": 2.25,
                "outputGap": 2.0,
            },
        ]

        javascript = """
import { prospectiveTaylor } from './web/js/models/taylor.js';
const scenarios = JSON.parse(process.argv[1]);
console.log(JSON.stringify(scenarios.map((scenario) => prospectiveTaylor(scenario))));
"""
        completed = subprocess.run(
            [NODE, "--input-type=module", "-e", javascript, json.dumps(scenarios)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        js_results = json.loads(completed.stdout)

        for scenario, js_result in zip(scenarios, js_results, strict=True):
            py_result = prospective_taylor(
                expected_inflation=scenario["expectedInflation"],
                inflation_target=scenario["inflationTarget"],
                neutral_real_rate=scenario["neutralRealRate"],
                output_gap=scenario["outputGap"],
            )
            self.assertAlmostEqual(js_result["nominalRate"], py_result.nominal_rate)
            self.assertAlmostEqual(
                js_result["decomposition"]["neutralRealRate"],
                py_result.decomposition.neutral_real_rate,
            )
            self.assertAlmostEqual(
                js_result["decomposition"]["inflation"],
                py_result.decomposition.inflation,
            )
            self.assertAlmostEqual(
                js_result["decomposition"]["inflationGapResponse"],
                py_result.decomposition.inflation_gap_response,
            )
            self.assertAlmostEqual(
                js_result["decomposition"]["outputGapResponse"],
                py_result.decomposition.output_gap_response,
            )


    def test_generic_coefficients_and_inertial_rule_match_python(self) -> None:
        scenario = {
            "inflation": 4.8,
            "inflationTarget": 3.0,
            "neutralRealRate": 4.5,
            "outputGap": -0.7,
            "inflationCoefficient": 0.8,
            "outputGapCoefficient": 0.3,
        }
        javascript = """
import { taylorRule, inertialTaylor } from './web/js/models/taylor.js';
const scenario = JSON.parse(process.argv[1]);
const rule = taylorRule(scenario);
const inertial = inertialTaylor({ previousPolicyRate: 14.5, taylorRate: rule.nominalRate, smoothing: 0.65 });
console.log(JSON.stringify({rule, inertial}));
"""
        completed = subprocess.run(
            [NODE, "--input-type=module", "-e", javascript, json.dumps(scenario)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        js = json.loads(completed.stdout)
        py_rule = taylor_rule(
            inflation=scenario["inflation"],
            inflation_target=scenario["inflationTarget"],
            neutral_real_rate=scenario["neutralRealRate"],
            output_gap=scenario["outputGap"],
            inflation_coefficient=scenario["inflationCoefficient"],
            output_gap_coefficient=scenario["outputGapCoefficient"],
        )
        py_inertial = inertial_taylor(previous_policy_rate=14.5, taylor_rate=py_rule.nominal_rate, smoothing=0.65)
        self.assertAlmostEqual(js["rule"]["nominalRate"], py_rule.nominal_rate)
        self.assertAlmostEqual(js["inertial"]["nominalRate"], py_inertial.nominal_rate)
        self.assertAlmostEqual(js["inertial"]["previousPolicyComponent"], py_inertial.previous_policy_component)
        self.assertAlmostEqual(js["inertial"]["taylorComponent"], py_inertial.taylor_component)


if __name__ == "__main__":
    unittest.main()
