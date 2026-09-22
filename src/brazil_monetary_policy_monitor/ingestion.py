"""Persistence helpers for provider ingestion runs."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import sqlite3
from typing import Iterable

from .collectors.bcb_sgs import SGSRecord


BCB_SGS_SOURCE_KEY = "bcb.sgs"
SELIC_SERIES_KEY = "br.selic.target"


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_bcb_sgs_selic_metadata(connection: sqlite3.Connection) -> tuple[int, int]:
    """Create or refresh the stable source and series metadata for SGS 432."""

    connection.execute(
        """
        INSERT INTO sources(
            key, provider, name, url, documentation_url, license, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            provider = excluded.provider,
            name = excluded.name,
            url = excluded.url,
            documentation_url = excluded.documentation_url,
            license = excluded.license,
            metadata_json = excluded.metadata_json,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (
            BCB_SGS_SOURCE_KEY,
            "BCB",
            "Sistema Gerenciador de Séries Temporais (SGS)",
            "https://api.bcb.gov.br/dados/serie/",
            "https://dadosabertos.bcb.gov.br/dataset/432-taxa-de-juros---meta-selic-definida-pelo-copom",
            "Open Data Commons Open Database License (ODbL)",
            json.dumps({"database": "SGS"}, sort_keys=True),
        ),
    )
    source_id = int(
        connection.execute(
            "SELECT id FROM sources WHERE key = ?", (BCB_SGS_SOURCE_KEY,)
        ).fetchone()[0]
    )

    connection.execute(
        """
        INSERT INTO series(
            key, source_id, source_series_id, title, description,
            unit_original, unit_normalized, frequency, data_kind,
            transformation, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            source_id = excluded.source_id,
            source_series_id = excluded.source_series_id,
            title = excluded.title,
            description = excluded.description,
            unit_original = excluded.unit_original,
            unit_normalized = excluded.unit_normalized,
            frequency = excluded.frequency,
            data_kind = excluded.data_kind,
            transformation = excluded.transformation,
            metadata_json = excluded.metadata_json,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (
            SELIC_SERIES_KEY,
            source_id,
            "432",
            "Taxa de juros - Meta Selic definida pelo Copom",
            "Meta definida pelo Copom para a taxa Selic.",
            "% a.a.",
            "percent_per_year",
            "daily",
            "observed",
            "identity",
            json.dumps(
                {
                    "official_start_date": "1999-03-05",
                    "sgs_code": 432,
                },
                sort_keys=True,
            ),
        ),
    )
    series_id = int(
        connection.execute(
            "SELECT id FROM series WHERE key = ?", (SELIC_SERIES_KEY,)
        ).fetchone()[0]
    )
    connection.commit()
    return source_id, series_id


def start_ingestion_run(
    connection: sqlite3.Connection,
    *,
    source_id: int,
    started_at: datetime,
    collector_version: str = "sprint2",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO ingestion_runs(
            provider, source_id, started_at, status, collector_version
        ) VALUES (?, ?, ?, 'running', ?)
        """,
        ("BCB", source_id, iso_z(started_at), collector_version),
    )
    connection.commit()
    return int(cursor.lastrowid)


def finish_ingestion_run(
    connection: sqlite3.Connection,
    *,
    run_id: int,
    finished_at: datetime,
    status: str,
    records_received: int,
    records_inserted: int,
    records_unchanged: int,
    error: dict[str, object] | None = None,
) -> None:
    if status not in {"succeeded", "failed", "partial"}:
        raise ValueError(f"invalid terminal ingestion status: {status}")
    cursor = connection.execute(
        """
        UPDATE ingestion_runs
        SET finished_at = ?,
            status = ?,
            records_received = ?,
            records_inserted = ?,
            records_updated = 0,
            records_unchanged = ?,
            error_json = ?
        WHERE id = ? AND status = 'running'
        """,
        (
            iso_z(finished_at),
            status,
            records_received,
            records_inserted,
            records_unchanged,
            None if error is None else json.dumps(error, sort_keys=True),
            run_id,
        ),
    )
    if cursor.rowcount != 1:
        connection.rollback()
        raise RuntimeError(f"ingestion run {run_id} is not in running state")
    connection.commit()


def _canonical_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def observation_vintage_key(record: SGSRecord) -> str:
    content = f"{record.reference_date.isoformat()}|{_canonical_decimal(record.value)}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def persist_sgs_records(
    connection: sqlite3.Connection,
    *,
    series_id: int,
    run_id: int,
    records: Iterable[SGSRecord],
    retrieved_at: datetime,
) -> tuple[int, int]:
    """Persist validated records atomically, preserving changed values as revisions."""

    timestamp = iso_z(retrieved_at)
    inserted = 0
    unchanged = 0

    with connection:
        for record in records:
            period = record.reference_date.isoformat()
            vintage_key = observation_vintage_key(record)
            existing = connection.execute(
                """
                SELECT id
                FROM observations
                WHERE series_id = ? AND reference_period = ? AND vintage_key = ?
                """,
                (series_id, period, vintage_key),
            ).fetchone()

            if existing is not None:
                connection.execute(
                    """
                    UPDATE observations
                    SET last_seen_at = ?
                    WHERE id = ?
                    """,
                    (timestamp, int(existing["id"])),
                )
                unchanged += 1
                continue

            connection.execute(
                """
                INSERT INTO observations(
                    series_id,
                    reference_period,
                    reference_start,
                    reference_end,
                    value,
                    published_at,
                    available_at,
                    first_seen_at,
                    last_seen_at,
                    vintage_key,
                    source_revision,
                    ingestion_run_id,
                    quality_flags_json
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, NULL, ?, '[]')
                """,
                (
                    series_id,
                    period,
                    period,
                    period,
                    float(record.value),
                    timestamp,
                    timestamp,
                    timestamp,
                    vintage_key,
                    run_id,
                ),
            )
            inserted += 1

    return inserted, unchanged
