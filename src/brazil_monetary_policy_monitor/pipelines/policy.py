"""Synchronization of documentary monetary-policy history."""

from __future__ import annotations

from pathlib import Path

from ..db import initialize_database
from ..ingestion.policy import persist_output_gap_vintages, persist_policy_inputs
from ..publish import publish_overview_json
from .runtime import Clock, utc_now


def sync_policy_inputs(*, database_path: str | Path, overview_path: str | Path | None = None, clock: Clock = utc_now) -> dict[str, object]:
    connection = initialize_database(database_path)
    try:
        now = clock()
        parameters_inserted, parameters_unchanged = persist_policy_inputs(connection, retrieved_at=now)
        gaps_inserted, gaps_unchanged = persist_output_gap_vintages(connection, retrieved_at=now)
        if overview_path is not None:
            publish_overview_json(connection, output_path=overview_path, generated_at=clock())
        coverage = {
            "inflation_target_regimes": int(connection.execute(
                "SELECT COUNT(*) FROM parameters WHERE key='br.inflation.target'"
            ).fetchone()[0]),
            "neutral_rate_regimes": int(connection.execute(
                "SELECT COUNT(*) FROM parameters WHERE key='br.neutral_real_rate.rpm'"
            ).fetchone()[0]),
            "output_gap_vintages": int(connection.execute(
                """SELECT COUNT(*) FROM observations o JOIN series s ON s.id=o.series_id
                   WHERE s.key='br.output_gap.copom'"""
            ).fetchone()[0]),
        }
        return {
            "status": "succeeded",
            "coverage": coverage,
            "parameter_records_inserted": parameters_inserted,
            "parameter_records_unchanged": parameters_unchanged,
            "output_gap_vintages_inserted": gaps_inserted,
            "output_gap_vintages_unchanged": gaps_unchanged,
            "records_inserted": parameters_inserted + gaps_inserted,
            "records_unchanged": parameters_unchanged + gaps_unchanged,
            "overview_path": None if overview_path is None else str(overview_path),
        }
    finally:
        connection.close()
