"""Brazilian external-sector and exchange-rate pipeline."""

from __future__ import annotations
from datetime import date
from pathlib import Path
from ..collectors.http import fetch_bytes
from ..db import initialize_database
from ..external_series import EXTERNAL_DAILY_SERIES, EXTERNAL_MONTHLY_SERIES
from ..publish.external import publish_external_json
from .runtime import Clock, FetchBytes, utc_now
from .sgs import DEFAULT_WINDOW_YEARS, update_sgs_series_group

DEFAULT_EXTERNAL_OVERLAP_DAYS = 45
DEFAULT_EXTERNAL_LOOKBACK_DAYS = 10 * 366
DAILY_COLLECTOR_VERSION = "external-sgs-daily-v1"
MONTHLY_COLLECTOR_VERSION = "external-sgs-monthly-v1"


def update_external_context(*, database_path: str | Path, raw_root: str | Path,
    published_dir: str | Path, external_output_path: str | Path, end: date,
    start: date | None = None, fetcher: FetchBytes = fetch_bytes, clock: Clock = utc_now,
    overlap_days: int = DEFAULT_EXTERNAL_OVERLAP_DAYS,
    initial_lookback_days: int = DEFAULT_EXTERNAL_LOOKBACK_DAYS,
    window_years: int = DEFAULT_WINDOW_YEARS) -> dict[str, object]:
    if start is not None and start > end: raise ValueError("start date must not be after end date")
    if overlap_days < 0: raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1: raise ValueError("initial_lookback_days must be positive")
    if not 1 <= window_years <= 10: raise ValueError("window_years must be between 1 and 10")
    connection = initialize_database(database_path)
    try:
        daily = update_sgs_series_group(
            connection, specs=EXTERNAL_DAILY_SERIES, raw_root=raw_root, published_dir=published_dir,
            end=end, start=start, fetcher=fetcher, clock=clock, overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days, window_years=window_years,
            collector_version=DAILY_COLLECTOR_VERSION, frequency="daily")
        monthly = update_sgs_series_group(
            connection, specs=EXTERNAL_MONTHLY_SERIES, raw_root=raw_root, published_dir=published_dir,
            end=end, start=start, fetcher=fetcher, clock=clock, overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days, window_years=window_years,
            collector_version=MONTHLY_COLLECTOR_VERSION, frequency="monthly")
        publish_external_json(connection, output_path=external_output_path, generated_at=clock())
        return {"status":"succeeded", "series":[*daily,*monthly],
                "external_output_path":str(external_output_path)}
    finally:
        connection.close()
