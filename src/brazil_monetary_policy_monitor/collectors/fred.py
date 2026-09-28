"""Minimal keyless FRED graph-CSV collector."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO
from math import isfinite
from urllib.parse import urlencode

from .bcb_sgs import SGSRecord

FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def build_fred_url(series_id: str, start: date, end: date) -> str:
    if start > end:
        raise ValueError("start date must not be after end date")
    query = urlencode({"id": series_id, "cosd": start.isoformat(), "coed": end.isoformat()})
    return f"{FRED_GRAPH_CSV_URL}?{query}"


def parse_fred_csv(payload: bytes, *, series_id: str) -> list[SGSRecord]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("FRED CSV is not valid UTF-8") from exc
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or len(reader.fieldnames) < 2:
        raise ValueError("FRED CSV must contain a date column and a value column")
    date_field = "observation_date" if "observation_date" in reader.fieldnames else reader.fieldnames[0]
    value_field = series_id if series_id in reader.fieldnames else reader.fieldnames[1]
    records: list[SGSRecord] = []
    seen: set[date] = set()
    for row in reader:
        raw_date = (row.get(date_field) or "").strip()
        raw_value = (row.get(value_field) or "").strip()
        if not raw_date or raw_value in {"", ".", "NA", "NaN"}:
            continue
        try:
            reference = date.fromisoformat(raw_date)
            value = Decimal(raw_value)
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f"invalid FRED row: {row}") from exc
        if not isfinite(float(value)):
            raise ValueError("FRED values must be finite")
        if reference in seen:
            raise ValueError(f"duplicate FRED reference date: {reference}")
        seen.add(reference)
        records.append(SGSRecord(reference_date=reference, value=value))
    records.sort(key=lambda item: item.reference_date)
    return records
