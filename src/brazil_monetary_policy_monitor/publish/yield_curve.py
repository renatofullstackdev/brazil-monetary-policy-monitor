"""Publish static sovereign-curve, ANBIMA ETTJ and B3 DI1 contracts."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3

from ..ingestion.market_curves import ANBIMA_ETTJ_SOURCE_KEY, B3_DI1_SOURCE_KEY
from ..db.events import events_as_known, events_latest
from ..models.term_structure import (
    ANBIMA_BREAKEVEN_CURVE,
    ANBIMA_NOMINAL_CURVE,
    ANBIMA_REAL_CURVE,
    B3_DI1_CURVE,
    BUSINESS_DAYS_PER_YEAR,
    STANDARD_TENORS_DU,
    adjacent_forwards,
    point_from_row,
)
from ..vintages import build_knowledge_context, market_curve_rows
from .atomic import write_json_atomic




def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _months_before(value: date, months: int) -> date:
    total = value.year * 12 + (value.month - 1) - months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _source(connection: sqlite3.Connection, key: str, *, required: bool = False) -> sqlite3.Row | None:
    row = connection.execute("SELECT * FROM sources WHERE key = ?", (key,)).fetchone()
    if row is None and required:
        raise LookupError(f"source metadata is not registered: {key}")
    return row


def _source_contract(row: sqlite3.Row | None) -> dict[str, object] | None:
    if row is None:
        return None
    metadata = json.loads(row["metadata_json"] or "{}")
    return {
        "provider": row["provider"],
        "name": row["name"],
        "url": row["url"],
        "documentation_url": row["documentation_url"],
        "license": row["license"],
        "metadata": metadata,
    }


def _last_ingestion_contract(connection: sqlite3.Connection, source_id: int) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT status, finished_at, records_received, records_inserted, records_unchanged, error_json
        FROM ingestion_runs
        WHERE source_id = ? AND status <> 'running'
        ORDER BY id DESC
        LIMIT 1
        """,
        (source_id,),
    ).fetchone()
    if row is None:
        return None
    message = None
    if row["error_json"]:
        try:
            error = json.loads(row["error_json"])
            message = error.get("message")
            if not message and error.get("skipped"):
                first = error["skipped"][0]
                message = first.get("reason") if isinstance(first, dict) else None
        except (TypeError, ValueError, json.JSONDecodeError):
            message = None
    return {
        "status": row["status"],
        "finished_at": row["finished_at"],
        "records_received": int(row["records_received"]),
        "records_inserted": int(row["records_inserted"]),
        "records_unchanged": int(row["records_unchanged"]),
        "message": message,
    }


def _previous_copom_date(connection: sqlite3.Connection, before: date, *, knowledge_cutoff: str | None = None) -> date | None:
    rows = events_latest(connection) if knowledge_cutoff is None else events_as_known(connection, knowledge_cutoff)
    candidates = [
        date.fromisoformat(str(row["occurred_at"])[:10])
        for row in rows
        if row["event_type"] == "copom_decision"
        and date.fromisoformat(str(row["occurred_at"])[:10]) < before
    ]
    return max(candidates) if candidates else None


def _linear_value(rows: list[sqlite3.Row], target_du: int) -> float | None:
    points = sorted(
        ((int(row["tenor_business_days"]), float(row["rate_percent"])) for row in rows if row["tenor_business_days"] is not None),
        key=lambda item: item[0],
    )
    if not points or target_du < points[0][0] or target_du > points[-1][0]:
        return None
    for du, value in points:
        if du == target_du:
            return value
    for (left_du, left_value), (right_du, right_value) in zip(points, points[1:]):
        if left_du < target_du < right_du:
            weight = (target_du - left_du) / (right_du - left_du)
            return left_value + weight * (right_value - left_value)
    return None


def _ettj_snapshot(rows: list[sqlite3.Row], *, include_points: bool) -> dict[str, object] | None:
    if not rows:
        return None
    reference = str(rows[0]["reference_date"])
    by_curve = {
        key: [row for row in rows if str(row["curve_key"]) == key]
        for key in (ANBIMA_NOMINAL_CURVE, ANBIMA_REAL_CURVE, ANBIMA_BREAKEVEN_CURVE)
    }
    field_by_key = {
        ANBIMA_NOMINAL_CURVE: "nominal",
        ANBIMA_REAL_CURVE: "real",
        ANBIMA_BREAKEVEN_CURVE: "implicit_inflation",
    }
    tenors: list[dict[str, object]] = []
    for tenor_du in STANDARD_TENORS_DU:
        row: dict[str, object] = {"tenor_years": tenor_du / BUSINESS_DAYS_PER_YEAR, "tenor_business_days": tenor_du}
        for curve_key, field in field_by_key.items():
            row[field] = _linear_value(by_curve[curve_key], tenor_du)
        tenors.append(row)

    def slope(field: str) -> float | None:
        two = next((item[field] for item in tenors if item["tenor_business_days"] == 504), None)
        ten = next((item[field] for item in tenors if item["tenor_business_days"] == 2520), None)
        return None if two is None or ten is None else float(ten) - float(two)

    result: dict[str, object] = {
        "requested_date": reference,
        "effective_date": reference,
        "tenors": tenors,
        "slopes": {
            "nominal_10y_minus_2y": slope("nominal"),
            "real_10y_minus_2y": slope("real"),
            "implicit_10y_minus_2y": slope("implicit_inflation"),
        },
    }
    if include_points:
        for curve_key, field in field_by_key.items():
            result[field if field != "implicit_inflation" else "implicit"] = [
                {
                    "tenor_business_days": int(row["tenor_business_days"]),
                    "tenor_years": int(row["tenor_business_days"]) / BUSINESS_DAYS_PER_YEAR,
                    "yield_percent": float(row["rate_percent"]),
                }
                for row in by_curve[curve_key]
                if row["tenor_business_days"] is not None
            ]
    return result


def _ettj_contract(connection: sqlite3.Connection, context) -> dict[str, object]:
    source = _source(connection, ANBIMA_ETTJ_SOURCE_KEY)
    if source is None:
        return {"status": "unavailable", "source": None, "latest": None, "history": [], "presets": {}, "last_ingestion": None}
    rows = market_curve_rows(connection, source_id=int(source["id"]), context=context)
    by_date: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_date.setdefault(str(row["reference_date"]), []).append(row)
    dates = sorted(by_date)
    history = [snapshot for current in dates if (snapshot := _ettj_snapshot(by_date[current], include_points=False))]
    latest = _ettj_snapshot(by_date[dates[-1]], include_points=True) if dates else None

    def on_or_before(requested: date) -> dict[str, object] | None:
        eligible = [value for value in dates if value <= requested.isoformat()]
        if not eligible:
            return None
        snapshot = _ettj_snapshot(by_date[eligible[-1]], include_points=False)
        if snapshot:
            snapshot["requested_date"] = requested.isoformat()
        return snapshot

    presets: dict[str, object] = {"latest": latest, "one_month": None, "one_year": None, "previous_copom": {"status": "unavailable"}}
    if latest is not None:
        latest_date = date.fromisoformat(str(latest["effective_date"]))
        presets["one_month"] = on_or_before(_months_before(latest_date, 1))
        presets["one_year"] = on_or_before(_months_before(latest_date, 12))
        copom = _previous_copom_date(connection, latest_date, knowledge_cutoff=context.cutoff if context.mode == "as_known" else None)
        if copom is not None:
            snapshot = on_or_before(copom)
            presets["previous_copom"] = {
                "status": "available" if snapshot else "unavailable",
                "requested_date": copom.isoformat(),
                "snapshot": snapshot,
            }
    return {
        "status": "available" if latest else "unavailable",
        "source": _source_contract(source),
        "available_range": None if not dates else {"start": dates[0], "end": dates[-1]},
        "latest": latest,
        "history": history,
        "presets": presets,
        "last_ingestion": _last_ingestion_contract(connection, int(source["id"])),
    }


def _di_contract(connection: sqlite3.Connection, context) -> dict[str, object]:
    source = _source(connection, B3_DI1_SOURCE_KEY)
    if source is None:
        return {"status": "unavailable", "source": None, "latest": None, "last_ingestion": None}
    rows = market_curve_rows(connection, source_id=int(source["id"]), curve_key=B3_DI1_CURVE, context=context)
    if not rows:
        return {
            "status": "unavailable",
            "source": _source_contract(source),
            "latest": None,
            "last_ingestion": _last_ingestion_contract(connection, int(source["id"])),
        }
    latest_date = max(str(row["reference_date"]) for row in rows)
    selected = [row for row in rows if str(row["reference_date"]) == latest_date]
    points = [point_from_row(row) for row in selected]
    return {
        "status": "available",
        "source": _source_contract(source),
        "last_ingestion": _last_ingestion_contract(connection, int(source["id"])),
        "latest": {
            "effective_date": latest_date,
            "points": [
                {
                    "tenor_business_days": point.tenor_business_days,
                    "tenor_years": point.tenor_years,
                    "yield_percent": point.rate_percent,
                    "instrument_key": point.instrument_key,
                    "price_value": point.price_value,
                }
                for point in points
            ],
            "forwards": adjacent_forwards(points),
        },
    }


def publish_yield_curve_json(
    connection: sqlite3.Connection,
    *,
    output_path: str | Path,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> Path:
    """Publish only market term structures retained by the greenfield product."""

    context = build_knowledge_context(
        generated_at=generated_at, knowledge_mode=knowledge_mode, knowledge_cutoff=knowledge_cutoff
    )
    ettj = _ettj_contract(connection, context)
    di = _di_contract(connection, context)
    market_available = ettj["status"] == "available" or di["status"] == "available"

    payload = {
        "view": "yield_curve",
        "generated_at": _iso_z(generated_at),
        **context.contract_fields(),
        "status": "available" if market_available else "unavailable",
        "market": {
            "ettj": ettj,
            "di": di,
            "methodology": {
                "ettj": "ANBIMA zero-coupon ETTJ (Svensson), tenors in business days.",
                "di": "B3 DI1 settlement rate/price from BVBG.187.01; adjacent forwards use 252-business-day compounding.",
                "caveat": (
                    "A ETTJ é a curva zero-cupom de referência mantida no monitor. "
                    "O DI1 é uma fonte provisória e será substituído pela estrutura TaxaSwap/PRE; "
                    "taxas futuras contêm prêmios e não equivalem a previsão pura da Selic."
                ),
            },
        },
    }
    return write_json_atomic(payload, output_path)
