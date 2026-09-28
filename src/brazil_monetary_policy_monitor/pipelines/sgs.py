"""Reusable BCB SGS collection workflow for scalar series."""

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
from ..collectors.http import ProviderFetchError
from ..ingestion.runs import finish_ingestion_run, start_ingestion_run
from ..ingestion.sgs import ensure_bcb_sgs_series_metadata, persist_sgs_records
from ..publish import publish_series_json
from ..snapshots import RawSnapshotRun
from .runtime import Clock, FetchBytes, error_document

DEFAULT_WINDOW_YEARS = 1


def resolve_series_incremental_start(
    connection: sqlite3.Connection,
    *,
    series_key: str,
    end: date,
    overlap_days: int,
    initial_lookback_days: int,
) -> date:
    if overlap_days < 0:
        raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1:
        raise ValueError("initial_lookback_days must be positive")
    row = connection.execute(
        """
        SELECT MAX(o.reference_end)
        FROM observations AS o
        JOIN series AS s ON s.id = o.series_id
        WHERE s.key = ?
        """,
        (series_key,),
    ).fetchone()
    if row is None or row[0] is None:
        return end - timedelta(days=initial_lookback_days)
    return min(date.fromisoformat(str(row[0])) - timedelta(days=overlap_days), end)


def validate_cross_chunk_records(records: list[SGSRecord]) -> list[SGSRecord]:
    records.sort(key=lambda record: record.reference_date)
    for previous, current in zip(records, records[1:]):
        if previous.reference_date == current.reference_date:
            raise ValueError(
                f"duplicate reference date across provider chunks: {current.reference_date}"
            )
    return records


def coalesce_identical_cross_chunk_records(records: list[SGSRecord]) -> list[SGSRecord]:
    records.sort(key=lambda record: record.reference_date)
    coalesced: list[SGSRecord] = []
    for record in records:
        if not coalesced or coalesced[-1].reference_date != record.reference_date:
            coalesced.append(record)
            continue
        if coalesced[-1].value != record.value:
            raise ValueError(
                "conflicting duplicate reference date across provider chunks: "
                f"{record.reference_date}"
            )
    return coalesced


def update_sgs_series_group(
    connection: sqlite3.Connection,
    *,
    specs,
    raw_root: str | Path,
    published_dir: str | Path,
    end: date,
    start: date | None,
    fetcher: FetchBytes,
    clock: Clock,
    overlap_days: int,
    initial_lookback_days: int,
    window_years: int,
    collector_version: str,
    frequency: str,
) -> list[dict[str, object]]:
    """Collect and publish a coherent group of daily or monthly SGS series."""

    if frequency not in {"daily", "monthly"}:
        raise ValueError("frequency must be 'daily' or 'monthly'")

    output_dir = Path(published_dir)
    results: list[dict[str, object]] = []
    for spec in specs:
        source_id, series_id = ensure_bcb_sgs_series_metadata(connection, spec)
        series_start = start or resolve_series_incremental_start(
            connection,
            series_key=spec.key,
            end=end,
            overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days,
        )
        if frequency == "monthly":
            series_start = series_start.replace(day=1)

        started_at = clock()
        run_id = start_ingestion_run(
            connection,
            source_id=source_id,
            started_at=started_at,
            collector_version=collector_version,
            provider="BCB",
        )
        snapshots = RawSnapshotRun(
            root=Path(raw_root),
            provider="bcb",
            series_key=f"sgs-{spec.code}",
            run_id=run_id,
            started_at=started_at,
        )
        received = inserted = unchanged = 0
        persisted = False
        try:
            records: list[SGSRecord] = []
            for index, (window_start, window_end) in enumerate(
                iter_date_windows(series_start, end, max_years=window_years), start=1
            ):
                url = build_sgs_url(spec.code, window_start, window_end)
                try:
                    payload = fetcher(url)
                except ProviderFetchError as exc:
                    if not is_empty_sgs_range_error(exc):
                        raise
                    snapshots.save_payload(index=index, url=url, payload=exc.response_body or b"")
                    continue
                snapshots.save_payload(index=index, url=url, payload=payload)
                chunk = parse_sgs_json(payload)
                received += len(chunk)
                records.extend(chunk)

            if frequency == "monthly":
                records = coalesce_identical_cross_chunk_records(records)
            else:
                records = validate_cross_chunk_records(records)

            inserted, unchanged = persist_sgs_records(
                connection,
                series_id=series_id,
                run_id=run_id,
                records=records,
                retrieved_at=clock(),
            )
            persisted = True
            output_path = output_dir / f"{spec.key.replace('.', '-')}.json"
            publish_series_json(
                connection,
                series_key=spec.key,
                output_path=output_path,
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
            results.append(
                {
                    "series_key": spec.key,
                    "sgs_code": spec.code,
                    "run_id": run_id,
                    "status": "succeeded",
                    "start": series_start.isoformat(),
                    "end": end.isoformat(),
                    "records_received": received,
                    "records_inserted": inserted,
                    "records_unchanged": unchanged,
                    "published_path": str(output_path),
                    "snapshot_directory": str(snapshots.directory),
                }
            )
        except Exception as exc:
            finished_at = clock()
            status = "partial" if persisted else "failed"
            error = error_document(exc)
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
            raise
    return results
