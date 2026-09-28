"""Provider-independent term-structure transformations.

Rates use percentage points per year on the Brazilian 252-business-day basis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Iterable, Mapping

BUSINESS_DAYS_PER_YEAR = 252
ANBIMA_NOMINAL_CURVE = "anbima.pre"
ANBIMA_REAL_CURVE = "anbima.ipca"
ANBIMA_BREAKEVEN_CURVE = "anbima.breakeven"
B3_DI1_CURVE = "b3.di1"
STANDARD_TENORS_DU = (504, 756, 1260, 1764, 2520)


@dataclass(frozen=True, slots=True)
class MarketCurvePoint:
    curve_key: str
    reference_date: date
    point_key: str
    rate_percent: float
    tenor_business_days: int | None = None
    maturity_date: date | None = None
    instrument_key: str | None = None
    price_value: float | None = None

    @property
    def tenor_years(self) -> float | None:
        if self.tenor_business_days is None:
            return None
        return self.tenor_business_days / BUSINESS_DAYS_PER_YEAR


def discount_factor(rate_percent: float, tenor_business_days: int) -> float:
    rate = float(rate_percent) / 100.0
    if not math.isfinite(rate) or rate <= -1:
        raise ValueError("rate must be finite and greater than -100 percent")
    if tenor_business_days <= 0:
        raise ValueError("tenor_business_days must be positive")
    return (1.0 + rate) ** (-tenor_business_days / BUSINESS_DAYS_PER_YEAR)


def business_days_from_di_price(*, rate_percent: float, price_value: float) -> int:
    """Infer DI1 business-day tenor from its settlement price and annual rate."""

    rate = float(rate_percent) / 100.0
    price = float(price_value)
    if not math.isfinite(rate) or rate <= -1:
        raise ValueError("rate must be finite and greater than -100 percent")
    if not math.isfinite(price) or not 0 < price <= 100000:
        raise ValueError("DI1 price must be in (0, 100000]")
    if abs(rate) < 1e-15:
        if abs(price - 100000.0) < 1e-8:
            raise ValueError("cannot infer tenor from zero rate and par price")
        raise ValueError("zero rate is inconsistent with non-par DI1 price")
    raw = BUSINESS_DAYS_PER_YEAR * math.log(100000.0 / price) / math.log1p(rate)
    if not math.isfinite(raw) or raw <= 0:
        raise ValueError("DI1 price/rate imply a non-positive tenor")
    return max(1, round(raw))


def forward_rate_percent(left: MarketCurvePoint, right: MarketCurvePoint) -> float:
    if left.tenor_business_days is None or right.tenor_business_days is None:
        raise ValueError("forward calculation requires business-day tenors")
    if right.tenor_business_days <= left.tenor_business_days:
        raise ValueError("right tenor must be greater than left tenor")
    left_df = discount_factor(left.rate_percent, left.tenor_business_days)
    right_df = discount_factor(right.rate_percent, right.tenor_business_days)
    span = right.tenor_business_days - left.tenor_business_days
    return ((left_df / right_df) ** (BUSINESS_DAYS_PER_YEAR / span) - 1.0) * 100.0


def adjacent_forwards(points: Iterable[MarketCurvePoint]) -> list[dict[str, object]]:
    ordered = sorted(
        (point for point in points if point.tenor_business_days is not None),
        key=lambda point: int(point.tenor_business_days or 0),
    )
    result: list[dict[str, object]] = []
    for left, right in zip(ordered, ordered[1:]):
        assert left.tenor_business_days is not None and right.tenor_business_days is not None
        result.append(
            {
                "start_business_days": left.tenor_business_days,
                "end_business_days": right.tenor_business_days,
                "start_years": left.tenor_business_days / BUSINESS_DAYS_PER_YEAR,
                "end_years": right.tenor_business_days / BUSINESS_DAYS_PER_YEAR,
                "tenor_years": right.tenor_business_days / BUSINESS_DAYS_PER_YEAR,
                "rate_percent": forward_rate_percent(left, right),
                "start_instrument": left.instrument_key,
                "end_instrument": right.instrument_key,
            }
        )
    return result


def point_from_row(row: Mapping[str, object]) -> MarketCurvePoint:
    return MarketCurvePoint(
        curve_key=str(row["curve_key"]),
        reference_date=date.fromisoformat(str(row["reference_date"])),
        point_key=str(row["point_key"]),
        rate_percent=float(row["rate_percent"]),
        tenor_business_days=None if row["tenor_business_days"] is None else int(row["tenor_business_days"]),
        maturity_date=None if row["maturity_date"] is None else date.fromisoformat(str(row["maturity_date"])),
        instrument_key=None if row["instrument_key"] is None else str(row["instrument_key"]),
        price_value=None if row["price_value"] is None else float(row["price_value"]),
    )
