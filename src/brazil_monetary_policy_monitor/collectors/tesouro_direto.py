"""Collector contract for Tesouro Direto daily offered-title rates."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import unicodedata


TESOURO_DIRETO_RATES_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)
TESOURO_DIRETO_DATASET_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "taxas-dos-titulos-ofertados-pelo-tesouro-direto"
)
TESOURO_DIRETO_METADATA_URL = (
    "https://tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "1a8eb2e3-4902-4a38-a1eb-6410f23d90de/download/Taxa.pdf"
)

NOMINAL_INSTRUMENT_TYPES = frozenset(
    {"Tesouro Prefixado", "Tesouro Prefixado com Juros Semestrais"}
)
REAL_INSTRUMENT_TYPES = frozenset(
    {"Tesouro IPCA+", "Tesouro IPCA+ com Juros Semestrais"}
)
CURVE_INSTRUMENT_TYPES = NOMINAL_INSTRUMENT_TYPES | REAL_INSTRUMENT_TYPES


@dataclass(frozen=True, slots=True)
class TreasuryQuote:
    instrument_type: str
    maturity_date: date
    reference_date: date
    buy_yield: Decimal | None
    sell_yield: Decimal | None
    buy_price: Decimal | None
    sell_price: Decimal | None
    base_price: Decimal | None


def _normalize_header(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(ascii_text.lower().split())


_HEADER_MAP = {
    "tipo titulo": "instrument_type",
    "data vencimento": "maturity_date",
    "data base": "reference_date",
    "taxa compra manha": "buy_yield",
    "taxa venda manha": "sell_yield",
    "pu compra manha": "buy_price",
    "pu venda manha": "sell_price",
    "pu base manha": "base_price",
}


def _decode(payload: bytes) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload.decode("latin-1")


def _parse_date(raw: str, *, row_number: int, field: str) -> date:
    value = raw.strip()
    try:
        day, month, year = (int(part) for part in value.split("/"))
        return date(year, month, day)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"row {row_number}: invalid {field}: {raw!r}") from exc


def _parse_decimal(raw: str | None, *, row_number: int, field: str) -> Decimal | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value or value in {"-", "--"}:
        return None
    canonical = value.replace(".", "").replace(",", ".")
    try:
        result = Decimal(canonical)
    except InvalidOperation as exc:
        raise ValueError(f"row {row_number}: invalid {field}: {raw!r}") from exc
    if not result.is_finite():
        raise ValueError(f"row {row_number}: non-finite {field}: {raw!r}")
    return result


def parse_tesouro_direto_csv(payload: bytes) -> list[TreasuryQuote]:
    """Parse and validate the official semicolon-separated Treasury CSV.

    The source uses Brazilian decimal notation. Header matching is accent- and
    case-insensitive because historical exports have varied slightly in casing.
    """

    text = _decode(payload)
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise ValueError("Tesouro Direto CSV has no header")

    normalized = {_normalize_header(header): header for header in reader.fieldnames}
    missing = [name for name in _HEADER_MAP if name not in normalized]
    if missing:
        raise ValueError(f"Tesouro Direto CSV missing required columns: {', '.join(missing)}")

    records: list[TreasuryQuote] = []
    seen: set[tuple[str, date, date]] = set()
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        values = {
            target: row[normalized[source]]
            for source, target in _HEADER_MAP.items()
        }
        instrument_type = (values["instrument_type"] or "").strip()
        if not instrument_type:
            raise ValueError(f"row {row_number}: empty instrument type")
        maturity = _parse_date(values["maturity_date"], row_number=row_number, field="maturity date")
        reference = _parse_date(values["reference_date"], row_number=row_number, field="reference date")
        if maturity <= reference:
            raise ValueError(f"row {row_number}: maturity must be after reference date")

        record = TreasuryQuote(
            instrument_type=instrument_type,
            maturity_date=maturity,
            reference_date=reference,
            buy_yield=_parse_decimal(values["buy_yield"], row_number=row_number, field="buy yield"),
            sell_yield=_parse_decimal(values["sell_yield"], row_number=row_number, field="sell yield"),
            buy_price=_parse_decimal(values["buy_price"], row_number=row_number, field="buy price"),
            sell_price=_parse_decimal(values["sell_price"], row_number=row_number, field="sell price"),
            base_price=_parse_decimal(values["base_price"], row_number=row_number, field="base price"),
        )
        key = (record.instrument_type, record.maturity_date, record.reference_date)
        if key in seen:
            raise ValueError(f"row {row_number}: duplicate title/date observation: {key}")
        seen.add(key)
        records.append(record)

    records.sort(key=lambda item: (item.reference_date, item.instrument_type, item.maturity_date))
    return records
