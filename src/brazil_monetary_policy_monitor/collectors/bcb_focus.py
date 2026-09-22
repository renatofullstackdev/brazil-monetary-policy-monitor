"""Collector helpers for BCB Focus market-expectation OData endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import json
from urllib.parse import urlencode


FOCUS_MONTHLY_ENDPOINT = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
    "ExpectativaMercadoMensais"
)
DEFAULT_PAGE_SIZE = 10_000
DEFAULT_WINDOW_DAYS = 30


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


def iter_focus_windows(
    start: date,
    end: date,
    *,
    max_days: int = DEFAULT_WINDOW_DAYS,
):
    """Yield bounded inclusive date windows for Focus requests.

    Olinda does not expose a reliable pagination contract for this resource, so
    the collector bounds the result set by date instead of depending on $skip.
    """

    if start > end:
        raise ValueError("start date must not be after end date")
    if max_days <= 0:
        raise ValueError("max_days must be positive")

    cursor = start
    span = timedelta(days=max_days - 1)
    while cursor <= end:
        window_end = min(cursor + span, end)
        yield cursor, window_end
        cursor = window_end + timedelta(days=1)


def build_focus_monthly_url(
    start: date,
    end: date,
    *,
    top: int = DEFAULT_PAGE_SIZE,
) -> str:
    if start > end:
        raise ValueError("start date must not be after end date")
    if top <= 0:
        raise ValueError("top must be positive")

    filter_expression = (
        "Indicador eq 'IPCA' "
        f"and Data ge '{start.isoformat()}' and Data le '{end.isoformat()}'"
    )
    query = urlencode(
        {
            "$filter": filter_expression,
            "$select": (
                "Indicador,Data,DataReferencia,Mediana,numeroRespondentes,baseCalculo"
            ),
            "$top": str(top),
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
        raw_base = raw.get("baseCalculo")
        if raw_base is True or raw_base == 1:
            # The endpoint may expose baseCalculo as either an integer or a
            # boolean. Base 1/true represents the five-business-day comparison
            # basis, which is not the current-expectation series used here.
            continue
        if not (raw_base is False or raw_base == 0):
            raise ValueError(f"unexpected Focus baseCalculo: {raw_base!r}")

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
