"""Pure monetary-policy calculations used by the backend and mirrored by the UI.

Rates and gaps are expressed in percentage points, not decimal fractions.
For example, 4.5 means 4.5%, not 0.045.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


CANONICAL_INFLATION_COEFFICIENT = 0.5
CANONICAL_OUTPUT_GAP_COEFFICIENT = 0.5


def _finite(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _coefficient(name: str, value: float) -> float:
    number = _finite(name, value)
    if number < 0:
        raise ValueError(f"{name} cannot be negative")
    return number


@dataclass(frozen=True, slots=True)
class TaylorDecomposition:
    """Additive components of a Taylor-rule result, in percentage points."""

    neutral_real_rate: float
    inflation: float
    inflation_gap_response: float
    output_gap_response: float

    @property
    def nominal_rate(self) -> float:
        return (
            self.neutral_real_rate
            + self.inflation
            + self.inflation_gap_response
            + self.output_gap_response
        )


@dataclass(frozen=True, slots=True)
class TaylorResult:
    """Result and transparent decomposition of a Taylor-rule calculation."""

    nominal_rate: float
    decomposition: TaylorDecomposition
    inflation_coefficient: float
    output_gap_coefficient: float


@dataclass(frozen=True, slots=True)
class InertialTaylorResult:
    """Partial adjustment from the previous policy rate toward a Taylor target."""

    nominal_rate: float
    previous_policy_component: float
    taylor_component: float
    smoothing: float
    underlying_taylor_rate: float


def taylor_rule(
    *,
    inflation: float,
    inflation_target: float,
    neutral_real_rate: float,
    output_gap: float,
    inflation_coefficient: float = CANONICAL_INFLATION_COEFFICIENT,
    output_gap_coefficient: float = CANONICAL_OUTPUT_GAP_COEFFICIENT,
) -> TaylorResult:
    """Calculate a transparent Taylor rule using percentage-point inputs."""

    inflation = _finite("inflation", inflation)
    inflation_target = _finite("inflation_target", inflation_target)
    neutral_real_rate = _finite("neutral_real_rate", neutral_real_rate)
    output_gap = _finite("output_gap", output_gap)
    inflation_coefficient = _coefficient(
        "inflation_coefficient", inflation_coefficient
    )
    output_gap_coefficient = _coefficient(
        "output_gap_coefficient", output_gap_coefficient
    )

    decomposition = TaylorDecomposition(
        neutral_real_rate=neutral_real_rate,
        inflation=inflation,
        inflation_gap_response=inflation_coefficient
        * (inflation - inflation_target),
        output_gap_response=output_gap_coefficient * output_gap,
    )
    return TaylorResult(
        nominal_rate=decomposition.nominal_rate,
        decomposition=decomposition,
        inflation_coefficient=inflation_coefficient,
        output_gap_coefficient=output_gap_coefficient,
    )


def classical_taylor(
    *,
    realized_inflation: float,
    inflation_target: float,
    neutral_real_rate: float,
    output_gap: float,
) -> TaylorResult:
    """Canonical Taylor benchmark using realized inflation and fixed 0.5/0.5 weights."""

    return taylor_rule(
        inflation=realized_inflation,
        inflation_target=inflation_target,
        neutral_real_rate=neutral_real_rate,
        output_gap=output_gap,
    )


def prospective_taylor(
    *,
    expected_inflation: float,
    inflation_target: float,
    neutral_real_rate: float,
    output_gap: float,
) -> TaylorResult:
    """Canonical Taylor benchmark using expected inflation at a chosen horizon."""

    return taylor_rule(
        inflation=expected_inflation,
        inflation_target=inflation_target,
        neutral_real_rate=neutral_real_rate,
        output_gap=output_gap,
    )


def inertial_taylor(
    *,
    previous_policy_rate: float,
    taylor_rate: float,
    smoothing: float,
) -> InertialTaylorResult:
    """Apply partial adjustment: rho*i[t-1] + (1-rho)*i_taylor."""

    previous_policy_rate = _finite("previous_policy_rate", previous_policy_rate)
    taylor_rate = _finite("taylor_rate", taylor_rate)
    smoothing = _finite("smoothing", smoothing)
    if not 0 <= smoothing <= 1:
        raise ValueError("smoothing must be between 0 and 1")

    previous_component = smoothing * previous_policy_rate
    taylor_component = (1 - smoothing) * taylor_rate
    return InertialTaylorResult(
        nominal_rate=previous_component + taylor_component,
        previous_policy_component=previous_component,
        taylor_component=taylor_component,
        smoothing=smoothing,
        underlying_taylor_rate=taylor_rate,
    )


def ex_ante_real_rate(*, nominal_rate: float, expected_inflation: float) -> float:
    """Return the V1 linear ex-ante real-rate approximation, in percentage points."""

    nominal_rate = _finite("nominal_rate", nominal_rate)
    expected_inflation = _finite("expected_inflation", expected_inflation)
    return nominal_rate - expected_inflation


def real_monetary_gap(*, ex_ante_rate: float, neutral_real_rate: float) -> float:
    """Distance between the ex-ante real rate and the estimated neutral real rate."""

    ex_ante_rate = _finite("ex_ante_rate", ex_ante_rate)
    neutral_real_rate = _finite("neutral_real_rate", neutral_real_rate)
    return ex_ante_rate - neutral_real_rate
