"""Pure transformations for offered-title yield-curve proxies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Iterable, Mapping, Sequence

from ..collectors.tesouro_direto import NOMINAL_INSTRUMENT_TYPES, REAL_INSTRUMENT_TYPES


DAYS_PER_YEAR = 365.2425
FIXED_TENORS = (2.0, 3.0, 5.0, 7.0, 10.0)


@dataclass(frozen=True, slots=True)
class CurvePoint:
    tenor_years: float
    yield_percent: float
    maturity_date: str
    instrument_type: str


def years_to_maturity(reference_date: date, maturity_date: date) -> float:
    if maturity_date <= reference_date:
        raise ValueError("maturity date must be after reference date")
    return (maturity_date - reference_date).days / DAYS_PER_YEAR


def fisher_breakeven(nominal_percent: float, real_percent: float) -> float:
    """Return the exact Fisher-implied inflation proxy in percentage points."""

    nominal = float(nominal_percent)
    real = float(real_percent)
    if not isfinite(nominal) or not isfinite(real):
        raise ValueError("rates must be finite")
    if nominal <= -100 or real <= -100:
        raise ValueError("rates must be greater than -100 percent")
    return ((1.0 + nominal / 100.0) / (1.0 + real / 100.0) - 1.0) * 100.0


def interpolate_curve(points: Sequence[CurvePoint], tenor_years: float) -> float | None:
    """Linearly interpolate a yield inside the observed maturity range only."""

    target = float(tenor_years)
    if not isfinite(target) or target <= 0:
        raise ValueError("tenor must be a positive finite number")
    ordered = sorted(points, key=lambda point: point.tenor_years)
    if not ordered or target < ordered[0].tenor_years or target > ordered[-1].tenor_years:
        return None
    for point in ordered:
        if abs(point.tenor_years - target) < 1e-12:
            return point.yield_percent
    for left, right in zip(ordered, ordered[1:]):
        if left.tenor_years < target < right.tenor_years:
            span = right.tenor_years - left.tenor_years
            weight = (target - left.tenor_years) / span
            return left.yield_percent + weight * (right.yield_percent - left.yield_percent)
    return None


def _prefer_instrument(existing: CurvePoint, candidate: CurvePoint) -> CurvePoint:
    """Prefer principal-at-maturity variants when two quotes share a maturity."""

    coupon_marker = "com Juros Semestrais"
    existing_coupon = coupon_marker in existing.instrument_type
    candidate_coupon = coupon_marker in candidate.instrument_type
    if existing_coupon and not candidate_coupon:
        return candidate
    return existing


def curve_points_from_rows(rows: Iterable[Mapping[str, object]], *, kind: str) -> list[CurvePoint]:
    allowed = NOMINAL_INSTRUMENT_TYPES if kind == "nominal" else REAL_INSTRUMENT_TYPES if kind == "real" else None
    if allowed is None:
        raise ValueError(f"unsupported curve kind: {kind}")
    by_maturity: dict[str, CurvePoint] = {}
    for row in rows:
        instrument_type = str(row["instrument_type"])
        if instrument_type not in allowed or row["buy_yield"] is None:
            continue
        reference = date.fromisoformat(str(row["reference_date"]))
        maturity = date.fromisoformat(str(row["maturity_date"]))
        point = CurvePoint(
            tenor_years=years_to_maturity(reference, maturity),
            yield_percent=float(row["buy_yield"]),
            maturity_date=maturity.isoformat(),
            instrument_type=instrument_type,
        )
        existing = by_maturity.get(point.maturity_date)
        by_maturity[point.maturity_date] = point if existing is None else _prefer_instrument(existing, point)
    return sorted(by_maturity.values(), key=lambda point: point.tenor_years)


def build_curve_snapshot(rows: Sequence[Mapping[str, object]], *, requested_date: date | None = None) -> dict[str, object] | None:
    """Build one date snapshot using the latest trading day on/before the request."""

    if not rows:
        return None
    dates = sorted({date.fromisoformat(str(row["reference_date"])) for row in rows})
    target = requested_date or dates[-1]
    eligible = [candidate for candidate in dates if candidate <= target]
    if not eligible:
        return None
    effective = eligible[-1]
    selected = [row for row in rows if str(row["reference_date"]) == effective.isoformat()]
    nominal = curve_points_from_rows(selected, kind="nominal")
    real = curve_points_from_rows(selected, kind="real")

    tenors: list[dict[str, float | None]] = []
    for tenor in FIXED_TENORS:
        nominal_value = interpolate_curve(nominal, tenor)
        real_value = interpolate_curve(real, tenor)
        implicit = None
        if nominal_value is not None and real_value is not None:
            implicit = fisher_breakeven(nominal_value, real_value)
        tenors.append(
            {
                "tenor_years": tenor,
                "nominal": nominal_value,
                "real": real_value,
                "implicit_inflation": implicit,
            }
        )

    def slope(field: str) -> float | None:
        two = next((item[field] for item in tenors if item["tenor_years"] == 2.0), None)
        ten = next((item[field] for item in tenors if item["tenor_years"] == 10.0), None)
        if two is None or ten is None:
            return None
        return float(ten) - float(two)

    return {
        "requested_date": target.isoformat(),
        "effective_date": effective.isoformat(),
        "nominal": [point.__dict__ if hasattr(point, "__dict__") else {
            "tenor_years": point.tenor_years,
            "yield_percent": point.yield_percent,
            "maturity_date": point.maturity_date,
            "instrument_type": point.instrument_type,
        } for point in nominal],
        "real": [point.__dict__ if hasattr(point, "__dict__") else {
            "tenor_years": point.tenor_years,
            "yield_percent": point.yield_percent,
            "maturity_date": point.maturity_date,
            "instrument_type": point.instrument_type,
        } for point in real],
        "tenors": tenors,
        "slopes": {
            "nominal_10y_minus_2y": slope("nominal"),
            "real_10y_minus_2y": slope("real"),
            "implicit_10y_minus_2y": slope("implicit_inflation"),
        },
    }
