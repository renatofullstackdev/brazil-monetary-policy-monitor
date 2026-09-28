"""Persistence for the current documentary DPF profile.

This adapter is intentionally isolated because historical RMD ingestion will replace these
snapshot parameters with monthly historical observations from official RMD/CKAN
sources without affecting other ingestion modules.
"""

from __future__ import annotations

from datetime import datetime
import json
import sqlite3

from ..temporal import iso_z
from .policy import parameter_version_key

TESOURO_RMD_SOURCE_KEY = "tesouro.rmd"


def ensure_tesouro_rmd_source(connection: sqlite3.Connection) -> int:
    """Register the official monthly RMD source used by the fiscal domain."""
    connection.execute(
        """
        INSERT INTO sources(key, provider, name, url, documentation_url, license, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
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
            TESOURO_RMD_SOURCE_KEY,
            "Tesouro Nacional",
            "Relatório Mensal da Dívida Pública Federal (RMD)",
            "https://www.tesourotransparente.gov.br/publicacoes/relatorio-mensal-da-divida-rmd",
            "https://www.tesourotransparente.gov.br/temas/divida-publica-federal/estatisticas-e-relatorios-da-divida-publica-federal",
            None,
            json.dumps(
                {
                    "frequency": "monthly",
                    "scope": "versioned documentary DPF indicators",
                    "publication_time_precision": "day",
                    "migration_note": (
                        "Historical RMD ingestion will replace documentary snapshots with "
                        "official historical observations."
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        ),
    )
    row = connection.execute(
        "SELECT id FROM sources WHERE key = ?", (TESOURO_RMD_SOURCE_KEY,)
    ).fetchone()
    assert row is not None
    connection.commit()
    return int(row[0])



def persist_fiscal_profile_inputs(
    connection: sqlite3.Connection,
    *,
    retrieved_at: datetime,
    inputs=None,
) -> tuple[int, int]:
    if inputs is None:
        from ..fiscal_profile import FISCAL_PROFILE_INPUTS

        inputs = FISCAL_PROFILE_INPUTS

    source_id = ensure_tesouro_rmd_source(connection)
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
