from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

FIXTURES = Path(__file__).with_name("fixtures")
SCENARIOS = json.loads(
    (FIXTURES / "monetary_model_scenarios.json").read_text(encoding="utf-8")
)["scenarios"]


from brazil_monetary_policy_monitor.models import (
    CANONICAL_INFLATION_COEFFICIENT,
    CANONICAL_OUTPUT_GAP_COEFFICIENT,
    classical_taylor,
    ex_ante_real_rate,
    inertial_taylor,
    prospective_taylor,
    real_monetary_gap,
    taylor_rule,
)


class TaylorRuleTests(unittest.TestCase):
    def test_canonical_coefficients_are_fixed_at_half(self) -> None:
        self.assertEqual(CANONICAL_INFLATION_COEFFICIENT, 0.5)
        self.assertEqual(CANONICAL_OUTPUT_GAP_COEFFICIENT, 0.5)

    def test_classical_taylor_matches_documented_additive_decomposition(self) -> None:
        scenario = SCENARIOS["classical"]
        result = classical_taylor(
            realized_inflation=scenario["realized_inflation"],
            inflation_target=scenario["inflation_target"],
            neutral_real_rate=scenario["neutral_real_rate"],
            output_gap=scenario["output_gap"],
        )

        self.assertAlmostEqual(result.decomposition.neutral_real_rate, 5.0)
        self.assertAlmostEqual(result.decomposition.inflation, 4.72)
        self.assertAlmostEqual(result.decomposition.inflation_gap_response, 0.86)
        self.assertAlmostEqual(result.decomposition.output_gap_response, 0.2)
        self.assertAlmostEqual(result.nominal_rate, scenario["expected_rate"])
        self.assertAlmostEqual(result.decomposition.nominal_rate, result.nominal_rate)

    def test_prospective_taylor_uses_expected_inflation_without_other_changes(self) -> None:
        scenario = SCENARIOS["prospective"]
        result = prospective_taylor(
            expected_inflation=scenario["expected_inflation"],
            inflation_target=scenario["inflation_target"],
            neutral_real_rate=scenario["neutral_real_rate"],
            output_gap=scenario["output_gap"],
        )

        self.assertAlmostEqual(result.nominal_rate, scenario["expected_rate"])
        self.assertAlmostEqual(result.decomposition.inflation_gap_response, 0.35)

    def test_lower_target_raises_taylor_rate_with_other_inputs_fixed(self) -> None:
        baseline = classical_taylor(
            realized_inflation=4.5,
            inflation_target=3.0,
            neutral_real_rate=5.0,
            output_gap=0.0,
        )
        lower_target = classical_taylor(
            realized_inflation=4.5,
            inflation_target=2.0,
            neutral_real_rate=5.0,
            output_gap=0.0,
        )

        self.assertAlmostEqual(lower_target.nominal_rate - baseline.nominal_rate, 0.5)

    def test_generic_rule_supports_explicit_noncanonical_coefficients(self) -> None:
        result = taylor_rule(
            inflation=4.0,
            inflation_target=3.0,
            neutral_real_rate=5.0,
            output_gap=2.0,
            inflation_coefficient=1.0,
            output_gap_coefficient=0.25,
        )

        self.assertAlmostEqual(result.nominal_rate, 10.5)
        self.assertEqual(result.inflation_coefficient, 1.0)
        self.assertEqual(result.output_gap_coefficient, 0.25)

    def test_negative_output_gap_reduces_rate(self) -> None:
        result = classical_taylor(
            realized_inflation=3.0,
            inflation_target=3.0,
            neutral_real_rate=5.0,
            output_gap=-2.0,
        )
        self.assertAlmostEqual(result.nominal_rate, 7.0)

    def test_nonfinite_inputs_are_rejected(self) -> None:
        for invalid in (math.nan, math.inf, -math.inf):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "inflation must be finite"):
                    classical_taylor(
                        realized_inflation=invalid,
                        inflation_target=3.0,
                        neutral_real_rate=5.0,
                        output_gap=0.0,
                    )

    def test_negative_response_coefficient_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            taylor_rule(
                inflation=4.0,
                inflation_target=3.0,
                neutral_real_rate=5.0,
                output_gap=0.0,
                inflation_coefficient=-0.5,
            )


class InertialTaylorTests(unittest.TestCase):
    def test_inertial_rule_decomposes_previous_and_target_components(self) -> None:
        scenario = SCENARIOS["inertial"]
        result = inertial_taylor(
            previous_policy_rate=scenario["previous_policy_rate"],
            taylor_rate=scenario["taylor_rate"],
            smoothing=scenario["smoothing"],
        )

        self.assertAlmostEqual(result.previous_policy_component, 9.0)
        self.assertAlmostEqual(result.taylor_component, 2.25)
        self.assertAlmostEqual(result.nominal_rate, scenario["expected_rate"])
        self.assertAlmostEqual(result.underlying_taylor_rate, 9.0)

    def test_smoothing_endpoints_have_clear_meaning(self) -> None:
        no_smoothing = inertial_taylor(
            previous_policy_rate=12.0,
            taylor_rate=9.0,
            smoothing=0.0,
        )
        full_smoothing = inertial_taylor(
            previous_policy_rate=12.0,
            taylor_rate=9.0,
            smoothing=1.0,
        )

        self.assertAlmostEqual(no_smoothing.nominal_rate, 9.0)
        self.assertAlmostEqual(full_smoothing.nominal_rate, 12.0)

    def test_smoothing_outside_unit_interval_is_rejected(self) -> None:
        for smoothing in (-0.01, 1.01):
            with self.subTest(smoothing=smoothing):
                with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                    inertial_taylor(
                        previous_policy_rate=12.0,
                        taylor_rate=9.0,
                        smoothing=smoothing,
                    )


class RealStanceTests(unittest.TestCase):
    def test_ex_ante_real_rate_uses_documented_linear_approximation(self) -> None:
        self.assertAlmostEqual(
            ex_ante_real_rate(nominal_rate=12.0, expected_inflation=4.2),
            7.8,
        )

    def test_real_monetary_gap_compares_real_rate_with_neutral_rate(self) -> None:
        self.assertAlmostEqual(
            real_monetary_gap(ex_ante_rate=7.8, neutral_real_rate=5.0),
            2.8,
        )

    def test_real_stance_rejects_nonfinite_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "nominal_rate must be finite"):
            ex_ante_real_rate(nominal_rate=math.inf, expected_inflation=4.0)
        with self.assertRaisesRegex(ValueError, "neutral_real_rate must be finite"):
            real_monetary_gap(ex_ante_rate=7.0, neutral_real_rate=math.nan)


if __name__ == "__main__":
    unittest.main()
