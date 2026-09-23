"""End-to-end update pipeline for the first official BCB series."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from .collectors.bcb_sgs import (
    SGSRecord,
    build_sgs_url,
    is_empty_sgs_range_error,
    iter_date_windows,
    parse_sgs_json,
)
from .collectors.http import ProviderFetchError, fetch_bytes
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


def _month_start(value: date) -> date:
    """Return the first calendar day of the month containing ``value``."""

    return value.replace(day=1)


def _coalesce_identical_cross_chunk_records(records: list[SGSRecord]) -> list[SGSRecord]:
    """Collapse identical duplicate observations while rejecting conflicts.

    SGS monthly series can return the same month from two adjacent date
    queries when a chunk boundary cuts through that month.  Repeating the
    exact same date/value pair is transport-level overlap, not a revision.
    A different value for the same reference date remains an error because
    accepting it would make the chosen vintage depend on chunk order.
    """

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
            try:
                payload = fetcher(url)
            except ProviderFetchError as exc:
                if not is_empty_sgs_range_error(exc):
                    raise
                # Preserve the provider's explicit empty-range response in the
                # raw snapshot, but normalize it to zero observations.
                snapshots.save_payload(
                    index=index, url=url, payload=exc.response_body or b""
                )
                continue
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
    window_days: int = 30,
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

DEFAULT_MACRO_OVERLAP_DAYS = 90
DEFAULT_MACRO_LOOKBACK_DAYS = 5 * 366


def _resolve_series_incremental_start(
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


def sync_policy_inputs(
    *,
    database_path: str | Path,
    overview_path: str | Path | None = None,
    clock: Clock = utc_now,
) -> dict[str, object]:
    """Persist the source-backed documentary inputs used by the monetary model."""

    from .ingestion import persist_policy_inputs
    from .publish import publish_overview_json

    connection = initialize_database(database_path)
    try:
        retrieved_at = clock()
        inserted, unchanged = persist_policy_inputs(
            connection,
            retrieved_at=retrieved_at,
        )
        if overview_path is not None:
            publish_overview_json(
                connection,
                output_path=overview_path,
                generated_at=clock(),
            )
        return {
            "status": "succeeded",
            "records_inserted": inserted,
            "records_unchanged": unchanged,
            "overview_path": None if overview_path is None else str(overview_path),
        }
    finally:
        connection.close()


def _update_monthly_sgs_series_group(
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
) -> list[dict[str, object]]:
    """Collect a coherent group of monthly SGS scalar series.

    Monthly observations are aligned to month starts before chunking because
    the SGS can repeat a reference month when an arbitrary day boundary cuts
    through that month.  Identical overlap is coalesced; conflicting values
    remain fatal so chunk order never decides a vintage.
    """

    from .ingestion import ensure_bcb_sgs_series_metadata

    output_dir = Path(published_dir)
    results: list[dict[str, object]] = []
    for spec in specs:
        source_id, series_id = ensure_bcb_sgs_series_metadata(connection, spec)
        series_start = start or _resolve_series_incremental_start(
            connection,
            series_key=spec.key,
            end=end,
            overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days,
        )
        series_start = _month_start(series_start)
        started_at = clock()
        run_id = start_ingestion_run(
            connection,
            source_id=source_id,
            started_at=started_at,
            collector_version=collector_version,
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
                iter_date_windows(series_start, end, max_years=window_years),
                start=1,
            ):
                url = build_sgs_url(spec.code, window_start, window_end)
                try:
                    payload = fetcher(url)
                except ProviderFetchError as exc:
                    if not is_empty_sgs_range_error(exc):
                        raise
                    snapshots.save_payload(
                        index=index, url=url, payload=exc.response_body or b""
                    )
                    continue
                snapshots.save_payload(index=index, url=url, payload=payload)
                chunk = parse_sgs_json(payload)
                received += len(chunk)
                records.extend(chunk)

            records = _coalesce_identical_cross_chunk_records(records)
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
                status="succeeded",
                finished_at=finished_at,
                records_received=received,
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
            error = _error_document(exc)
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


def update_macro_context(
    *,
    database_path: str | Path,
    raw_root: str | Path,
    published_dir: str | Path,
    overview_path: str | Path,
    end: date,
    start: date | None = None,
    fetcher: FetchBytes = fetch_bytes,
    clock: Clock = utc_now,
    overlap_days: int = DEFAULT_MACRO_OVERLAP_DAYS,
    initial_lookback_days: int = DEFAULT_MACRO_LOOKBACK_DAYS,
    window_years: int = DEFAULT_WINDOW_YEARS,
) -> dict[str, object]:
    """Update the Sprint 7 inflation/activity/labor context from BCB SGS."""

    from .ingestion import persist_policy_inputs
    from .macro_series import MACRO_SERIES
    from .publish import publish_overview_json

    if start is not None and start > end:
        raise ValueError("start date must not be after end date")
    if overlap_days < 0:
        raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1:
        raise ValueError("initial_lookback_days must be positive")
    if not 1 <= window_years <= 10:
        raise ValueError("window_years must be between 1 and 10")

    connection = initialize_database(database_path)
    try:
        policy_inserted, policy_unchanged = persist_policy_inputs(
            connection,
            retrieved_at=clock(),
        )
        results = _update_monthly_sgs_series_group(
            connection,
            specs=MACRO_SERIES,
            raw_root=raw_root,
            published_dir=published_dir,
            end=end,
            start=start,
            fetcher=fetcher,
            clock=clock,
            overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days,
            window_years=window_years,
            collector_version="sprint7-macro",
        )
        publish_overview_json(
            connection,
            output_path=overview_path,
            generated_at=clock(),
        )
        return {
            "status": "succeeded",
            "policy_inputs_inserted": policy_inserted,
            "policy_inputs_unchanged": policy_unchanged,
            "series": results,
            "overview_path": str(overview_path),
        }
    finally:
        connection.close()


DEFAULT_CREDIT_OVERLAP_DAYS = 90
DEFAULT_CREDIT_LOOKBACK_DAYS = 5 * 366


def update_credit_context(
    *,
    database_path: str | Path,
    raw_root: str | Path,
    published_dir: str | Path,
    credit_output_path: str | Path,
    end: date,
    start: date | None = None,
    fetcher: FetchBytes = fetch_bytes,
    clock: Clock = utc_now,
    overlap_days: int = DEFAULT_CREDIT_OVERLAP_DAYS,
    initial_lookback_days: int = DEFAULT_CREDIT_LOOKBACK_DAYS,
    window_years: int = DEFAULT_WINDOW_YEARS,
) -> dict[str, object]:
    """Update BCB credit/transmission series and publish one coherent contract."""

    from .credit_series import CREDIT_SERIES
    from .publish.credit_transmission import publish_credit_transmission_json

    if start is not None and start > end:
        raise ValueError("start date must not be after end date")
    if overlap_days < 0:
        raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1:
        raise ValueError("initial_lookback_days must be positive")
    if not 1 <= window_years <= 10:
        raise ValueError("window_years must be between 1 and 10")

    connection = initialize_database(database_path)
    try:
        results = _update_monthly_sgs_series_group(
            connection,
            specs=CREDIT_SERIES,
            raw_root=raw_root,
            published_dir=published_dir,
            end=end,
            start=start,
            fetcher=fetcher,
            clock=clock,
            overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days,
            window_years=window_years,
            collector_version="sprint9-credit",
        )
        publish_credit_transmission_json(
            connection,
            output_path=credit_output_path,
            generated_at=clock(),
        )
        return {
            "status": "succeeded",
            "series": results,
            "credit_output_path": str(credit_output_path),
        }
    finally:
        connection.close()


DEFAULT_YIELD_CURVE_OVERLAP_DAYS = 45
DEFAULT_YIELD_CURVE_LOOKBACK_DAYS = 5 * 366


def resolve_yield_curve_incremental_start(
    connection: sqlite3.Connection,
    *,
    source_id: int,
    end: date,
    overlap_days: int = DEFAULT_YIELD_CURVE_OVERLAP_DAYS,
    initial_lookback_days: int = DEFAULT_YIELD_CURVE_LOOKBACK_DAYS,
) -> date:
    if overlap_days < 0:
        raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1:
        raise ValueError("initial_lookback_days must be positive")
    row = connection.execute(
        "SELECT MAX(reference_date) FROM yield_curve_quotes WHERE source_id = ?",
        (source_id,),
    ).fetchone()
    if row is None or row[0] is None:
        return end - timedelta(days=initial_lookback_days)
    return min(date.fromisoformat(str(row[0])) - timedelta(days=overlap_days), end)


def update_yield_curve(
    *,
    database_path: str | Path,
    raw_root: str | Path,
    published_path: str | Path,
    end: date,
    start: date | None = None,
    fetcher: FetchBytes = fetch_bytes,
    clock: Clock = utc_now,
    overlap_days: int = DEFAULT_YIELD_CURVE_OVERLAP_DAYS,
    initial_lookback_days: int = DEFAULT_YIELD_CURVE_LOOKBACK_DAYS,
) -> dict[str, object]:
    """Ingest Tesouro Direto offered-title rates and publish curve proxies.

    The official resource is a full-history CSV rather than a date-ranged API.
    Every run therefore snapshots the complete provider payload, but only the
    configured recent window is normalized into SQLite.  This keeps the raw
    evidence intact while bounding database/publication size.
    """

    from .collectors.tesouro_direto import (
        CURVE_INSTRUMENT_TYPES,
        TESOURO_DIRETO_RATES_URL,
        parse_tesouro_direto_csv,
    )
    from .db.yield_curve import persist_yield_curve_quotes
    from .ingestion import ensure_tesouro_direto_metadata
    from .publish import publish_yield_curve_json

    if overlap_days < 0:
        raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1:
        raise ValueError("initial_lookback_days must be positive")

    connection = initialize_database(database_path)
    source_id = ensure_tesouro_direto_metadata(connection)
    effective_start = start or resolve_yield_curve_incremental_start(
        connection,
        source_id=source_id,
        end=end,
        overlap_days=overlap_days,
        initial_lookback_days=initial_lookback_days,
    )
    if effective_start > end:
        connection.close()
        raise ValueError("start date must not be after end date")

    started_at = clock()
    run_id = start_ingestion_run(
        connection,
        source_id=source_id,
        started_at=started_at,
        collector_version="sprint8-yield-curve",
        provider="Tesouro Nacional",
    )
    snapshots = RawSnapshotRun(
        root=Path(raw_root),
        provider="tesouro_nacional",
        series_key="tesouro-direto-rates",
        run_id=run_id,
        started_at=started_at,
    )
    received = inserted = unchanged = 0
    persisted = False
    try:
        payload = fetcher(TESOURO_DIRETO_RATES_URL)
        snapshots.save_payload(index=1, url=TESOURO_DIRETO_RATES_URL, payload=payload)
        all_records = parse_tesouro_direto_csv(payload)
        records = [
            record
            for record in all_records
            if record.instrument_type in CURVE_INSTRUMENT_TYPES
            and effective_start <= record.reference_date <= end
        ]
        received = len(records)
        inserted, unchanged = persist_yield_curve_quotes(
            connection,
            source_id=source_id,
            run_id=run_id,
            records=records,
            retrieved_at=clock(),
        )
        persisted = True
        publish_yield_curve_json(
            connection,
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
            status="succeeded",
            finished_at=finished_at,
            records_received=received,
        )
        return {
            "status": "succeeded",
            "run_id": run_id,
            "start": effective_start.isoformat(),
            "end": end.isoformat(),
            "records_in_file": len(all_records),
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
