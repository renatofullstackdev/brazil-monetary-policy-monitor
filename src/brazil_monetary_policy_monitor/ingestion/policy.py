"""Persistence for documentary monetary-policy inputs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
import sqlite3

from ..temporal import iso_z
from .common import canonical_decimal, stable_hash

POLICY_DOCUMENT_SOURCE_KEY = "bcb.policy_documents"


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
                    "scope": "source-backed documentary model inputs",
                    "publication_time_precision": "day",
                    "temporal_contract": {
                        "effective_from": "when the parameter is applicable",
                        "published_at": "document publication boundary",
                        "reference_period": "period described by the source, when applicable",
                    },
                },
                sort_keys=True,
            ),
        ),
    )
    row = connection.execute(
        "SELECT id FROM sources WHERE key = ?", (POLICY_DOCUMENT_SOURCE_KEY,)
    ).fetchone()
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
        item.published_on.isoformat(),
        item.source_reference,
        item.methodology,
    )


def persist_policy_inputs(
    connection: sqlite3.Connection,
    *,
    retrieved_at: datetime,
    inputs=None,
) -> tuple[int, int]:
    """Persist curated policy inputs idempotently with documentary provenance."""

    if inputs is None:
        from ..policy_inputs import POLICY_INPUTS

        inputs = POLICY_INPUTS

    source_id = ensure_policy_document_source(connection)
    retrieved = iso_z(retrieved_at)
    inserted = 0
    unchanged = 0
    with connection:
        for item in inputs:
            version_key = parameter_version_key(item)
            existing = connection.execute(
                """
                SELECT id FROM parameters
                WHERE key = ? AND effective_from = ? AND version_key = ?
                """,
                (item.key, item.effective_from.isoformat(), version_key),
            ).fetchone()
            if existing is not None:
                unchanged += 1
                continue

            # Documentary inputs generally establish a day, not a clock time.
            # Treat the end of that UTC day as the conservative knowledge boundary.
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
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    item.key,
                    item.value,
                    item.unit,
                    item.data_kind,
                    item.effective_from.isoformat(),
                    published,
                    published,
                    retrieved,
                    version_key,
                    source_id,
                    item.source_reference,
                    item.methodology,
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                ),
            )
            inserted += 1
    return inserted, unchanged
