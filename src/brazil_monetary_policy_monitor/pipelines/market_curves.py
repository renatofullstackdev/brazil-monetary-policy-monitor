"""Ingest ANBIMA ETTJ and B3 DI1 without coupling provider details to the UI."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from pathlib import Path

from ..collectors.anbima_ettj import ANBIMA_ETTJ_DOWNLOAD_URL, parse_anbima_ettj_csv, request_fields
from ..collectors.b3_di1 import build_b3_sprd_url, parse_b3_di1_zip
from ..collectors.http import ProviderFetchError, fetch_bytes, post_form_bytes
from ..db import initialize_database
from ..db.market_curves import persist_market_curve_points
from ..ingestion.market_curves import ensure_market_curve_sources
from ..ingestion.runs import finish_ingestion_run, start_ingestion_run
from ..publish.yield_curve import publish_yield_curve_json
from ..snapshots import RawSnapshotRun
from .runtime import error_document, utc_now

GetBytes = Callable[[str], bytes]
PostFormBytes = Callable[[str, Mapping[str, str]], bytes]
Clock = Callable[[], datetime]
DEFAULT_MARKET_CURVE_LOOKBACK_DAYS = 7


def _business_dates(start: date, end: date) -> list[date]:
    if start > end:
        raise ValueError("start date must not be after end date")
    days = (end - start).days
    return [value for offset in range(days + 1) if (value := start + timedelta(days=offset)).weekday() < 5]


def _run_source(
    connection,
    *,
    source_id: int,
    provider: str,
    series_key: str,
    raw_root: str | Path,
    dates: list[date],
    fetch_payload: Callable[[date], tuple[str, bytes]],
    parse_payload: Callable[[bytes], list],
    extension: str,
    clock: Clock,
) -> dict[str, object]:
    started_at = clock()
    run_id = start_ingestion_run(
        connection,
        source_id=source_id,
        started_at=started_at,
        collector_version="market-curves-provisional-v1",
        provider=provider,
    )
    snapshots = RawSnapshotRun(
        root=Path(raw_root),
        provider=provider.lower().replace(" ", "_"),
        series_key=series_key,
        run_id=run_id,
        started_at=started_at,
    )
    received = inserted = unchanged = 0
    skipped: list[dict[str, str]] = []
    chunk = 0
    try:
        for reference in dates:
            try:
                url, payload = fetch_payload(reference)
            except ProviderFetchError as exc:
                if exc.status_code in {404, 410}:
                    skipped.append({"date": reference.isoformat(), "reason": "no provider file for this date"})
                    continue
                # Authentication, throttling after retries, server failures and
                # transport errors are operational failures. Treating them as a
                # non-trading day would silently produce incomplete backfills.
                raise
            chunk += 1
            snapshots.save_payload(index=chunk, url=url, payload=payload, extension=extension)
            records = parse_payload(payload)
            if records and records[0].reference_date != reference:
                raise ValueError(
                    f"provider returned {records[0].reference_date.isoformat()} for requested {reference.isoformat()}"
                )
            received += len(records)
            new, same = persist_market_curve_points(
                connection,
                source_id=source_id,
                run_id=run_id,
                records=records,
                retrieved_at=clock(),
            )
            inserted += new
            unchanged += same
        status = "succeeded" if received else "partial"
        finished_at = clock()
        finish_ingestion_run(
            connection,
            run_id=run_id,
            finished_at=finished_at,
            status=status,
            records_received=received,
            records_inserted=inserted,
            records_unchanged=unchanged,
            error=None if received else {"message": "No usable trading-day payload was collected", "skipped": skipped},
        )
        snapshots.write_manifest(
            status=status,
            finished_at=finished_at,
            records_received=received,
            error=None if received else {"skipped": skipped},
        )
        return {
            "status": status,
            "run_id": run_id,
            "records_received": received,
            "records_inserted": inserted,
            "records_unchanged": unchanged,
            "skipped_dates": skipped,
            "snapshot_directory": str(snapshots.directory),
        }
    except Exception as exc:
        finished_at = clock()
        finish_ingestion_run(
            connection,
            run_id=run_id,
            finished_at=finished_at,
            status="failed",
            records_received=received,
            records_inserted=inserted,
            records_unchanged=unchanged,
            error=error_document(exc),
        )
        snapshots.write_manifest(
            status="failed",
            finished_at=finished_at,
            records_received=received,
            error=error_document(exc),
        )
        raise


def update_market_curves(
    *,
    database_path: str | Path,
    raw_root: str | Path,
    published_path: str | Path,
    end: date,
    start: date | None = None,
    get_fetcher: GetBytes = fetch_bytes,
    post_fetcher: PostFormBytes = post_form_bytes,
    clock: Clock = utc_now,
) -> dict[str, object]:
    """Collect recent ETTJ/DI1 observations and republish market expectations.

    The ANBIMA legacy download surface exposes only a short recent window.  On
    first use the command therefore defaults to seven calendar days and then
    accumulates revision-aware history locally.  A longer explicit ``start``
    is allowed for providers/dates that still respond.
    """

    effective_start = start or end - timedelta(days=DEFAULT_MARKET_CURVE_LOOKBACK_DAYS)
    dates = _business_dates(effective_start, end)
    connection = initialize_database(database_path)
    anbima_source_id, b3_source_id = ensure_market_curve_sources(connection)

    def fetch_anbima(reference: date):
        return ANBIMA_ETTJ_DOWNLOAD_URL, post_fetcher(ANBIMA_ETTJ_DOWNLOAD_URL, request_fields(reference))

    def fetch_b3(reference: date):
        url = build_b3_sprd_url(reference)
        return url, get_fetcher(url)


    try:
        anbima = _run_source(
            connection,
            source_id=anbima_source_id,
            provider="ANBIMA",
            series_key="ettj",
            raw_root=raw_root,
            dates=dates,
            fetch_payload=fetch_anbima,
            parse_payload=parse_anbima_ettj_csv,
            extension="csv",
            clock=clock,
        )
        b3 = _run_source(
            connection,
            source_id=b3_source_id,
            provider="B3",
            series_key="di1",
            raw_root=raw_root,
            dates=dates,
            fetch_payload=fetch_b3,
            parse_payload=parse_b3_di1_zip,
            extension="zip",
            clock=clock,
        )
        publish_yield_curve_json(connection, output_path=published_path, generated_at=clock())
        source_statuses = {anbima["status"], b3["status"]}
        status = "succeeded" if source_statuses == {"succeeded"} else "partial"
        return {
            "status": status,
            "start": effective_start.isoformat(),
            "end": end.isoformat(),
            "anbima": anbima,
            "b3": b3,
            "published_path": str(published_path),
        }
    finally:
        connection.close()
