"""Synchronization of documentary monetary-policy inputs."""

from __future__ import annotations

from pathlib import Path

from ..db import initialize_database
from ..ingestion.policy import persist_policy_inputs
from ..publish import publish_overview_json
from .runtime import Clock, utc_now


def sync_policy_inputs(
    *,
    database_path: str | Path,
    overview_path: str | Path | None = None,
    clock: Clock = utc_now,
) -> dict[str, object]:
    connection = initialize_database(database_path)
    try:
        inserted, unchanged = persist_policy_inputs(connection, retrieved_at=clock())
        if overview_path is not None:
            publish_overview_json(connection, output_path=overview_path, generated_at=clock())
        return {
            "status": "succeeded",
            "records_inserted": inserted,
            "records_unchanged": unchanged,
            "overview_path": None if overview_path is None else str(overview_path),
        }
    finally:
        connection.close()
