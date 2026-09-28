"""Queries for versioned model parameters and documentary policy inputs."""

from __future__ import annotations

import sqlite3


def parameter_latest(
    connection: sqlite3.Connection,
    key: str,
    *,
    knowledge_cutoff: str | None = None,
) -> sqlite3.Row | None:
    """Return the latest version of a parameter that is defensibly available.

    ``knowledge_cutoff`` constrains both availability and effective date.  The
    latter prevents a parameter announced in advance from being used before it
    becomes effective in a current-state view.
    """

    cutoff_clause = ""
    params: dict[str, object] = {"key": key}
    if knowledge_cutoff is not None:
        cutoff_clause = "AND p.available_at <= :cutoff AND p.effective_from <= substr(:cutoff, 1, 10)"
        params["cutoff"] = knowledge_cutoff

    return connection.execute(
        f"""
        SELECT
            p.*,
            s.provider AS source_provider,
            s.name AS source_name,
            s.url AS source_url,
            s.documentation_url AS source_documentation_url
        FROM parameters AS p
        LEFT JOIN sources AS s ON s.id = p.source_id
        WHERE p.key = :key
          {cutoff_clause}
        ORDER BY
            p.effective_from DESC,
            p.available_at DESC,
            COALESCE(p.published_at, '') DESC,
            p.id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
