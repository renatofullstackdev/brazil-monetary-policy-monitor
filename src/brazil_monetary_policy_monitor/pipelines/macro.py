"""Brazilian inflation, activity and labor-market pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..collectors.http import fetch_bytes
from ..db import initialize_database
from ..ingestion.policy import persist_output_gap_vintages, persist_policy_inputs
from ..macro_series import MACRO_SERIES
from ..publish import publish_overview_json
from .runtime import Clock, FetchBytes, utc_now
from .sgs import DEFAULT_WINDOW_YEARS, update_sgs_series_group

DEFAULT_MACRO_OVERLAP_DAYS = 90
DEFAULT_MACRO_LOOKBACK_DAYS = 5 * 366
COLLECTOR_VERSION = "macro-sgs-v1"


def update_macro_context(
    *, database_path: str | Path, raw_root: str | Path, published_dir: str | Path,
    overview_path: str | Path, end: date, start: date | None = None,
    fetcher: FetchBytes = fetch_bytes, clock: Clock = utc_now,
    overlap_days: int = DEFAULT_MACRO_OVERLAP_DAYS,
    initial_lookback_days: int = DEFAULT_MACRO_LOOKBACK_DAYS,
    window_years: int = DEFAULT_WINDOW_YEARS,
) -> dict[str, object]:
    if start is not None and start > end: raise ValueError("start date must not be after end date")
    if overlap_days < 0: raise ValueError("overlap_days cannot be negative")
    if initial_lookback_days < 1: raise ValueError("initial_lookback_days must be positive")
    if not 1 <= window_years <= 10: raise ValueError("window_years must be between 1 and 10")
    connection = initialize_database(database_path)
    try:
        policy_now = clock()
        policy_inserted, policy_unchanged = persist_policy_inputs(connection, retrieved_at=policy_now)
        gap_inserted, gap_unchanged = persist_output_gap_vintages(connection, retrieved_at=policy_now)
        results = update_sgs_series_group(
            connection, specs=MACRO_SERIES, raw_root=raw_root, published_dir=published_dir,
            end=end, start=start, fetcher=fetcher, clock=clock, overlap_days=overlap_days,
            initial_lookback_days=initial_lookback_days, window_years=window_years,
            collector_version=COLLECTOR_VERSION, frequency="monthly",
        )
        publish_overview_json(connection, output_path=overview_path, generated_at=clock())
        return {"status":"succeeded", "policy_inputs_inserted":policy_inserted + gap_inserted,
                "policy_inputs_unchanged":policy_unchanged + gap_unchanged,
                "policy_parameters_inserted": policy_inserted,
                "output_gap_vintages_inserted": gap_inserted,
                "series":results,
                "overview_path":str(overview_path)}
    finally:
        connection.close()
