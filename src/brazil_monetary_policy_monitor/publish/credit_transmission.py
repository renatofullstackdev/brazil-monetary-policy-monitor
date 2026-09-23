"""Publish the static credit/transmission contract consumed by the browser UI."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

from ..credit_series import CREDIT_SERIES_BY_KEY
from ..db.observations import observations_latest
from ..models.credit import real_balance_growth_percent
from .atomic import write_json_atomic


CREDIT_TRANSMISSION_SCHEMA_VERSION = 1
IPCA_SERIES_KEY = "br.ipca.monthly"


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _series_metadata(connection: sqlite3.Connection, series_key: str):
    return connection.execute(
        """
        SELECT s.*, src.provider, src.name AS source_name,
               src.documentation_url AS source_documentation_url
        FROM series AS s
        JOIN sources AS src ON src.id = s.source_id
        WHERE s.key = ?
        """,
        (series_key,),
    ).fetchone()


def _source_document(metadata) -> dict[str, Any] | None:
    if metadata is None:
        return None
    try:
        local = json.loads(metadata["metadata_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        local = {}
    return {
        "provider": metadata["provider"],
        "name": metadata["source_name"],
        "documentation_url": local.get("documentation_url") or metadata["source_documentation_url"],
    }


def _ym(value: str) -> tuple[int, int]:
    parsed = date.fromisoformat(value)
    return parsed.year, parsed.month


def _month_index(value: str) -> int:
    year, month = _ym(value)
    return year * 12 + month


def _monthly_rows(connection: sqlite3.Connection, series_key: str) -> list[sqlite3.Row]:
    return observations_latest(connection, series_key)


def _simple_history(connection: sqlite3.Connection, series_key: str) -> list[dict[str, Any]]:
    return [
        {
            "date": row["reference_period"],
            "value": float(row["value"]),
            "available_at": row["available_at"],
        }
        for row in _monthly_rows(connection, series_key)
    ]


def _inflation_windows(connection: sqlite3.Connection) -> dict[int, tuple[float, str]]:
    """Map ending month index to (12m inflation percent, latest availability)."""

    rows = _monthly_rows(connection, IPCA_SERIES_KEY)
    by_index = {_month_index(str(row["reference_period"])): row for row in rows}
    result: dict[int, tuple[float, str]] = {}
    for ending_index in sorted(by_index):
        indexes = range(ending_index - 11, ending_index + 1)
        window = [by_index.get(index) for index in indexes]
        if any(row is None for row in window):
            continue
        typed = [row for row in window if row is not None]
        factor = math.prod(1.0 + float(row["value"]) / 100.0 for row in typed)
        result[ending_index] = (
            (factor - 1.0) * 100.0,
            max(str(row["available_at"]) for row in typed),
        )
    return result


def _real_growth_history(
    connection: sqlite3.Connection,
    balance_series_key: str,
) -> list[dict[str, Any]]:
    balances = _monthly_rows(connection, balance_series_key)
    by_index = {_month_index(str(row["reference_period"])): row for row in balances}
    inflation = _inflation_windows(connection)
    result: list[dict[str, Any]] = []
    for current_index in sorted(by_index):
        previous = by_index.get(current_index - 12)
        current = by_index[current_index]
        inflation_item = inflation.get(current_index)
        if previous is None or inflation_item is None:
            continue
        inflation_12m, inflation_available_at = inflation_item
        value = real_balance_growth_percent(
            float(current["value"]),
            float(previous["value"]),
            inflation_12m,
        )
        result.append(
            {
                "date": current["reference_period"],
                "value": value,
                "available_at": max(
                    str(current["available_at"]),
                    str(previous["available_at"]),
                    inflation_available_at,
                ),
            }
        )
    return result


def _series_document(
    connection: sqlite3.Connection,
    *,
    series_key: str,
    label: str,
    values: list[dict[str, Any]],
    unit: str,
    data_kind: str,
    transformation: str,
    note: str,
    required_inputs: list[str],
) -> dict[str, Any]:
    metadata = _series_metadata(connection, series_key)
    spec = CREDIT_SERIES_BY_KEY.get(series_key)
    if not values:
        return {
            "key": series_key,
            "label": label,
            "status": "unavailable",
            "data_kind": data_kind,
            "unit": unit,
            "frequency": "monthly",
            "transformation": transformation,
            "required_inputs": required_inputs,
            "note": note,
            "latest": None,
            "observations": [],
            "source": _source_document(metadata),
        }
    latest = values[-1]
    return {
        "key": series_key,
        "label": label,
        "title": metadata["title"] if metadata is not None else (spec.title if spec else label),
        "description": metadata["description"] if metadata is not None else (spec.description if spec else note),
        "status": "available",
        "data_kind": data_kind,
        "unit": unit,
        "frequency": "monthly",
        "transformation": transformation,
        "required_inputs": [],
        "note": note,
        "latest": latest,
        "observations": values,
        "source": _source_document(metadata),
    }


def _observed_series_document(
    connection: sqlite3.Connection,
    *,
    series_key: str,
    label: str,
    note: str,
) -> dict[str, Any]:
    spec = CREDIT_SERIES_BY_KEY[series_key]
    return _series_document(
        connection,
        series_key=series_key,
        label=label,
        values=_simple_history(connection, series_key),
        unit=spec.unit_normalized,
        data_kind="observed",
        transformation="identity",
        note=note,
        required_inputs=[series_key],
    )


def _real_growth_document(
    connection: sqlite3.Connection,
    *,
    series_key: str,
    label: str,
) -> dict[str, Any]:
    return _series_document(
        connection,
        series_key=series_key,
        label=label,
        values=_real_growth_history(connection, series_key),
        unit="percent_year_over_year_real",
        data_kind="derived",
        transformation="nominal_balance_yoy_deflated_by_compounded_ipca_12m",
        note=(
            "Crescimento real em 12 meses do saldo nominal, deflacionado pelo IPCA composto "
            "nos mesmos 12 meses. Não é uma série publicada diretamente pelo BCB."
        ),
        required_inputs=[series_key, IPCA_SERIES_KEY],
    )


def build_credit_transmission_document(
    connection: sqlite3.Connection,
    *,
    generated_at: datetime,
) -> dict[str, Any]:
    free_growth = _real_growth_document(
        connection,
        series_key="br.credit.free.balance",
        label="Crédito livre — crescimento real (12m)",
    )
    directed_growth = _real_growth_document(
        connection,
        series_key="br.credit.directed.balance",
        label="Crédito direcionado — crescimento real (12m)",
    )
    free_rate = _observed_series_document(
        connection,
        series_key="br.credit.free.interest_rate",
        label="Juros do crédito livre",
        note="Taxa média anual das novas operações; a composição das concessões pode mudar ao longo do tempo.",
    )
    directed_rate = _observed_series_document(
        connection,
        series_key="br.credit.directed.interest_rate",
        label="Juros do crédito direcionado",
        note="Taxa média anual das novas operações direcionadas; não deve ser comparada a uma taxa livre sem considerar composição e regras específicas.",
    )
    free_delinquency = _observed_series_document(
        connection,
        series_key="br.credit.free.delinquency",
        label="Inadimplência — crédito livre",
        note="Percentual da carteira com pelo menos uma parcela em atraso superior a 90 dias.",
    )
    directed_delinquency = _observed_series_document(
        connection,
        series_key="br.credit.directed.delinquency",
        label="Inadimplência — crédito direcionado",
        note="Percentual da carteira com pelo menos uma parcela em atraso superior a 90 dias.",
    )

    groups = {
        "real_growth": {
            "label": "Crescimento real do saldo",
            "unit": "percent_year_over_year_real",
            "series": [free_growth, directed_growth],
        },
        "interest_rates": {
            "label": "Taxas médias das novas operações",
            "unit": "percent_per_year",
            "series": [free_rate, directed_rate],
        },
        "delinquency": {
            "label": "Inadimplência acima de 90 dias",
            "unit": "percent",
            "series": [free_delinquency, directed_delinquency],
        },
    }
    all_series = [item for group in groups.values() for item in group["series"]]
    available = sum(item["status"] == "available" for item in all_series)
    dates = [
        item["latest"]["date"]
        for item in all_series
        if item["status"] == "available" and item.get("latest")
    ]
    return {
        "schema_version": CREDIT_TRANSMISSION_SCHEMA_VERSION,
        "view": "credit_transmission",
        "country": "BR",
        "generated_at": _iso_z(generated_at),
        "knowledge_mode": "latest_revision",
        "status": "available" if available else "unavailable",
        "availability": {
            "available_series": available,
            "total_series": len(all_series),
        },
        "latest_reference": max(dates) if dates else None,
        "groups": groups,
        "notes": [
            "O bloco é descritivo: não atribui movimentos de crédito exclusivamente à Selic.",
            "Crescimento real usa o saldo nominal do BCB e o IPCA mensal já armazenado pelo monitor.",
            "Taxas médias referem-se a novas operações e podem variar também por composição, risco e condições de oferta de crédito.",
            "Inadimplência é a proporção da carteira com atraso superior a 90 dias.",
        ],
    }


def publish_credit_transmission_json(
    connection: sqlite3.Connection,
    *,
    output_path: str | Path,
    generated_at: datetime,
) -> Path:
    return write_json_atomic(
        build_credit_transmission_document(connection, generated_at=generated_at),
        output_path,
    )
