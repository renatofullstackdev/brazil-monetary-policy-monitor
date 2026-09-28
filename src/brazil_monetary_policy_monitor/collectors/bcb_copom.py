"""BCB Copom document API collector primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import re
from urllib.parse import urlencode

COPOM_API_BASE = "https://www.bcb.gov.br/api/servico/sitebcb/copom"


@dataclass(frozen=True, slots=True)
class CopomListRecord:
    meeting_number: int
    reference_date: date
    publication_date: date | None
    title: str


@dataclass(frozen=True, slots=True)
class CopomDocument:
    meeting_number: int
    reference_date: date
    publication_date: date | None
    title: str
    html_text: str
    pdf_url: str | None = None


def build_copom_list_url(kind: str, *, quantity: int = 80) -> str:
    if kind not in {"atas", "comunicados"}:
        raise ValueError("kind must be atas or comunicados")
    if quantity < 1:
        raise ValueError("quantity must be positive")
    return f"{COPOM_API_BASE}/{kind}?{urlencode({'quantidade': quantity})}"


def build_copom_detail_url(kind: str, meeting_number: int) -> str:
    if kind not in {"atas", "comunicados"}:
        raise ValueError("kind must be atas or comunicados")
    if meeting_number < 1:
        raise ValueError("meeting_number must be positive")
    suffix = "atas_detalhes" if kind == "atas" else "comunicados_detalhes"
    return f"{COPOM_API_BASE}/{suffix}?{urlencode({'nro_reuniao': meeting_number})}"


def _root(payload: bytes) -> list[dict[str, object]]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Copom JSON payload") from exc
    if not isinstance(value, dict) or not isinstance(value.get("conteudo"), list):
        raise ValueError("Copom payload must contain a conteudo array")
    return value["conteudo"]


def _date(value: object, *, field: str, optional: bool = False) -> date | None:
    if value in (None, "") and optional:
        return None
    if not isinstance(value, str):
        raise ValueError(f"invalid {field}")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc


def parse_copom_list(payload: bytes, *, kind: str) -> list[CopomListRecord]:
    rows: list[CopomListRecord] = []
    for item in _root(payload):
        raw_number = item.get("nroReuniao") if kind == "atas" else item.get("nro_reuniao")
        if not isinstance(raw_number, int):
            raise ValueError("Copom list row missing meeting number")
        title = item.get("titulo")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Copom list row missing title")
        rows.append(
            CopomListRecord(
                meeting_number=raw_number,
                reference_date=_date(item.get("dataReferencia"), field="dataReferencia"),
                publication_date=_date(item.get("dataPublicacao"), field="dataPublicacao", optional=True),
                title=title.strip(),
            )
        )
    rows.sort(key=lambda row: (row.reference_date, row.meeting_number))
    return rows


def parse_copom_detail(payload: bytes, *, kind: str) -> CopomDocument:
    rows = _root(payload)
    if len(rows) != 1:
        raise ValueError("Copom detail payload must contain exactly one item")
    item = rows[0]
    raw_number = item.get("nroReuniao") if kind == "atas" else item.get("nro_reuniao")
    if not isinstance(raw_number, int):
        raise ValueError("Copom detail missing meeting number")
    title = item.get("titulo")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Copom detail missing title")
    text_field = "textoAta" if kind == "atas" else "textoComunicado"
    html_text = item.get(text_field)
    if not isinstance(html_text, str):
        raise ValueError(f"Copom detail missing {text_field}")
    pdf = item.get("urlPdfAta") if kind == "atas" else None
    return CopomDocument(
        meeting_number=raw_number,
        reference_date=_date(item.get("dataReferencia"), field="dataReferencia"),
        publication_date=_date(item.get("dataPublicacao"), field="dataPublicacao", optional=True),
        title=title.strip(),
        html_text=html_text,
        pdf_url=pdf if isinstance(pdf, str) and pdf else None,
    )


_RATE_RE = re.compile(r"(?:Selic|taxa\s+Selic)[^0-9]{0,40}(\d{1,2}(?:[.,]\d{1,2})?)\s*%", re.I)


def extract_selic_rate(title: str, html_text: str = "") -> float | None:
    for text in (title, html_text):
        match = _RATE_RE.search(text)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def decision_direction(title: str) -> str | None:
    lower = title.lower()
    if "reduz" in lower or "reduzir" in lower:
        return "cut"
    if "eleva" in lower or "aument" in lower:
        return "hike"
    if "mant" in lower:
        return "hold"
    return None
