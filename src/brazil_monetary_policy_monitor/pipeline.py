"""End-to-end update pipeline for the first official BCB series."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from .collectors.bcb_sgs import SGSRecord, build_sgs_url, iter_date_windows, parse_sgs_json
from .collectors.http import fetch_bytes
from .db import initialize_database
from .ingestion import (
    SELIC_SERIES_KEY,
    ensure_bcb_sgs_selic_metadata,
    finish_ingestion_run,
    persist_sgs_records,
    start_ingestion_run,
)
from .publish import publish_series_json
from .snapshots import RawSnapshotRun


SELIC_SGS_CODE = 432
SELIC_OFFICIAL_START = date(1999, 3, 5)
DEFAULT_OVERLAP_DAYS = 7
DEFAULT_WINDOW_YEARS = 1

FetchBytes = Callable[[str], bytes]
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _error_document(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


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
    start = latest_date - timedelta(days=overlap_days)
    return min(start, end)


def _validate_cross_chunk_records(records: list[SGSRecord]) -> list[SGSRecord]:
    records.sort(key=lambda record: record.reference_date)
    for previous, current in zip(records, records[1:]):
        if previous.reference_date == current.reference_date:
            raise ValueError(
                f"duplicate reference date across provider chunks: {current.reference_date}"
            )
    return records


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
    """Run the complete SGS 432 pipeline and publish only after validated persistence."""

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
    )
    snapshots = RawSnapshotRun(
        root=Path(raw_root),
        provider="bcb",
        series_key="sgs-432",
        run_id=run_id,
        started_at=started_at,
    )

    received = 0
    inserted = 0
    unchanged = 0
    persisted = False

    try:
        records: list[SGSRecord] = []
        for index, (window_start, window_end) in enumerate(
            iter_date_windows(start, end, max_years=window_years),
            start=1,
        ):
            url = build_sgs_url(SELIC_SGS_CODE, window_start, window_end)
            payload = fetcher(url)
            snapshots.save_payload(index=index, url=url, payload=payload)
            chunk_records = parse_sgs_json(payload)
            received += len(chunk_records)
            records.extend(chunk_records)

        records = _validate_cross_chunk_records(records)
        retrieved_at = clock()
        inserted, unchanged = persist_sgs_records(
            connection,
            series_id=series_id,
            run_id=run_id,
            records=records,
            retrieved_at=retrieved_at,
        )
        persisted = True

        generated_at = clock()
        publish_series_json(
            connection,
            series_key=SELIC_SERIES_KEY,
            output_path=published_path,
            generated_at=generated_at,
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
            status="succeeded",
            finished_at=finished_at,
            records_received=received,
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
        error = _error_document(exc)
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
        # On success close here; failure closes in the exception path first.
        try:
            connection.close()
        except sqlite3.Error:
            pass


def resolve_focus_incremental_start(
    connection: sqlite3.Connection,
    *,
    end: date,
    overlap_days: int = 21,
    initial_lookback_days: int = 730,
) -> date:
    """Choose a bounded Focus backfill, then overlap recent survey dates on updates."""

    from .ingestion import FOCUS_IPCA_MONTHLY_SERIES_KEY

    if overlap_days < 0 or initial_lookback_days < 1:
        raise ValueError("invalid Focus lookback configuration")
    row = connection.execute(
        """
        SELECT MAX(o.source_observation_at)
        FROM observations AS o
        JOIN series AS s ON s.id = o.series_id
        WHERE s.key = ?
        """,
        (FOCUS_IPCA_MONTHLY_SERIES_KEY,),
    ).fetchone()
    latest = None if row is None else row[0]
    if latest is None:
        return end - timedelta(days=initial_lookback_days)
    latest_date = date.fromisoformat(str(latest)[:10])
    return min(latest_date - timedelta(days=overlap_days), end)


def update_focus_ipca(
    *,
    database_path: str | Path,
    raw_root: str | Path,
    published_path: str | Path,
    overview_path: str | Path,
    start: date,
    end: date,
    fetcher: FetchBytes = fetch_bytes,
    clock: Clock = utc_now,
    page_size: int = 10_000,
    window_days: int = 90,
) -> dict[str, object]:
    """Collect monthly Focus IPCA medians and derive the Copom-horizon 12m proxy."""

    from .collectors.bcb_focus import (
        build_focus_monthly_url,
        iter_focus_windows,
        parse_focus_monthly_json,
    )
    from .horizons import derive_horizon_expectations, resolve_br_policy_horizon
    from .ingestion import (
        FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY,
        ensure_bcb_focus_metadata,
        persist_focus_monthly_records,
        persist_horizon_expectations,
    )
    from .publish import publish_overview_json

    if start > end:
        raise ValueError("start date must not be after end date")
    if page_size < 1 or page_size > 10_000:
        raise ValueError("page_size must be between 1 and 10000")
    if window_days < 1 or window_days > 366:
        raise ValueError("window_days must be between 1 and 366")

    connection = initialize_database(database_path)
    source_id, monthly_series_id, horizon_series_id = ensure_bcb_focus_metadata(connection)
    started_at = clock()
    run_id = start_ingestion_run(
        connection,
        source_id=source_id,
        started_at=started_at,
        collector_version="sprint6-focus",
    )
    snapshots = RawSnapshotRun(
        root=Path(raw_root),
        provider="bcb",
        series_key="focus-ipca-monthly",
        run_id=run_id,
        started_at=started_at,
    )

    received = 0
    inserted = 0
    unchanged = 0
    persisted = False
    snapshot_index = 0

    try:
        records = []
        seen: set[tuple[date, date]] = set()
        for window_start, window_end in iter_focus_windows(
            start, end, max_days=window_days
        ):
            url = build_focus_monthly_url(
                window_start,
                window_end,
                top=page_size,
            )
            payload = fetcher(url)
            snapshot_index += 1
            snapshots.save_payload(index=snapshot_index, url=url, payload=payload)
            page = parse_focus_monthly_json(payload)
            if len(page) >= page_size:
                raise ValueError(
                    "Focus response reached the configured row ceiling; "
                    "reduce --window-days rather than relying on OData pagination "
                    f"({window_start} through {window_end}, {len(page)} rows)"
                )
            received += len(page)
            for record in page:
                key = (record.survey_date, record.target_month)
                if key in seen:
                    raise ValueError(
                        "duplicate Focus record across date windows: "
                        f"{record.survey_date} / {record.target_month:%Y-%m}"
                    )
                seen.add(key)
                records.append(record)

        records.sort(key=lambda item: (item.survey_date, item.target_month))
        retrieved_at = clock()
        raw_inserted, raw_unchanged = persist_focus_monthly_records(
            connection,
            series_id=monthly_series_id,
            run_id=run_id,
            records=records,
            retrieved_at=retrieved_at,
        )

        horizon = resolve_br_policy_horizon(end)
        expectations = derive_horizon_expectations(records, horizon=horizon)
        derived_inserted, derived_unchanged = persist_horizon_expectations(
            connection,
            series_id=horizon_series_id,
            run_id=run_id,
            expectations=expectations,
            retrieved_at=retrieved_at,
        )
        inserted = raw_inserted + derived_inserted
        unchanged = raw_unchanged + derived_unchanged
        persisted = True

        publish_series_json(
            connection,
            series_key=FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY,
            output_path=published_path,
            generated_at=clock(),
        )
        publish_overview_json(
            connection,
            output_path=overview_path,
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
            status="succeeded",
            finished_at=finished_at,
            records_received=received,
        )
        return {
            "run_id": run_id,
            "status": "succeeded",
            "records_received": received,
            "records_inserted": inserted,
            "records_unchanged": unchanged,
            "horizon": horizon.key,
            "horizon_expectations": len(expectations),
            "published_path": str(published_path),
            "overview_path": str(overview_path),
            "snapshot_directory": str(snapshots.directory),
        }
    except Exception as exc:
        finished_at = clock()
        status = "partial" if persisted else "failed"
        error = _error_document(exc)
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
        finally:
            snapshots.write_manifest(
                status=status,
                finished_at=finished_at,
                records_received=received,
                error=error,
            )
        raise
    finally:
        connection.close()
