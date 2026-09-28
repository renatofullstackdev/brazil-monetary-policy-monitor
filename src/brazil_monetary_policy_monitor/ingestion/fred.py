"""FRED source and series metadata registration."""

from __future__ import annotations

import json
import sqlite3

FRED_SOURCE_KEY = "fred.us"


def ensure_fred_series_metadata(connection: sqlite3.Connection, spec) -> tuple[int, int]:
    connection.execute(
        """
        INSERT INTO sources(key, provider, name, url, documentation_url, license, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            provider=excluded.provider, name=excluded.name, url=excluded.url,
            documentation_url=excluded.documentation_url, license=excluded.license,
            metadata_json=excluded.metadata_json,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        (
            FRED_SOURCE_KEY,
            "Federal Reserve Bank of St. Louis (FRED)",
            "Federal Reserve Economic Data — graph CSV",
            "https://fred.stlouisfed.org/graph/fredgraph.csv",
            "https://fred.stlouisfed.org/",
            "Series-specific; preserve source attribution",
            json.dumps({"transport": "keyless graph CSV", "api_key_required": False}, sort_keys=True),
        ),
    )
    source_row = connection.execute("SELECT id FROM sources WHERE key=?", (FRED_SOURCE_KEY,)).fetchone()
    assert source_row is not None
    source_id = int(source_row[0])
    connection.execute(
        """
        INSERT INTO series(key, source_id, source_series_id, title, description,
            unit_original, unit_normalized, frequency, data_kind, transformation, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            source_id=excluded.source_id, source_series_id=excluded.source_series_id,
            title=excluded.title, description=excluded.description,
            unit_original=excluded.unit_original, unit_normalized=excluded.unit_normalized,
            frequency=excluded.frequency, data_kind=excluded.data_kind,
            transformation=excluded.transformation, metadata_json=excluded.metadata_json,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        (
            spec.key,
            source_id,
            spec.fred_id,
            spec.title,
            spec.description,
            spec.unit_original,
            spec.unit_normalized,
            spec.frequency,
            spec.data_kind,
            spec.transformation,
            json.dumps({"fred_id": spec.fred_id, "documentation_url": spec.documentation_url}, sort_keys=True),
        ),
    )
    series_row = connection.execute("SELECT id FROM series WHERE key=?", (spec.key,)).fetchone()
    assert series_row is not None
    connection.commit()
    return source_id, int(series_row[0])
