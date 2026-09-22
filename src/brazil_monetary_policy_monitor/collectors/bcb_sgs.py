"""Collector primitives for Banco Central do Brasil SGS JSON series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
from urllib.parse import urlencode


SGS_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"


@dataclass(frozen=True, slots=True)
class SGSRecord:
    reference_date: date
    value: Decimal


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        # 29 February -> 28 February when the target year is not leap.
        return value.replace(month=2, day=28, year=value.year + years)


def iter_date_windows(
    start: date,
    end: date,
    *,
    max_years: int = 10,
) -> list[tuple[date, date]]:
    """Split an inclusive interval into calendar windows no longer than N years."""

    if start > end:
        raise ValueError("start date must not be after end date")
    if max_years <= 0:
        raise ValueError("max_years must be positive")

    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(_add_years(cursor, max_years) - timedelta(days=1), end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def build_sgs_url(code: int | str, start: date, end: date) -> str:
    if start > end:
        raise ValueError("start date must not be after end date")
    params = urlencode(
        {
            "dataInicial": start.strftime("%d/%m/%Y"),
            "dataFinal": end.strftime("%d/%m/%Y"),
            "formato": "json",
        }
    )
    return f"{SGS_BASE_URL.format(code=code)}?{params}"


def _parse_decimal(raw: object, *, row_number: int) -> Decimal:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"row {row_number}: 'valor' must be a non-empty string")
    text = raw.strip().replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"row {row_number}: invalid numeric value {raw!r}") from exc
    if not value.is_finite():
        raise ValueError(f"row {row_number}: numeric value must be finite")
    return value


def parse_sgs_json(payload: bytes) -> list[SGSRecord]:
    """Validate and normalize a SGS JSON response without partial acceptance."""

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("provider payload is not valid UTF-8 JSON") from exc

    if not isinstance(decoded, list):
        raise ValueError("provider payload root must be a JSON array")

    records: list[SGSRecord] = []
    seen_dates: set[date] = set()
    for row_number, row in enumerate(decoded, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"row {row_number}: expected an object")
        if "data" not in row or "valor" not in row:
            raise ValueError(f"row {row_number}: expected 'data' and 'valor' fields")

        raw_date = row["data"]
        if not isinstance(raw_date, str):
            raise ValueError(f"row {row_number}: 'data' must be a string")
        try:
            reference_date = datetime.strptime(raw_date, "%d/%m/%Y").date()
        except ValueError as exc:
            raise ValueError(f"row {row_number}: invalid SGS date {raw_date!r}") from exc

        if reference_date in seen_dates:
            raise ValueError(f"duplicate reference date in provider payload: {raw_date}")
        seen_dates.add(reference_date)
        records.append(
            SGSRecord(
                reference_date=reference_date,
                value=_parse_decimal(row["valor"], row_number=row_number),
            )
        )

    records.sort(key=lambda record: record.reference_date)
    return records
