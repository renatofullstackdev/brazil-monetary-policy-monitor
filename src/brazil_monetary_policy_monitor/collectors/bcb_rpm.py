"""BCB Relatório de Política Monetária API collector primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from urllib.parse import urlencode

RPM_API_BASE = "https://www.bcb.gov.br/api/servico/sitebcb/rpm"


@dataclass(frozen=True, slots=True)
class RpmReport:
    identifier: str
    publication_date: date
    url: str
    page_url: str
    edition: str | None = None
    volume: str | None = None


@dataclass(frozen=True, slots=True)
class RpmCalendarEntry:
    event: str
    event_date: date
    description: str


def build_rpm_reports_url(*, quantity: int = 12) -> str:
    if quantity < 1:
        raise ValueError("quantity must be positive")
    return f"{RPM_API_BASE}/relatorios?{urlencode({'quantidade': quantity})}"


def build_rpm_calendar_url(*, start_date: date = date(2025, 1, 1)) -> str:
    return f"{RPM_API_BASE}/proximos-relatorios?{urlencode({'inicioAgenda': start_date.isoformat()})}"


def _root(payload: bytes) -> list[dict[str, object]]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid RPM JSON payload") from exc
    if not isinstance(value, dict) or not isinstance(value.get("conteudo"), list):
        raise ValueError("RPM payload must contain a conteudo array")
    return value["conteudo"]


def _date(value: object, *, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"invalid {field}")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc


def parse_rpm_reports(payload: bytes) -> list[RpmReport]:
    reports: list[RpmReport] = []
    for item in _root(payload):
        identifier = item.get("identificador")
        url = item.get("url")
        page_url = item.get("linkPaginaBC")
        if not isinstance(identifier, str) or len(identifier) != 6 or not identifier.isdigit():
            raise ValueError("RPM report missing YYYYMM identifier")
        if not isinstance(url, str) or not url:
            raise ValueError("RPM report missing PDF URL")
        if not isinstance(page_url, str) or not page_url:
            raise ValueError("RPM report missing BCB page URL")
        reports.append(
            RpmReport(
                identifier=identifier,
                publication_date=_date(item.get("dataReferencia"), field="dataReferencia"),
                url=url,
                page_url=page_url,
                edition=item.get("edicao") if isinstance(item.get("edicao"), str) else None,
                volume=item.get("volume") if isinstance(item.get("volume"), str) else None,
            )
        )
    reports.sort(key=lambda item: (item.publication_date, item.identifier))
    return reports


def parse_rpm_calendar(payload: bytes) -> list[RpmCalendarEntry]:
    entries: list[RpmCalendarEntry] = []
    for item in _root(payload):
        event = item.get("evento")
        description = item.get("descricao")
        if not isinstance(event, str) or not event.strip():
            raise ValueError("RPM calendar row missing event")
        if not isinstance(description, str):
            raise ValueError("RPM calendar row missing description")
        entries.append(
            RpmCalendarEntry(
                event=event.strip(),
                event_date=_date(item.get("dataEvento"), field="dataEvento"),
                description=description.strip(),
            )
        )
    entries.sort(key=lambda item: (item.event_date, item.event))
    return entries


def reference_quarter(value: date) -> str:
    quarter = (value.month - 1) // 3 + 1
    return f"{value.year}-Q{quarter}"
