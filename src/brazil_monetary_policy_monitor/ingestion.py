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

FOCUS_SOURCE_KEY = "bcb.focus"
FOCUS_IPCA_MONTHLY_SERIES_KEY = "br.focus.ipca.monthly_median"
FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY = "br.focus.ipca.policy_horizon"


def ensure_bcb_focus_metadata(connection: sqlite3.Connection) -> tuple[int, int, int]:
    """Create metadata for raw monthly Focus medians and the derived policy-horizon series."""

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
            FOCUS_SOURCE_KEY,
            "BCB",
            "Sistema Expectativas de Mercado (Focus)",
            "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/",
            "https://dadosabertos.bcb.gov.br/dataset/expectativas-mercado",
            "Open Data Commons Open Database License (ODbL)",
            json.dumps(
                {
                    "database": "EXP",
                    "api": "OData",
                    "publication_cadence_note": (
                        "Statistics are calculated daily; the BCB catalog says they are "
                        "published on the first business day of each week."
                    ),
                },
                sort_keys=True,
            ),
        ),
    )
    source_id = int(
        connection.execute(
            "SELECT id FROM sources WHERE key = ?", (FOCUS_SOURCE_KEY,)
        ).fetchone()[0]
    )

    definitions = (
        (
            FOCUS_IPCA_MONTHLY_SERIES_KEY,
            "ExpectativaMercadoMensais/IPCA",
            "Focus — mediana mensal do IPCA",
            "Mediana das expectativas mensais de IPCA das instituições participantes do Focus.",
            "survey",
            "identity",
            {
                "endpoint": "ExpectativaMercadoMensais",
                "indicator": "IPCA",
                "baseCalculo": 0,
                "reference_period": "target month",
                "source_observation_at": "Focus Data field (survey/statistic date)",
            },
        ),
        (
            FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY,
            "derived/from/ExpectativaMercadoMensais/IPCA",
            "Focus — inflação composta no horizonte relevante do Copom",
            (
                "Inflação acumulada em 12 meses até o trimestre de horizonte relevante, "
                "derivada pela composição das medianas mensais do Focus."
            ),
            "derived",
            "compound_12_monthly_focus_medians",
            {
                "warning": (
                    "Compounding monthly medians is not identical to the median of "
                    "institution-level cumulative 12-month forecasts."
                )
            },
        ),
    )
    ids: list[int] = []
    for key, source_series_id, title, description, kind, transformation, metadata in definitions:
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
                key,
                source_id,
                source_series_id,
                title,
                description,
                "%",
                "percent_per_year" if kind == "derived" else "percent_per_month",
                "survey_date",
                kind,
                transformation,
                json.dumps(metadata, sort_keys=True),
            ),
        )
        ids.append(
            int(connection.execute("SELECT id FROM series WHERE key = ?", (key,)).fetchone()[0])
        )
    connection.commit()
    return source_id, ids[0], ids[1]


def _month_end(value):
    from calendar import monthrange
    from datetime import date

    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def _focus_vintage_key(*parts: object) -> str:
    content = "|".join(str(part) for part in parts)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def persist_focus_monthly_records(
    connection: sqlite3.Connection,
    *,
    series_id: int,
    run_id: int,
    records,
    retrieved_at: datetime,
) -> tuple[int, int]:
    """Persist Focus monthly medians without backdating public availability."""

    timestamp = iso_z(retrieved_at)
    inserted = 0
    unchanged = 0
    with connection:
        for record in records:
            period = record.target_month.strftime("%Y-%m")
            source_date = record.survey_date.isoformat()
            vintage_key = _focus_vintage_key(
                period,
                source_date,
                _canonical_decimal(record.median),
                record.respondent_count,
            )
            existing = connection.execute(
                """
                SELECT id FROM observations
                WHERE series_id = ? AND reference_period = ? AND vintage_key = ?
                """,
                (series_id, period, vintage_key),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    "UPDATE observations SET last_seen_at = ? WHERE id = ?",
                    (timestamp, int(existing["id"])),
                )
                unchanged += 1
                continue
            connection.execute(
                """
                INSERT INTO observations(
                    series_id, reference_period, reference_start, reference_end, value,
                    published_at, available_at, first_seen_at, last_seen_at,
                    vintage_key, source_revision, ingestion_run_id, quality_flags_json,
                    source_observation_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    series_id,
                    period,
                    record.target_month.isoformat(),
                    _month_end(record.target_month).isoformat(),
                    float(record.median),
                    timestamp,
                    timestamp,
                    timestamp,
                    vintage_key,
                    source_date,
                    run_id,
                    json.dumps(
                        [
                            "publication_timestamp_not_provided_by_endpoint",
                            {
                                "numeroRespondentes": record.respondent_count,
                                "baseCalculo": record.base_calculation,
                            },
                        ],
                        sort_keys=True,
                    ),
                    source_date,
                ),
            )
            inserted += 1
    return inserted, unchanged


def persist_horizon_expectations(
    connection: sqlite3.Connection,
    *,
    series_id: int,
    run_id: int,
    expectations,
    retrieved_at: datetime,
) -> tuple[int, int]:
    """Persist horizon-aligned derived expectations as immutable survey-date vintages."""

    timestamp = iso_z(retrieved_at)
    inserted = 0
    unchanged = 0
    with connection:
        for item in expectations:
            source_date = item.survey_date.isoformat()
            period = item.horizon.key
            vintage_key = _focus_vintage_key(
                period, source_date, _canonical_decimal(item.value), "compound_monthly_medians"
            )
            existing = connection.execute(
                """SELECT id FROM observations
                   WHERE series_id = ? AND reference_period = ? AND vintage_key = ?""",
                (series_id, period, vintage_key),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    "UPDATE observations SET last_seen_at = ? WHERE id = ?",
                    (timestamp, int(existing["id"])),
                )
                unchanged += 1
                continue
            connection.execute(
                """
                INSERT INTO observations(
                    series_id, reference_period, reference_start, reference_end, value,
                    published_at, available_at, first_seen_at, last_seen_at,
                    vintage_key, source_revision, ingestion_run_id, quality_flags_json,
                    source_observation_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    series_id,
                    period,
                    item.horizon.window_start.isoformat(),
                    item.horizon.window_end.isoformat(),
                    float(item.value),
                    timestamp,
                    timestamp,
                    timestamp,
                    vintage_key,
                    source_date,
                    run_id,
                    json.dumps(
                        [
                            "derived_from_monthly_focus_medians",
                            "not_institution_level_cumulative_median",
                        ]
                    ),
                    source_date,
                ),
            )
            inserted += 1
    return inserted, unchanged
