"""Persistence for documentary monetary-policy regimes and output-gap vintages."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import sqlite3

from ..temporal import iso_z
from .common import canonical_decimal, stable_hash

POLICY_DOCUMENT_SOURCE_KEY = "bcb.policy_documents"
OUTPUT_GAP_SERIES_KEY = "br.output_gap.copom"


def ensure_policy_document_source(connection: sqlite3.Connection) -> int:
    connection.execute(
        """
        INSERT INTO sources(key, provider, name, url, documentation_url, license, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            provider = excluded.provider,
            name = excluded.name,
            url = excluded.url,
            documentation_url = excluded.documentation_url,
            metadata_json = excluded.metadata_json,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (
            POLICY_DOCUMENT_SOURCE_KEY,
            "BCB/CMN",
            "Documentos oficiais de política monetária",
            "https://www.bcb.gov.br/publicacoes/rpm",
            "https://www.bcb.gov.br/controleinflacao",
            None,
            json.dumps(
                {
                    "scope": "source-backed documentary policy inputs and vintages",
                    "publication_time_precision": "day",
                    "temporal_contract": {
                        "effective_from/effective_to": "regime applicability",
                        "published_at/available_at": "public documentary knowledge boundary",
                        "reference_period": "economic period described by the source",
                        "source_observation_at": "document publication date for output-gap vintages",
                    },
                },
                sort_keys=True,
            ),
        ),
    )
    row = connection.execute("SELECT id FROM sources WHERE key = ?", (POLICY_DOCUMENT_SOURCE_KEY,)).fetchone()
    assert row is not None
    connection.commit()
    return int(row[0])


def ensure_output_gap_series(connection: sqlite3.Connection, *, source_id: int | None = None) -> int:
    if source_id is None:
        source_id = ensure_policy_document_source(connection)
    connection.execute(
        """
        INSERT INTO series(
            key, source_id, source_series_id, title, description,
            unit_original, unit_normalized, frequency, data_kind,
            transformation, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            source_id=excluded.source_id, source_series_id=excluded.source_series_id,
            title=excluded.title, description=excluded.description,
            unit_original=excluded.unit_original, unit_normalized=excluded.unit_normalized,
            frequency=excluded.frequency, data_kind=excluded.data_kind,
            transformation=excluded.transformation, metadata_json=excluded.metadata_json,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        (
            OUTPUT_GAP_SERIES_KEY,
            source_id,
            "RI/RPM/output-gap",
            "Hiato do produto — vintages do Copom",
            "Estimativas trimestrais do hiato do produto publicadas nos RI/RPM, preservadas por vintage documental.",
            "%",
            "percentage_points",
            "quarterly_document_vintage",
            "estimated",
            "identity",
            json.dumps({
                "revision_aware": True,
                "warning": "O hiato é não observável e pode ser revisado em relatórios posteriores.",
                "temporal_contract": {
                    "reference_period": "quarter estimated by the Copom",
                    "source_observation_at": "RI/RPM publication date",
                    "available_at": "end of the documented publication day",
                },
            }, ensure_ascii=False, sort_keys=True),
        ),
    )
    row = connection.execute("SELECT id FROM series WHERE key=?", (OUTPUT_GAP_SERIES_KEY,)).fetchone()
    assert row is not None
    connection.commit()
    return int(row[0])


def parameter_version_key(item) -> str:
    return stable_hash(
        item.key,
        canonical_decimal(Decimal(str(item.value))),
        item.unit,
        item.data_kind,
        item.effective_from.isoformat(),
        None if getattr(item, "effective_to", None) is None else item.effective_to.isoformat(),
        item.published_on.isoformat(),
        item.source_reference,
        item.methodology,
    )


def persist_policy_inputs(connection: sqlite3.Connection, *, retrieved_at: datetime, inputs=None) -> tuple[int, int]:
    """Persist target and neutral-rate documentary regimes idempotently.

    The built-in catalog is authoritative for the policy keys it owns. When the
    default catalog is used, obsolete rows from earlier project versions are
    removed before the current documentary regimes are inserted. Supplying an
    explicit ``inputs`` iterable disables that reconciliation, which keeps unit
    tests and one-off imports non-destructive.
    """

    reconcile_catalog = inputs is None
    if inputs is None:
        from ..policy_inputs import POLICY_INPUTS
        inputs = POLICY_INPUTS
    inputs = tuple(inputs)

    source_id = ensure_policy_document_source(connection)
    retrieved = iso_z(retrieved_at)
    inserted = unchanged = 0
    with connection:
        if reconcile_catalog:
            expected_by_key: dict[str, set[str]] = {}
            for item in inputs:
                expected_by_key.setdefault(item.key, set()).add(parameter_version_key(item))
            for key, expected_versions in expected_by_key.items():
                placeholders = ",".join("?" for _ in expected_versions)
                connection.execute(
                    f"DELETE FROM parameters WHERE source_id=? AND key=? AND version_key NOT IN ({placeholders})",
                    (source_id, key, *sorted(expected_versions)),
                )

        for item in inputs:
            version_key = parameter_version_key(item)
            existing = connection.execute(
                "SELECT id FROM parameters WHERE key=? AND effective_from=? AND version_key=?",
                (item.key, item.effective_from.isoformat(), version_key),
            ).fetchone()
            if existing is not None:
                unchanged += 1
                continue
            published = f"{item.published_on.isoformat()}T23:59:59Z"
            metadata = {
                "publication_time_precision": "day",
                "reference_period": item.reference_period,
                "source_url": item.source_url,
                "source_label": item.source_label,
                "note": item.note,
            }
            connection.execute(
                """
                INSERT INTO parameters(
                    key, value, unit, data_kind, effective_from, effective_to,
                    published_at, available_at, retrieved_at, version_key,
                    source_id, source_reference, methodology, ingestion_run_id,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    item.key, item.value, item.unit, item.data_kind,
                    item.effective_from.isoformat(),
                    None if getattr(item, "effective_to", None) is None else item.effective_to.isoformat(),
                    published, published, retrieved, version_key, source_id,
                    item.source_reference, item.methodology,
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                ),
            )
            inserted += 1
    return inserted, unchanged


def _quarter_bounds(reference_period: str) -> tuple[date, date]:
    year_text, quarter_text = reference_period.split("-Q")
    year, quarter = int(year_text), int(quarter_text)
    month = 1 + (quarter - 1) * 3
    start = date(year, month, 1)
    if quarter == 4:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 3, 1) - timedelta(days=1)
    return start, end


def persist_output_gap_vintages(connection: sqlite3.Connection, *, retrieved_at: datetime, vintages=None) -> tuple[int, int]:
    """Persist official RI/RPM output-gap vintages without collapsing revisions."""

    if vintages is None:
        from ..policy_inputs import OUTPUT_GAP_VINTAGES
        vintages = OUTPUT_GAP_VINTAGES
    source_id = ensure_policy_document_source(connection)
    series_id = ensure_output_gap_series(connection, source_id=source_id)
    retrieved = iso_z(retrieved_at)
    inserted = unchanged = 0
    with connection:
        # Sprint 18 moved the output gap from a snapshot parameter to a
        # revision-aware series. Remove the obsolete representation rather than
        # keeping two competing sources of truth.
        connection.execute(
            "DELETE FROM parameters WHERE source_id=? AND key='br.output_gap.rpm'",
            (source_id,),
        )
        for item in vintages:
            if item.published_on > retrieved_at.date():
                continue
            start, end = _quarter_bounds(item.reference_period)
            available = f"{item.published_on.isoformat()}T23:59:59Z"
            vintage_key = stable_hash(item.reference_period, item.report_key, canonical_decimal(Decimal(str(item.value))))
            existing = connection.execute(
                "SELECT id FROM observations WHERE series_id=? AND reference_period=? AND vintage_key=?",
                (series_id, item.reference_period, vintage_key),
            ).fetchone()
            if existing is not None:
                connection.execute("UPDATE observations SET last_seen_at=? WHERE id=?", (retrieved, int(existing['id'])))
                unchanged += 1
                continue
            flags = [
                "documentary_copom_output_gap",
                "revision_aware",
                {"report_key": item.report_key, "source_url": item.source_url, "source_label": item.source_label, "source_reference": item.source_reference},
            ]
            if item.note:
                flags.append({"note": item.note})
            connection.execute(
                """
                INSERT INTO observations(
                    series_id, reference_period, reference_start, reference_end, value,
                    published_at, available_at, first_seen_at, last_seen_at,
                    vintage_key, source_revision, ingestion_run_id, quality_flags_json,
                    source_observation_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    series_id, item.reference_period, start.isoformat(), end.isoformat(), item.value,
                    available, available, retrieved, retrieved, vintage_key, item.report_key,
                    json.dumps(flags, ensure_ascii=False, sort_keys=True), item.published_on.isoformat(),
                ),
            )
            inserted += 1
    return inserted, unchanged
