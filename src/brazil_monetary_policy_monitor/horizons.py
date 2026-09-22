"""Explicit policy-horizon metadata and horizon-aligned Focus transformations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from calendar import monthrange
from collections import defaultdict

from .collectors.bcb_focus import FocusMonthlyRecord


@dataclass(frozen=True, slots=True)
class PolicyHorizon:
    country: str
    year: int
    quarter: int
    effective_from: date
    source_label: str
    source_url: str

    @property
    def key(self) -> str:
        return f"{self.year}-Q{self.quarter}"

    @property
    def end_month(self) -> date:
        return date(self.year, self.quarter * 3, 1)

    @property
    def window_start(self) -> date:
        return _shift_month(self.end_month, -11)

    @property
    def window_end(self) -> date:
        last_day = monthrange(self.end_month.year, self.end_month.month)[1]
        return date(self.end_month.year, self.end_month.month, last_day)


@dataclass(frozen=True, slots=True)
class HorizonExpectation:
    survey_date: date
    horizon: PolicyHorizon
    value: Decimal
    component_months: tuple[date, ...]


def _shift_month(value: date, months: int) -> date:
    zero_based = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(zero_based, 12)
    return date(year, month_index + 1, 1)


def horizon_months(horizon: PolicyHorizon) -> tuple[date, ...]:
    return tuple(_shift_month(horizon.window_start, offset) for offset in range(12))


# Keep horizon changes explicit and source-backed instead of deriving them from a
# calendar rule. The Copom can move the relevant horizon as its policy window evolves.
BR_POLICY_HORIZONS: tuple[PolicyHorizon, ...] = (
    PolicyHorizon(
        country="BR",
        year=2027,
        quarter=4,
        effective_from=date(2026, 6, 18),
        source_label="279ª reunião do Copom — junho de 2026",
        source_url="https://www.bcb.gov.br/publicacoes/atascopom/17062026",
    ),
    PolicyHorizon(
        country="BR",
        year=2028,
        quarter=1,
        effective_from=date(2026, 8, 6),
        source_label="280ª reunião do Copom — agosto de 2026",
        source_url="https://www.bcb.gov.br/publicacoes/atascopom",
    ),
)


def resolve_br_policy_horizon(as_of: date) -> PolicyHorizon:
    eligible = [item for item in BR_POLICY_HORIZONS if item.effective_from <= as_of]
    if not eligible:
        raise LookupError(f"no BR policy horizon configured for {as_of.isoformat()}")
    return max(eligible, key=lambda item: item.effective_from)


def derive_horizon_expectations(
    records: list[FocusMonthlyRecord],
    *,
    horizon: PolicyHorizon,
) -> list[HorizonExpectation]:
    """Compound 12 monthly Focus medians ending at the policy-horizon quarter.

    This is a derived proxy. Compounding medians of monthly distributions is not
    mathematically identical to the median of institutions' cumulative 12-month
    forecasts, so callers must retain the derived provenance.
    """

    required = horizon_months(horizon)
    required_set = set(required)
    grouped: dict[date, dict[date, Decimal]] = defaultdict(dict)
    for record in records:
        if record.survey_date < horizon.effective_from:
            continue
        if record.target_month in required_set:
            grouped[record.survey_date][record.target_month] = record.median

    results: list[HorizonExpectation] = []
    hundred = Decimal("100")
    one = Decimal("1")
    for survey_date, values in sorted(grouped.items()):
        if any(month not in values for month in required):
            continue
        factor = one
        for month in required:
            factor *= one + values[month] / hundred
        annualized_window = (factor - one) * hundred
        results.append(
            HorizonExpectation(
                survey_date=survey_date,
                horizon=horizon,
                value=annualized_window,
                component_months=required,
            )
        )
    return results
