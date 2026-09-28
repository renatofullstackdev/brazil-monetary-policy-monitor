"""Publish the static fiscal context consumed by the browser UI."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from ..fiscal_series import FISCAL_SERIES_BY_KEY
from ..vintages import KnowledgeContext, build_knowledge_context, observation_rows, parameter_row
from .atomic import write_json_atomic
from .indicator_contract import structure_indicator_contract


FLOW_KEYS = (
    "br.fiscal.primary_result_12m_gdp",
    "br.fiscal.nominal_interest_12m_gdp",
    "br.fiscal.nominal_result_12m_gdp",
)
DEBT_KEYS = (
    "br.fiscal.dbgg_gdp",
    "br.fiscal.dlgg_gdp",
    "br.fiscal.dlsp_gdp",
)
DBGG_KEY = DEBT_KEYS[0]
PROFILE_KEYS = (
    "br.dpf.stock_brl_billions",
    "br.dpf.maturing_12m_share",
    "br.dpf.average_term_years",
    "br.dpf.average_cost_12m",
    "br.dpf.liquidity_reserve_brl_billions",
    "br.dpf.liquidity_index_months",
)
COMPOSITION_KEYS = (
    ("fixed_rate", "Prefixado", "br.dpf.composition.fixed_rate_share"),
    ("price_index", "Índice de preços", "br.dpf.composition.price_index_share"),
    ("floating_rate", "Taxa flutuante", "br.dpf.composition.floating_rate_share"),
    ("fx", "Câmbio", "br.dpf.composition.fx_share"),
)


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _series_document(connection: sqlite3.Connection, key: str, context: KnowledgeContext) -> dict[str, Any]:
    rows = observation_rows(connection, key, context)
    spec = FISCAL_SERIES_BY_KEY[key]
    latest = rows[-1] if rows else None
    return {
        "key": key,
        "label": spec.title,
        "title": spec.title,
        "definition": spec.description,
        "kind": spec.data_kind,
        "data_kind": spec.data_kind,
        "unit": spec.unit_normalized,
        "frequency": spec.frequency,
        "transformation": spec.transformation,
        "status": "available" if rows else "unavailable",
        "inputs": [],
        "missing_inputs": [] if rows else [key],
        "caveats": [],
        "source": {
            "provider": "BCB",
            "name": f"SGS {spec.code}",
            "documentation_url": spec.documentation_url,
            "sgs_code": spec.code,
        },
        "latest": None if latest is None else {
            "date": latest["reference_period"],
            "value": float(latest["value"]),
            "available_at": latest["available_at"],
        },
        "observations": [
            {
                "date": row["reference_period"],
                "value": float(row["value"]),
                "available_at": row["available_at"],
            }
            for row in rows
        ],
    }


def _parameter_document(connection: sqlite3.Connection, key: str, context: KnowledgeContext) -> dict[str, Any] | None:
    row = parameter_row(connection, key, context)
    if row is None:
        return None
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "key": key,
        "value": float(row["value"]),
        "unit": row["unit"],
        "kind": row["data_kind"],
        "effective_from": row["effective_from"],
        "published_at": row["published_at"],
        "source_reference": row["source_reference"],
        "methodology": row["methodology"],
        "reference_period": metadata.get("reference_period"),
        "source_url": metadata.get("source_url") or row["source_documentation_url"],
        "source_label": metadata.get("source_label") or row["source_name"],
        "caveats": [metadata["note"]] if metadata.get("note") else [],
    }


def build_fiscal_document(
    connection: sqlite3.Connection,
    *,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> dict[str, Any]:
    context = build_knowledge_context(
        generated_at=generated_at, knowledge_mode=knowledge_mode, knowledge_cutoff=knowledge_cutoff
    )
    series = {key: _series_document(connection, key, context) for key in (*FLOW_KEYS, *DEBT_KEYS)}
    profile = {key: _parameter_document(connection, key, context) for key in PROFILE_KEYS}
    composition = []
    for code, label, key in COMPOSITION_KEYS:
        item = _parameter_document(connection, key, context)
        composition.append({
            "code": code,
            "label": label,
            "key": key,
            "value": None if item is None else item["value"],
            "unit": "percent",
            "source_reference": None if item is None else item["source_reference"],
        })

    available_profile = [item for item in profile.values() if item is not None]
    reference_period = None
    published_at = None
    if available_profile:
        reference_period = max(str(item["reference_period"]) for item in available_profile if item["reference_period"])
        published_at = max(str(item["published_at"]) for item in available_profile if item["published_at"])

    return structure_indicator_contract({
        "view": "fiscal",
        "generated_at": _iso_z(generated_at),
        **context.contract_fields(),
        "sign_convention": {
            "nfsp": "positive_deficit_negative_surplus",
            "note": (
                "Os três fluxos seguem o sinal oficial das NFSP: positivo indica necessidade de "
                "financiamento/déficit e negativo, superávit. Juros nominais não são tratados "
                "como medida autônoma de impulso fiscal."
            ),
        },
        "flows": [series[key] for key in FLOW_KEYS],
        "debt_positions": [series[key] for key in DEBT_KEYS],
        "dpf_profile": {
            "status": "available" if available_profile else "unavailable",
            "reference_period": reference_period,
            "published_at": published_at,
            "source": {
                "provider": "Tesouro Nacional",
                "name": "Relatório Mensal da Dívida Pública Federal (RMD)",
                "note": (
                    "Snapshot documental versionado. O monitor não reconstrói prazo médio, custo "
                    "ou liquidez a partir de uma base mais simples."
                ),
            },
            "metrics": profile,
            "composition": composition,
        },
    })


def publish_fiscal_json(
    connection: sqlite3.Connection,
    *,
    output_path: str | Path,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> Path:
    return write_json_atomic(
        build_fiscal_document(
            connection, generated_at=generated_at, knowledge_mode=knowledge_mode, knowledge_cutoff=knowledge_cutoff
        ),
        output_path,
    )
