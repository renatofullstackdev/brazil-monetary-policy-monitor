"""Publish the static Tesouro Direto yield-curve contract."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3

from ..db.yield_curve import latest_yield_curve_quotes
from ..ingestion import TESOURO_DIRETO_SOURCE_KEY
from ..models.yield_curve import build_curve_snapshot
from .atomic import write_json_atomic


YIELD_CURVE_SCHEMA_VERSION = 1


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


def _source(connection: sqlite3.Connection) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM sources WHERE key = ?", (TESOURO_DIRETO_SOURCE_KEY,)
    ).fetchone()
    if row is None:
        raise LookupError("Tesouro Direto source metadata is not registered")
    return row


def _previous_copom_date(connection: sqlite3.Connection, before: date) -> date | None:
    row = connection.execute(
        """
        SELECT occurred_at
        FROM events
        WHERE event_type IN ('copom_meeting', 'copom_decision')
          AND substr(occurred_at, 1, 10) < ?
        ORDER BY occurred_at DESC
        LIMIT 1
        """,
        (before.isoformat(),),
    ).fetchone()
    if row is None:
        return None
    return date.fromisoformat(str(row[0])[:10])


def publish_yield_curve_json(
    connection: sqlite3.Connection,
    *,
    output_path: str | Path,
    generated_at: datetime,
) -> Path:
    source = _source(connection)
    rows = latest_yield_curve_quotes(connection, source_id=int(source["id"]))
    metadata = json.loads(source["metadata_json"] or "{}")

    rows_by_date: dict[date, list[sqlite3.Row]] = {}
    for row in rows:
        reference = date.fromisoformat(str(row["reference_date"]))
        rows_by_date.setdefault(reference, []).append(row)
    distinct_dates = sorted(rows_by_date)

    def snapshot_for_effective(effective: date) -> dict[str, object] | None:
        return build_curve_snapshot(rows_by_date.get(effective, []), requested_date=effective)

    def snapshot_on_or_before(requested: date) -> dict[str, object] | None:
        eligible = [candidate for candidate in distinct_dates if candidate <= requested]
        if not eligible:
            return None
        snapshot = snapshot_for_effective(eligible[-1])
        if snapshot is not None:
            snapshot["requested_date"] = requested.isoformat()
        return snapshot

    snapshots = [
        snapshot
        for current in distinct_dates
        if (snapshot := snapshot_for_effective(current)) is not None
    ]

    latest = snapshots[-1] if snapshots else None
    presets: dict[str, object] = {
        "latest": latest,
        "one_month": None,
        "one_year": None,
        "previous_copom": {
            "status": "unavailable",
            "note": "Ainda não há evento Copom persistido; a Sprint 14 preencherá este preset automaticamente.",
        },
    }
    if latest is not None:
        latest_date = date.fromisoformat(str(latest["effective_date"]))
        presets["one_month"] = snapshot_on_or_before(_months_before(latest_date, 1))
        presets["one_year"] = snapshot_on_or_before(_months_before(latest_date, 12))
        copom_date = _previous_copom_date(connection, latest_date)
        if copom_date is not None:
            snapshot = snapshot_on_or_before(copom_date)
            presets["previous_copom"] = {
                "status": "available" if snapshot is not None else "unavailable",
                "requested_date": copom_date.isoformat(),
                "snapshot": snapshot,
                "note": None if snapshot is not None else "Não há curva disponível na data ou antes do evento Copom.",
            }

    payload = {
        "schema_version": YIELD_CURVE_SCHEMA_VERSION,
        "view": "yield_curve",
        "generated_at": _iso_z(generated_at),
        "status": "available" if latest is not None else "unavailable",
        "source": {
            "provider": source["provider"],
            "name": source["name"],
            "url": source["url"],
            "documentation_url": source["documentation_url"],
            "license": source["license"],
            "metadata_url": metadata.get("metadata_url"),
        },
        "methodology": {
            "quote": "Taxa Compra Manha",
            "curve_type": "offered_title_yield_proxy",
            "nominal_instruments": [
                "Tesouro Prefixado",
                "Tesouro Prefixado com Juros Semestrais",
            ],
            "real_instruments": [
                "Tesouro IPCA+",
                "Tesouro IPCA+ com Juros Semestrais",
            ],
            "constant_tenors_years": [2, 3, 5, 7, 10],
            "interpolation": "linear_between_bracketing_offered_maturities_no_extrapolation",
            "implicit_inflation": "exact_fisher_nominal_over_real_minus_one",
            "caveat": (
                "As linhas são proxies formadas por yields dos títulos ofertados, não curvas zero-cupom. "
                "A inflação implícita contém prêmios de risco, liquidez e diferenças de instrumentos; "
                "não deve ser interpretada como expectativa pura de inflação."
            ),
        },
        "available_range": None if not snapshots else {
            "start": snapshots[0]["effective_date"],
            "end": snapshots[-1]["effective_date"],
        },
        "latest": latest,
        "presets": presets,
        "snapshots": snapshots,
    }
    return write_json_atomic(payload, output_path)
