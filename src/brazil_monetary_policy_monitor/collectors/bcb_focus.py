"""Collector helpers for BCB Focus market-expectation OData endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from urllib.parse import urlencode


FOCUS_MONTHLY_ENDPOINT = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
    "ExpectativaMercadoMensais"
)
DEFAULT_PAGE_SIZE = 10_000


@dataclass(frozen=True, slots=True)
class FocusMonthlyRecord:
    survey_date: date
    target_month: date
    median: Decimal
    respondent_count: int | None
    base_calculation: int


def _parse_reference_month(value: object) -> date:
    if not isinstance(value, str):
        raise ValueError("Focus DataReferencia must be a string")
    try:
        month_text, year_text = value.split("/", 1)
        month = int(month_text)
        year = int(year_text)
        return date(year, month, 1)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid Focus DataReferencia: {value!r}") from exc


def build_focus_monthly_url(
    start: date,
    end: date,
    *,
    skip: int = 0,
    top: int = DEFAULT_PAGE_SIZE,
) -> str:
    if start > end:
        raise ValueError("start date must not be after end date")
    if skip < 0:
        raise ValueError("skip cannot be negative")
    if top <= 0:
        raise ValueError("top must be positive")

    filter_expression = (
        "Indicador eq 'IPCA' and baseCalculo eq 0 "
        f"and Data ge '{start.isoformat()}' and Data le '{end.isoformat()}'"
    )
    query = urlencode(
        {
            "$filter": filter_expression,
            "$select": (
                "Indicador,Data,DataReferencia,Mediana,numeroRespondentes,baseCalculo"
            ),
            "$orderby": "Data asc,DataReferencia asc",
            "$top": str(top),
            "$skip": str(skip),
            "$format": "json",
        }
    )
    return f"{FOCUS_MONTHLY_ENDPOINT}?{query}"


def parse_focus_monthly_json(payload: bytes) -> list[FocusMonthlyRecord]:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Focus response is not valid UTF-8 JSON") from exc

    if not isinstance(document, dict) or not isinstance(document.get("value"), list):
        raise ValueError("Focus response must be an object containing a value array")

    records: list[FocusMonthlyRecord] = []
    seen: set[tuple[date, date]] = set()
    for raw in document["value"]:
        if not isinstance(raw, dict):
            raise ValueError("Focus value entries must be objects")
        if raw.get("Indicador") != "IPCA":
            raise ValueError(f"unexpected Focus indicator: {raw.get('Indicador')!r}")
        if raw.get("baseCalculo") != 0:
            raise ValueError(f"unexpected Focus baseCalculo: {raw.get('baseCalculo')!r}")

        try:
            survey_date = date.fromisoformat(str(raw["Data"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid Focus Data: {raw.get('Data')!r}") from exc
        target_month = _parse_reference_month(raw.get("DataReferencia"))

        try:
            median = Decimal(str(raw["Mediana"]))
        except (KeyError, InvalidOperation) as exc:
            raise ValueError(f"invalid Focus Mediana: {raw.get('Mediana')!r}") from exc
        if not median.is_finite():
            raise ValueError("Focus Mediana must be finite")

        raw_count = raw.get("numeroRespondentes")
        if raw_count is None:
            respondent_count = None
        elif isinstance(raw_count, int) and raw_count >= 0:
            respondent_count = raw_count
        else:
            raise ValueError(f"invalid Focus numeroRespondentes: {raw_count!r}")

        key = (survey_date, target_month)
        if key in seen:
            raise ValueError(
                "duplicate Focus survey/reference month in response: "
                f"{survey_date.isoformat()} / {target_month:%Y-%m}"
            )
        seen.add(key)
        records.append(
            FocusMonthlyRecord(
                survey_date=survey_date,
                target_month=target_month,
                median=median,
                respondent_count=respondent_count,
                base_calculation=0,
            )
        )

    records.sort(key=lambda item: (item.survey_date, item.target_month))
    return records
