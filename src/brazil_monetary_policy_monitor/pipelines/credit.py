"""Brazilian credit-transmission pipeline."""

from __future__ import annotations
from datetime import date
from pathlib import Path
from ..collectors.http import fetch_bytes
from ..credit_series import CREDIT_SERIES
from ..db import initialize_database
from ..publish.credit_transmission import publish_credit_transmission_json
from .runtime import Clock, FetchBytes, utc_now
from .sgs import DEFAULT_WINDOW_YEARS, update_sgs_series_group

DEFAULT_CREDIT_OVERLAP_DAYS = 90
DEFAULT_CREDIT_LOOKBACK_DAYS = 5 * 366
COLLECTOR_VERSION = "credit-sgs-v1"


def update_credit_context(*, database_path: str | Path, raw_root: str | Path,
    published_dir: str | Path, credit_output_path: str | Path, end: date,
    start: date | None = None, fetcher: FetchBytes = fetch_bytes, clock: Clock = utc_now,
    overlap_days: int = DEFAULT_CREDIT_OVERLAP_DAYS,
    initial_lookback_days: int = DEFAULT_CREDIT_LOOKBACK_DAYS,
    window_years: int = DEFAULT_WINDOW_YEARS) -> dict[str, object]:
    if start is not None and start > end: raise ValueError("start date must not be after end date")
    if overlap_days < 0: raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1: raise ValueError("initial_lookback_days must be positive")
    if not 1 <= window_years <= 10: raise ValueError("window_years must be between 1 and 10")
    connection = initialize_database(database_path)
    try:
        results = update_sgs_series_group(
            connection, specs=CREDIT_SERIES, raw_root=raw_root, published_dir=published_dir,
            end=end, start=start, fetcher=fetcher, clock=clock, overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days, window_years=window_years,
            collector_version=COLLECTOR_VERSION, frequency="monthly")
        publish_credit_transmission_json(connection, output_path=credit_output_path, generated_at=clock())
        return {"status":"succeeded", "series":results, "credit_output_path":str(credit_output_path)}
    finally:
        connection.close()
