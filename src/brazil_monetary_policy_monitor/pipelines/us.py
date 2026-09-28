"""United States benchmark pipeline using keyless FRED graph CSV transport."""

from __future__ import annotations
from datetime import date
from pathlib import Path
import sqlite3
from ..collectors.fred import build_fred_url, parse_fred_csv
from ..collectors.http import fetch_bytes
from ..db import initialize_database
from ..ingestion.fred import ensure_fred_series_metadata
from ..ingestion.runs import finish_ingestion_run, start_ingestion_run
from ..ingestion.sgs import persist_sgs_records
from ..publish import publish_series_json
from ..publish.us import publish_us_json
from ..snapshots import RawSnapshotRun
from ..us_series import US_SERIES
from .runtime import Clock, FetchBytes, error_document, utc_now
from .sgs import resolve_series_incremental_start

DEFAULT_US_OVERLAP_DAYS = 45
DEFAULT_US_LOOKBACK_DAYS = 10 * 366
COLLECTOR_VERSION = "fred-us-benchmarks-v1"


def _update_fred_series_group(connection: sqlite3.Connection, *, specs,
    raw_root: str | Path, published_dir: str | Path, end: date, start: date | None,
    fetcher: FetchBytes, clock: Clock, overlap_days: int, initial_lookback_days: int
) -> list[dict[str, object]]:
    output_dir = Path(published_dir)
    results=[]
    for spec in specs:
        source_id, series_id = ensure_fred_series_metadata(connection, spec)
        series_start = start or resolve_series_incremental_start(
            connection, series_key=spec.key, end=end, overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days)
        started_at=clock()
        run_id=start_ingestion_run(connection, source_id=source_id, started_at=started_at,
                                   collector_version=COLLECTOR_VERSION, provider="FRED")
        snapshots=RawSnapshotRun(root=Path(raw_root),provider="fred",series_key=spec.fred_id.lower(),
                                 run_id=run_id,started_at=started_at)
        received=inserted=unchanged=0; persisted=False
        try:
            url=build_fred_url(spec.fred_id,series_start,end); payload=fetcher(url)
            snapshots.save_payload(index=1,url=url,payload=payload,extension="csv")
            records=parse_fred_csv(payload,series_id=spec.fred_id); received=len(records)
            inserted,unchanged=persist_sgs_records(connection,series_id=series_id,run_id=run_id,
                                                    records=records,retrieved_at=clock())
            persisted=True
            output_path=output_dir/f"{spec.key.replace('.', '-')}.json"
            publish_series_json(connection,series_key=spec.key,output_path=output_path,generated_at=clock())
            finished_at=clock()
            finish_ingestion_run(connection,run_id=run_id,finished_at=finished_at,status="succeeded",
                                 records_received=received,records_inserted=inserted,records_unchanged=unchanged)
            snapshots.write_manifest(status="succeeded",finished_at=finished_at,records_received=received)
            results.append({"series_key":spec.key,"fred_id":spec.fred_id,"run_id":run_id,
                            "status":"succeeded","start":series_start.isoformat(),"end":end.isoformat(),
                            "records_received":received,"records_inserted":inserted,
                            "records_unchanged":unchanged,"published_path":str(output_path),
                            "snapshot_directory":str(snapshots.directory)})
        except Exception as exc:
            finished_at=clock(); status="partial" if persisted else "failed"; error=error_document(exc)
            finish_ingestion_run(connection,run_id=run_id,finished_at=finished_at,status=status,
                                 records_received=received,records_inserted=inserted,
                                 records_unchanged=unchanged,error=error)
            snapshots.write_manifest(status=status,finished_at=finished_at,records_received=received,error=error)
            raise
    return results


def update_us_context(*, database_path: str | Path, raw_root: str | Path,
    published_dir: str | Path, us_output_path: str | Path, end: date,
    start: date | None = None, fetcher: FetchBytes = fetch_bytes, clock: Clock = utc_now,
    overlap_days: int = DEFAULT_US_OVERLAP_DAYS,
    initial_lookback_days: int = DEFAULT_US_LOOKBACK_DAYS) -> dict[str, object]:
    if start is not None and start > end: raise ValueError("start date must not be after end date")
    if overlap_days < 0: raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1: raise ValueError("initial_lookback_days must be positive")
    connection=initialize_database(database_path)
    try:
        results=_update_fred_series_group(connection,specs=US_SERIES,raw_root=raw_root,
            published_dir=published_dir,end=end,start=start,fetcher=fetcher,clock=clock,
            overlap_days=overlap_days,initial_lookback_days=initial_lookback_days)
        publish_us_json(connection,output_path=us_output_path,generated_at=clock())
        return {"status":"succeeded","series":results,"us_output_path":str(us_output_path)}
    finally:
        connection.close()
