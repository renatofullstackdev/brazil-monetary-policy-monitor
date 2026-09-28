"""Lifecycle persistence for ingestion runs."""

from __future__ import annotations

from datetime import datetime
import json
import sqlite3

from ..temporal import iso_z


def start_ingestion_run(
    connection: sqlite3.Connection,
    *,
    source_id: int,
    started_at: datetime,
    collector_version: str,
    provider: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO ingestion_runs(
            provider, source_id, started_at, status, collector_version
        ) VALUES (?, ?, ?, 'running', ?)
        """,
        (provider, source_id, iso_z(started_at), collector_version),
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
