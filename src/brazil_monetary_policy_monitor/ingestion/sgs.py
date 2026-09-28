"""BCB SGS metadata registration and observation persistence."""

from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal
import json
import sqlite3
from typing import Iterable

from ..collectors.bcb_sgs import SGSRecord
from ..temporal import iso_z
from .common import canonical_decimal, stable_hash

BCB_SGS_SOURCE_KEY = "bcb.sgs"
SELIC_SERIES_KEY = "br.selic.target"


def _ensure_sgs_source(connection: sqlite3.Connection) -> int:
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
            "https://www3.bcb.gov.br/sgspub/",
            "Open Data Commons Open Database License (ODbL)",
            json.dumps({"database": "SGS"}, sort_keys=True),
        ),
    )
    row = connection.execute(
        "SELECT id FROM sources WHERE key = ?", (BCB_SGS_SOURCE_KEY,)
    ).fetchone()
    assert row is not None
    return int(row[0])


def ensure_bcb_sgs_selic_metadata(connection: sqlite3.Connection) -> tuple[int, int]:
    """Create or refresh stable source and series metadata for SGS 432."""

    source_id = _ensure_sgs_source(connection)
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
            json.dumps({"official_start_date": "1999-03-05", "sgs_code": 432}, sort_keys=True),
        ),
    )
    row = connection.execute("SELECT id FROM series WHERE key = ?", (SELIC_SERIES_KEY,)).fetchone()
    assert row is not None
    series_id = int(row[0])
    reconcile_selic_availability(connection, series_id=series_id)
    connection.commit()
    return source_id, series_id


def _selic_reference_available_at(reference_date, retrieved_at: datetime) -> str:
    """Return a defensible knowledge boundary for the policy target in force.

    SGS 432 describes the Copom target that is publicly in force on each
    reference date.  Historical backfills therefore need not pretend that the
    target became known only when this repository downloaded the old row.  For
    past dates we use the end of the reference day as a conservative boundary;
    for the current day an earlier local retrieval remains stronger evidence.
    """

    if retrieved_at.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    end_of_reference_day = datetime.combine(
        reference_date, time.max, tzinfo=timezone.utc
    )
    return iso_z(min(end_of_reference_day, retrieved_at.astimezone(timezone.utc)))


def reconcile_selic_availability(
    connection: sqlite3.Connection, *, series_id: int
) -> int:
    """Repair legacy Selic backfills whose availability equalled first_seen_at.

    Earlier project versions treated every SGS observation conservatively as
    known only at local ingestion time.  That is appropriate for ordinary SGS
    backfills but too conservative for SGS 432: the row states the policy target
    already in force on its reference date.  This reconciliation is idempotent
    and never moves availability later.
    """

    rows = connection.execute(
        """
        SELECT id, reference_period, available_at, first_seen_at
        FROM observations
        WHERE series_id=?
        ORDER BY reference_period, first_seen_at, id
        """,
        (series_id,),
    ).fetchall()
    changed = 0
    seen_periods: set[str] = set()
    for row in rows:
        period = str(row["reference_period"])
        # Only the first locally observed vintage may inherit the semantic
        # availability of the target already in force.  A later correction or
        # provider revision must remain available only from its first local
        # observation; backdating that revision would introduce future knowledge.
        if period in seen_periods:
            continue
        seen_periods.add(period)
        try:
            reference = datetime.fromisoformat(period).date()
            first_seen = datetime.fromisoformat(str(row["first_seen_at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        candidate = _selic_reference_available_at(reference, first_seen)
        if candidate < str(row["available_at"]):
            connection.execute(
                "UPDATE observations SET available_at=? WHERE id=?",
                (candidate, int(row["id"])),
            )
            changed += 1
    return changed


def ensure_bcb_sgs_series_metadata(connection: sqlite3.Connection, spec) -> tuple[int, int]:
    """Register a scalar SGS series from a declarative series specification."""

    source_id = _ensure_sgs_source(connection)
    metadata = {"sgs_code": spec.code, "documentation_url": spec.documentation_url}
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
            spec.key,
            source_id,
            str(spec.code),
            spec.title,
            spec.description,
            spec.unit_original,
            spec.unit_normalized,
            spec.frequency,
            spec.data_kind,
            spec.transformation,
            json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        ),
    )
    row = connection.execute("SELECT id FROM series WHERE key = ?", (spec.key,)).fetchone()
    assert row is not None
    connection.commit()
    return source_id, int(row[0])


def observation_vintage_key(record: SGSRecord) -> str:
    return stable_hash(record.reference_date.isoformat(), canonical_decimal(Decimal(record.value)))


def persist_sgs_records(
    connection: sqlite3.Connection,
    *,
    series_id: int,
    run_id: int,
    records: Iterable[SGSRecord],
    retrieved_at: datetime,
) -> tuple[int, int]:
    """Persist validated scalar observations while preserving changed values as revisions."""

    timestamp = iso_z(retrieved_at)
    series_row = connection.execute("SELECT key FROM series WHERE id=?", (series_id,)).fetchone()
    if series_row is None:
        raise ValueError(f"unknown series_id: {series_id}")
    is_selic = str(series_row["key"]) == SELIC_SERIES_KEY
    inserted = 0
    unchanged = 0
    with connection:
        for record in records:
            period = record.reference_date.isoformat()
            prior_period = connection.execute(
                "SELECT 1 FROM observations WHERE series_id=? AND reference_period=? LIMIT 1",
                (series_id, period),
            ).fetchone()
            available = (
                _selic_reference_available_at(record.reference_date, retrieved_at)
                if is_selic and prior_period is None else timestamp
            )
            vintage_key = observation_vintage_key(record)
            existing = connection.execute(
                """
                SELECT id FROM observations
                WHERE series_id = ? AND reference_period = ? AND vintage_key = ?
                """,
                (series_id, period, vintage_key),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    "UPDATE observations SET last_seen_at = ?, available_at = MIN(available_at, ?) WHERE id = ?",
                    (timestamp, available, int(existing["id"])),
                )
                unchanged += 1
                continue

            connection.execute(
                """
                INSERT INTO observations(
                    series_id, reference_period, reference_start, reference_end, value,
                    published_at, available_at, first_seen_at, last_seen_at,
                    vintage_key, source_revision, ingestion_run_id, quality_flags_json
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, NULL, ?, '[]')
                """,
                (
                    series_id,
                    period,
                    period,
                    period,
                    float(record.value),
                    available,
                    timestamp,
                    timestamp,
                    vintage_key,
                    run_id,
                ),
            )
            inserted += 1
    return inserted, unchanged
