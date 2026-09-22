"""Queries that make observation-vintage semantics explicit."""

from __future__ import annotations

import sqlite3


_LATEST_SQL = """
WITH ranked AS (
    SELECT
        o.*,
        ROW_NUMBER() OVER (
            PARTITION BY o.series_id, o.reference_period
            ORDER BY o.available_at DESC, COALESCE(o.source_observation_at, '') DESC, o.first_seen_at DESC, o.id DESC
        ) AS revision_rank
    FROM observations AS o
    JOIN series AS s ON s.id = o.series_id
    WHERE s.key = :series_key
)
SELECT *
FROM ranked
WHERE revision_rank = 1
ORDER BY reference_start, reference_end, id
"""

_AS_KNOWN_SQL = """
WITH eligible AS (
    SELECT o.*
    FROM observations AS o
    JOIN series AS s ON s.id = o.series_id
    WHERE s.key = :series_key
      AND o.available_at <= :knowledge_cutoff
),
ranked AS (
    SELECT
        eligible.*,
        ROW_NUMBER() OVER (
            PARTITION BY series_id, reference_period
            ORDER BY available_at DESC, COALESCE(source_observation_at, '') DESC, first_seen_at DESC, id DESC
        ) AS revision_rank
    FROM eligible
)
SELECT *
FROM ranked
WHERE revision_rank = 1
ORDER BY reference_start, reference_end, id
"""


def observations_latest(
    connection: sqlite3.Connection,
    series_key: str,
) -> list[sqlite3.Row]:
    """Return the newest known revision for each period of a series."""

    return list(connection.execute(_LATEST_SQL, {"series_key": series_key}))


def observations_as_known(
    connection: sqlite3.Connection,
    series_key: str,
    knowledge_cutoff: str,
) -> list[sqlite3.Row]:
    """Return only revisions known to be available by ``knowledge_cutoff``."""

    return list(
        connection.execute(
            _AS_KNOWN_SQL,
            {
                "series_key": series_key,
                "knowledge_cutoff": knowledge_cutoff,
            },
        )
    )
