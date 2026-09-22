"""Publish normalized database series as atomic static JSON artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from ..db.observations import observations_latest
from .atomic import write_json_atomic


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def publish_series_json(
    connection: sqlite3.Connection,
    *,
    series_key: str,
    output_path: str | Path,
    generated_at: datetime,
) -> Path:
    metadata = connection.execute(
        """
        SELECT
            s.key,
            s.source_series_id,
            s.title,
            s.description,
            s.unit_original,
            s.unit_normalized,
            s.frequency,
            s.data_kind,
            s.transformation,
            src.key AS source_key,
            src.provider,
            src.name AS source_name,
            src.documentation_url,
            src.license
        FROM series AS s
        JOIN sources AS src ON src.id = s.source_id
        WHERE s.key = ?
        """,
        (series_key,),
    ).fetchone()
    if metadata is None:
        raise KeyError(f"unknown series: {series_key}")

    rows = observations_latest(connection, series_key)
    document = {
        "schema_version": 1,
        "generated_at": _iso_z(generated_at),
        "series": {
            "key": metadata["key"],
            "source_series_id": metadata["source_series_id"],
            "title": metadata["title"],
            "description": metadata["description"],
            "unit_original": metadata["unit_original"],
            "unit_normalized": metadata["unit_normalized"],
            "frequency": metadata["frequency"],
            "data_kind": metadata["data_kind"],
            "transformation": metadata["transformation"],
            "source": {
                "key": metadata["source_key"],
                "provider": metadata["provider"],
                "name": metadata["source_name"],
                "documentation_url": metadata["documentation_url"],
                "license": metadata["license"],
            },
        },
        "observations": [
            {
                "date": row["reference_period"],
                "value": row["value"],
                "available_at": row["available_at"],
                "vintage_key": row["vintage_key"],
            }
            for row in rows
        ],
    }

    return write_json_atomic(document, output_path)
