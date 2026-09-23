"""Persistence helpers for revision-aware Tesouro Direto quote snapshots."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import sqlite3
from typing import Iterable

from ..collectors.tesouro_direto import TreasuryQuote
from ..ingestion import iso_z


def _canonical_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def quote_vintage_key(record: TreasuryQuote) -> str:
    content = "|".join(
        (
            record.instrument_type,
            record.maturity_date.isoformat(),
            record.reference_date.isoformat(),
            _canonical_decimal(record.buy_yield),
            _canonical_decimal(record.sell_yield),
            _canonical_decimal(record.buy_price),
            _canonical_decimal(record.sell_price),
            _canonical_decimal(record.base_price),
        )
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def persist_yield_curve_quotes(
    connection: sqlite3.Connection,
    *,
    source_id: int,
    run_id: int,
    records: Iterable[TreasuryQuote],
    retrieved_at: datetime,
) -> tuple[int, int]:
    timestamp = iso_z(retrieved_at)
    inserted = unchanged = 0
    with connection:
        for record in records:
            vintage_key = quote_vintage_key(record)
            existing = connection.execute(
                """
                SELECT id FROM yield_curve_quotes
                WHERE source_id = ? AND instrument_type = ? AND maturity_date = ?
                  AND reference_date = ? AND vintage_key = ?
                """,
                (
                    source_id,
                    record.instrument_type,
                    record.maturity_date.isoformat(),
                    record.reference_date.isoformat(),
                    vintage_key,
                ),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    "UPDATE yield_curve_quotes SET last_seen_at = ? WHERE id = ?",
                    (timestamp, int(existing["id"])),
                )
                unchanged += 1
                continue
            connection.execute(
                """
                INSERT INTO yield_curve_quotes(
                    source_id, instrument_type, maturity_date, reference_date,
                    buy_yield, sell_yield, buy_price, sell_price, base_price,
                    available_at, first_seen_at, last_seen_at, vintage_key,
                    ingestion_run_id, quality_flags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]')
                """,
                (
                    source_id,
                    record.instrument_type,
                    record.maturity_date.isoformat(),
                    record.reference_date.isoformat(),
                    None if record.buy_yield is None else float(record.buy_yield),
                    None if record.sell_yield is None else float(record.sell_yield),
                    None if record.buy_price is None else float(record.buy_price),
                    None if record.sell_price is None else float(record.sell_price),
                    None if record.base_price is None else float(record.base_price),
                    timestamp,
                    timestamp,
                    timestamp,
                    vintage_key,
                    run_id,
                ),
            )
            inserted += 1
    return inserted, unchanged


def latest_yield_curve_quotes(
    connection: sqlite3.Connection,
    *,
    source_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    clauses = ["source_id = ?"]
    params: list[object] = [source_id]
    if start_date is not None:
        clauses.append("reference_date >= ?")
        params.append(start_date)
    if end_date is not None:
        clauses.append("reference_date <= ?")
        params.append(end_date)
    where = " AND ".join(clauses)
    return connection.execute(
        f"""
        WITH ranked AS (
            SELECT q.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY source_id, instrument_type, maturity_date, reference_date
                       ORDER BY available_at DESC, first_seen_at DESC, id DESC
                   ) AS revision_rank
            FROM yield_curve_quotes AS q
            WHERE {where}
        )
        SELECT * FROM ranked
        WHERE revision_rank = 1
        ORDER BY reference_date, instrument_type, maturity_date
        """,
        params,
    ).fetchall()
