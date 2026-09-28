"""Explicit, source-backed Copom policy horizons and Focus transformations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from calendar import monthrange
from collections import defaultdict

from .collectors.bcb_focus import FocusMonthlyRecord


@dataclass(frozen=True, slots=True)
class PolicyHorizon:
    country: str
    year: int
    quarter: int
    meeting_end: date
    available_from: date
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
    available_on: date
    horizon: PolicyHorizon
    value: Decimal
    component_months: tuple[date, ...]


def _shift_month(value: date, months: int) -> date:
    zero_based = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(zero_based, 12)
    return date(year, month_index + 1, 1)


def horizon_months(horizon: PolicyHorizon) -> tuple[date, ...]:
    return tuple(_shift_month(horizon.window_start, offset) for offset in range(12))


def conservative_focus_available_on(survey_date: date) -> date:
    """Conservative upper knowledge boundary for historical Focus statistics.

    The BCB catalog documents weekly publication but the OData endpoint does not
    provide the historical publication timestamp. Adding seven calendar days
    deliberately avoids equating ``Data`` with public availability. This is a
    conservative proxy, not a claim about the exact release day.
    """

    return survey_date + timedelta(days=7)


# Horizon changes are explicit documentary facts. ``available_from`` is the
# publication date of the relevant Copom minute/report, not the meeting date.
# This prevents a historical model from using information before it was public.
BR_POLICY_HORIZONS: tuple[PolicyHorizon, ...] = (
    PolicyHorizon("BR", 2026, 1, date(2024, 9, 18), date(2024, 9, 24), "265ª reunião do Copom — setembro de 2024", "https://www.bcb.gov.br/publicacoes/atascopom/18092024"),
    PolicyHorizon("BR", 2026, 2, date(2024, 11, 6), date(2024, 11, 14), "266ª reunião do Copom — novembro de 2024", "https://www.bcb.gov.br/publicacoes/atascopom/06112024"),
    PolicyHorizon("BR", 2026, 3, date(2025, 1, 29), date(2025, 2, 4), "268ª reunião do Copom — janeiro de 2025", "https://www.bcb.gov.br/publicacoes/atascopom/29012025"),
    PolicyHorizon("BR", 2026, 4, date(2025, 5, 7), date(2025, 5, 13), "270ª reunião do Copom — maio de 2025", "https://www.bcb.gov.br/publicacoes/atascopom/07052025"),
    PolicyHorizon("BR", 2027, 1, date(2025, 7, 30), date(2025, 8, 5), "272ª reunião do Copom — julho de 2025", "https://www.bcb.gov.br/publicacoes/atascopom/30072025"),
    PolicyHorizon("BR", 2027, 2, date(2025, 11, 5), date(2025, 11, 11), "274ª reunião do Copom — novembro de 2025", "https://www.bcb.gov.br/publicacoes/atascopom/05112025"),
    PolicyHorizon("BR", 2027, 3, date(2026, 1, 28), date(2026, 2, 3), "276ª reunião do Copom — janeiro de 2026", "https://www.bcb.gov.br/publicacoes/atascopom/28012026"),
    PolicyHorizon("BR", 2027, 4, date(2026, 4, 29), date(2026, 5, 5), "278ª reunião do Copom — abril de 2026", "https://www.bcb.gov.br/publicacoes/atascopom/29042026"),
    PolicyHorizon("BR", 2028, 1, date(2026, 8, 5), date(2026, 8, 11), "280ª reunião do Copom — agosto de 2026", "https://www.bcb.gov.br/publicacoes/atascopom"),
)


def resolve_br_policy_horizon(as_of: date) -> PolicyHorizon:
    """Return the latest policy horizon known by ``as_of``."""

    eligible = [item for item in BR_POLICY_HORIZONS if item.available_from <= as_of]
    if not eligible:
        raise LookupError(f"no BR policy horizon configured for {as_of.isoformat()}")
    return max(eligible, key=lambda item: item.available_from)


def _compound_expectations(
    grouped: dict[date, dict[date, Decimal]], horizon: PolicyHorizon
) -> list[HorizonExpectation]:
    required = horizon_months(horizon)
    results: list[HorizonExpectation] = []
    hundred = Decimal("100")
    one = Decimal("1")
    for survey_date, values in sorted(grouped.items()):
        if any(month not in values for month in required):
            continue
        available_on = conservative_focus_available_on(survey_date)
        if resolve_br_policy_horizon(available_on).key != horizon.key:
            continue
        factor = one
        for month in required:
            factor *= one + values[month] / hundred
        results.append(HorizonExpectation(
            survey_date=survey_date,
            available_on=max(available_on, horizon.available_from),
            horizon=horizon,
            value=(factor - one) * hundred,
            component_months=required,
        ))
    return results


def derive_horizon_expectations(records: list[FocusMonthlyRecord], *, horizon: PolicyHorizon) -> list[HorizonExpectation]:
    """Compound 12 monthly Focus medians for one explicitly supplied horizon."""

    required_set = set(horizon_months(horizon))
    grouped: dict[date, dict[date, Decimal]] = defaultdict(dict)
    for record in records:
        if record.target_month in required_set:
            grouped[record.survey_date][record.target_month] = record.median
    return _compound_expectations(grouped, horizon)


def derive_historical_horizon_expectations(records: list[FocusMonthlyRecord]) -> list[HorizonExpectation]:
    """Reconstruct the Focus proxy using the horizon known when each vintage became available."""

    by_survey: dict[date, list[FocusMonthlyRecord]] = defaultdict(list)
    for record in records:
        by_survey[record.survey_date].append(record)

    results: list[HorizonExpectation] = []
    for survey_date, survey_records in sorted(by_survey.items()):
        available_on = conservative_focus_available_on(survey_date)
        try:
            horizon = resolve_br_policy_horizon(available_on)
        except LookupError:
            continue
        values = {record.target_month: record.median for record in survey_records}
        required = horizon_months(horizon)
        if any(month not in values for month in required):
            continue
        hundred = Decimal("100")
        factor = Decimal("1")
        for month in required:
            factor *= Decimal("1") + values[month] / hundred
        results.append(HorizonExpectation(
            survey_date=survey_date,
            available_on=max(available_on, horizon.available_from),
            horizon=horizon,
            value=(factor - Decimal("1")) * hundred,
            component_months=required,
        ))
    return results
