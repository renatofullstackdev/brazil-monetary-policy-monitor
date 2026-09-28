"""Selic target pipeline."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sqlite3

from ..collectors.bcb_sgs import (
    SGSRecord,
    build_sgs_url,
    is_empty_sgs_range_error,
    iter_date_windows,
    parse_sgs_json,
)
from ..collectors.http import ProviderFetchError, fetch_bytes
from ..db import initialize_database
from ..ingestion.runs import finish_ingestion_run, start_ingestion_run
from ..ingestion.sgs import SELIC_SERIES_KEY, ensure_bcb_sgs_selic_metadata, persist_sgs_records
from ..publish import publish_series_json
from ..snapshots import RawSnapshotRun
from .runtime import Clock, FetchBytes, error_document, utc_now
from .sgs import DEFAULT_WINDOW_YEARS, validate_cross_chunk_records

SELIC_SGS_CODE = 432
SELIC_OFFICIAL_START = date(1999, 3, 5)
DEFAULT_OVERLAP_DAYS = 7
COLLECTOR_VERSION = "selic-sgs-v1"


def resolve_incremental_start(
    connection: sqlite3.Connection,
    *,
    end: date,
    overlap_days: int = DEFAULT_OVERLAP_DAYS,
) -> date:
    if overlap_days < 0:
        raise ValueError("overlap_days cannot be negative")
    row = connection.execute(
        """
        SELECT MAX(o.reference_end)
        FROM observations AS o
        JOIN series AS s ON s.id = o.series_id
        WHERE s.key = ?
        """,
        (SELIC_SERIES_KEY,),
    ).fetchone()
    latest = None if row is None else row[0]
    if latest is None:
        return SELIC_OFFICIAL_START
    latest_date = date.fromisoformat(str(latest))
    return min(latest_date - timedelta(days=overlap_days), end)


def update_selic(
    *,
    database_path: str | Path,
    raw_root: str | Path,
    published_path: str | Path,
    start: date,
    end: date,
    fetcher: FetchBytes = fetch_bytes,
    clock: Clock = utc_now,
    window_years: int = DEFAULT_WINDOW_YEARS,
) -> dict[str, object]:
    if start > end:
        raise ValueError("start date must not be after end date")
    if not 1 <= window_years <= 10:
        raise ValueError("window_years must be between 1 and 10")

    connection = initialize_database(database_path)
    source_id, series_id = ensure_bcb_sgs_selic_metadata(connection)
    started_at = clock()
    run_id = start_ingestion_run(
        connection,
        source_id=source_id,
        started_at=started_at,
        collector_version=COLLECTOR_VERSION,
        provider="BCB",
    )
    snapshots = RawSnapshotRun(
        root=Path(raw_root),
        provider="bcb",
        series_key="sgs-432",
        run_id=run_id,
        started_at=started_at,
    )
    received = inserted = unchanged = 0
    persisted = False
    try:
        records: list[SGSRecord] = []
        for index, (window_start, window_end) in enumerate(
            iter_date_windows(start, end, max_years=window_years), start=1
        ):
            url = build_sgs_url(SELIC_SGS_CODE, window_start, window_end)
            try:
                payload = fetcher(url)
            except ProviderFetchError as exc:
                if not is_empty_sgs_range_error(exc):
                    raise
                snapshots.save_payload(index=index, url=url, payload=exc.response_body or b"")
                continue
            snapshots.save_payload(index=index, url=url, payload=payload)
            chunk_records = parse_sgs_json(payload)
            received += len(chunk_records)
            records.extend(chunk_records)

        records = validate_cross_chunk_records(records)
        inserted, unchanged = persist_sgs_records(
            connection,
            series_id=series_id,
            run_id=run_id,
            records=records,
            retrieved_at=clock(),
        )
        persisted = True
        publish_series_json(
            connection,
            series_key=SELIC_SERIES_KEY,
            output_path=published_path,
            generated_at=clock(),
        )
        finished_at = clock()
        finish_ingestion_run(
            connection,
            run_id=run_id,
            finished_at=finished_at,
            status="succeeded",
            records_received=received,
            records_inserted=inserted,
            records_unchanged=unchanged,
        )
        snapshots.write_manifest(
            status="succeeded", finished_at=finished_at, records_received=received
        )
        return {
            "run_id": run_id,
            "status": "succeeded",
            "records_received": received,
            "records_inserted": inserted,
            "records_unchanged": unchanged,
            "published_path": str(published_path),
            "snapshot_directory": str(snapshots.directory),
        }
    except Exception as exc:
        finished_at = clock()
        status = "partial" if persisted else "failed"
        error = error_document(exc)
        try:
            finish_ingestion_run(
                connection,
                run_id=run_id,
                finished_at=finished_at,
                status=status,
                records_received=received,
                records_inserted=inserted,
                records_unchanged=unchanged,
                error=error,
            )
            snapshots.write_manifest(
                status=status,
                finished_at=finished_at,
                records_received=received,
                error=error,
            )
        finally:
            connection.close()
        raise
    finally:
        try:
            connection.close()
        except sqlite3.Error:
            pass
