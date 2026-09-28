"""Brazilian fiscal-flow and current DPF profile pipeline."""

from __future__ import annotations
from datetime import date
from pathlib import Path
from ..collectors.http import fetch_bytes
from ..db import initialize_database
from ..fiscal_series import FISCAL_SERIES
from ..ingestion.fiscal import persist_fiscal_profile_inputs
from ..publish.fiscal import publish_fiscal_json
from .runtime import Clock, FetchBytes, utc_now
from .sgs import DEFAULT_WINDOW_YEARS, update_sgs_series_group

DEFAULT_FISCAL_OVERLAP_DAYS = 90
DEFAULT_FISCAL_LOOKBACK_DAYS = 10 * 366
COLLECTOR_VERSION = "fiscal-sgs-rmd-v1"


def update_fiscal_context(*, database_path: str | Path, raw_root: str | Path,
    published_dir: str | Path, fiscal_output_path: str | Path, end: date,
    start: date | None = None, fetcher: FetchBytes = fetch_bytes, clock: Clock = utc_now,
    overlap_days: int = DEFAULT_FISCAL_OVERLAP_DAYS,
    initial_lookback_days: int = DEFAULT_FISCAL_LOOKBACK_DAYS,
    window_years: int = DEFAULT_WINDOW_YEARS) -> dict[str, object]:
    if start is not None and start > end: raise ValueError("start date must not be after end date")
    if overlap_days < 0: raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1: raise ValueError("initial_lookback_days must be positive")
    if not 1 <= window_years <= 10: raise ValueError("window_years must be between 1 and 10")
    connection = initialize_database(database_path)
    try:
        profile_inserted, profile_unchanged = persist_fiscal_profile_inputs(connection, retrieved_at=clock())
        results = update_sgs_series_group(
            connection, specs=FISCAL_SERIES, raw_root=raw_root, published_dir=published_dir,
            end=end, start=start, fetcher=fetcher, clock=clock, overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days, window_years=window_years,
            collector_version=COLLECTOR_VERSION, frequency="monthly")
        publish_fiscal_json(connection, output_path=fiscal_output_path, generated_at=clock())
        return {"status":"succeeded", "profile_inputs_inserted":profile_inserted,
                "profile_inputs_unchanged":profile_unchanged, "series":results,
                "fiscal_output_path":str(fiscal_output_path)}
    finally:
        connection.close()
