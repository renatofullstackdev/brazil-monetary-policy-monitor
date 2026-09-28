"""Revision-aware persistence for generic market term-structure points."""

from __future__ import annotations

from datetime import datetime
import hashlib
import sqlite3
from typing import Iterable

from ..temporal import iso_z
from ..models.term_structure import MarketCurvePoint


def _vintage_key(point: MarketCurvePoint) -> str:
    content = "|".join(
        (
            point.curve_key,
            point.reference_date.isoformat(),
            point.point_key,
            "" if point.tenor_business_days is None else str(point.tenor_business_days),
            "" if point.maturity_date is None else point.maturity_date.isoformat(),
            point.instrument_key or "",
            format(point.rate_percent, ".12g"),
            "" if point.price_value is None else format(point.price_value, ".12g"),
        )
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def persist_market_curve_points(
    connection: sqlite3.Connection,
    *,
    source_id: int,
    run_id: int,
    records: Iterable[MarketCurvePoint],
    retrieved_at: datetime,
) -> tuple[int, int]:
    timestamp = iso_z(retrieved_at)
    inserted = unchanged = 0
    with connection:
        for point in records:
            vintage_key = _vintage_key(point)
            existing = connection.execute(
                """
                SELECT id FROM market_curve_points
                WHERE source_id = ? AND curve_key = ? AND reference_date = ?
                  AND point_key = ? AND vintage_key = ?
                """,
                (source_id, point.curve_key, point.reference_date.isoformat(), point.point_key, vintage_key),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    "UPDATE market_curve_points SET last_seen_at = ? WHERE id = ?",
                    (timestamp, int(existing["id"])),
                )
                unchanged += 1
                continue
            connection.execute(
                """
                INSERT INTO market_curve_points(
                    source_id, curve_key, reference_date, point_key,
                    tenor_business_days, maturity_date, instrument_key,
                    rate_percent, price_value, available_at, first_seen_at,
                    last_seen_at, vintage_key, ingestion_run_id, quality_flags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]')
                """,
                (
                    source_id,
                    point.curve_key,
                    point.reference_date.isoformat(),
                    point.point_key,
                    point.tenor_business_days,
                    None if point.maturity_date is None else point.maturity_date.isoformat(),
                    point.instrument_key,
                    point.rate_percent,
                    point.price_value,
                    timestamp,
                    timestamp,
                    timestamp,
                    vintage_key,
                    run_id,
                ),
            )
            inserted += 1
    return inserted, unchanged


def market_curve_points_latest(
    connection: sqlite3.Connection,
    *,
    source_id: int | None = None,
    curve_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    return _market_curve_rows(
        connection,
        source_id=source_id,
        curve_key=curve_key,
        start_date=start_date,
        end_date=end_date,
        knowledge_cutoff=None,
    )


def market_curve_points_as_known(
    connection: sqlite3.Connection,
    *,
    knowledge_cutoff: str,
    source_id: int | None = None,
    curve_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    return _market_curve_rows(
        connection,
        source_id=source_id,
        curve_key=curve_key,
        start_date=start_date,
        end_date=end_date,
        knowledge_cutoff=knowledge_cutoff,
    )


def _market_curve_rows(
    connection: sqlite3.Connection,
    *,
    source_id: int | None,
    curve_key: str | None,
    start_date: str | None,
    end_date: str | None,
    knowledge_cutoff: str | None,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[object] = []
    if source_id is not None:
        clauses.append("source_id = ?")
        params.append(source_id)
    if curve_key is not None:
        clauses.append("curve_key = ?")
        params.append(curve_key)
    if start_date is not None:
        clauses.append("reference_date >= ?")
        params.append(start_date)
    if end_date is not None:
        clauses.append("reference_date <= ?")
        params.append(end_date)
    if knowledge_cutoff is not None:
        clauses.append("available_at <= ?")
        params.append(knowledge_cutoff)
    where = " AND ".join(clauses) if clauses else "1 = 1"
    return connection.execute(
        f"""
        WITH ranked AS (
            SELECT p.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY source_id, curve_key, reference_date, point_key
                       ORDER BY available_at DESC, first_seen_at DESC, id DESC
                   ) AS revision_rank
            FROM market_curve_points AS p
            WHERE {where}
        )
        SELECT * FROM ranked
        WHERE revision_rank = 1
        ORDER BY reference_date, curve_key, tenor_business_days, point_key
        """,
        params,
    ).fetchall()
