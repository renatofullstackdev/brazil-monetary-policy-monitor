"""ANBIMA ETTJ zero-coupon curve collector."""

from __future__ import annotations

import csv
from datetime import date
from io import StringIO

from ..models.term_structure import (
    ANBIMA_BREAKEVEN_CURVE,
    ANBIMA_NOMINAL_CURVE,
    ANBIMA_REAL_CURVE,
    MarketCurvePoint,
)

ANBIMA_ETTJ_PAGE_URL = "https://www.anbima.com.br/informacoes/est-termo/CZ.asp"
ANBIMA_ETTJ_DOWNLOAD_URL = "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp"
ANBIMA_ETTJ_METHODOLOGY_URL = "https://www.anbima.com.br/data/files/F9/73/38/F5/C2DEA510CD3B4DA568A80AC2/ETTJ-Intra-Metodologia.pdf"


def request_fields(reference_date: date) -> dict[str, str]:
    return {
        "escolha": "2",
        "Idioma": "PT",
        "saida": "csv",
        "Dt_Ref": reference_date.strftime("%d/%m/%Y"),
    }


def _decode(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("ANBIMA payload could not be decoded")


def _number(value: str) -> float:
    text = value.strip()
    if not text:
        raise ValueError("empty ANBIMA number")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return float(text)


def _tenor_business_days(value: str) -> int:
    """Parse ANBIMA integer vertices, where dots are thousands separators."""

    text = value.strip().replace(".", "")
    if not text or not text.isdigit():
        raise ValueError("invalid ANBIMA tenor")
    tenor = int(text)
    if tenor <= 0:
        raise ValueError("ANBIMA tenor must be positive")
    return tenor


def _reference_date(rows: list[list[str]]) -> date:
    for row in rows[:8]:
        if not row:
            continue
        value = row[0].strip()
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
        try:
            day, month, year = value.split("/")
            return date(int(year), int(month), int(day))
        except (ValueError, TypeError):
            continue
    raise ValueError("ANBIMA reference date not found")


def parse_anbima_ettj_csv(payload: bytes) -> list[MarketCurvePoint]:
    text = _decode(payload)
    rows = [[cell.strip() for cell in row] for row in csv.reader(StringIO(text), delimiter=";")]
    reference = _reference_date(rows)
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if row and row[0].lower().replace("é", "e").startswith("vertices")
        ),
        None,
    )
    if header_index is None:
        raise ValueError("ANBIMA ETTJ vertices table not found")

    result: list[MarketCurvePoint] = []
    for row in rows[header_index + 1 :]:
        if len(row) < 4 or not row[0].strip():
            continue
        try:
            tenor = _tenor_business_days(row[0])
            real = _number(row[1])
            nominal = _number(row[2])
            breakeven = _number(row[3])
        except ValueError:
            continue
        for curve_key, value in (
            (ANBIMA_REAL_CURVE, real),
            (ANBIMA_NOMINAL_CURVE, nominal),
            (ANBIMA_BREAKEVEN_CURVE, breakeven),
        ):
            result.append(
                MarketCurvePoint(
                    curve_key=curve_key,
                    reference_date=reference,
                    point_key=f"du:{tenor}",
                    tenor_business_days=tenor,
                    rate_percent=value,
                )
            )
    if not result:
        raise ValueError("ANBIMA ETTJ payload contains no curve points")
    return result
