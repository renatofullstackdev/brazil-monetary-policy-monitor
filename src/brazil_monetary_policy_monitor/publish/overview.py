"""Publish the static overview contract consumed by the browser UI."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

from ..db.observations import observations_latest
from ..db.parameters import parameter_latest
from ..horizons import resolve_br_policy_horizon
from ..ingestion import FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY, SELIC_SERIES_KEY
from ..macro_series import MACRO_SERIES_BY_KEY
from ..models.monetary import prospective_taylor
from .atomic import write_json_atomic


OVERVIEW_SCHEMA_VERSION = 1


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _unavailable(
    *, key: str, label: str, data_kind: str, unit: str,
    required_inputs: list[str], note: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": "unavailable",
        "data_kind": data_kind,
        "unit": unit,
        "required_inputs": required_inputs,
        "note": note,
        "latest": None,
        "observations": [],
        "source": None,
    }


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


def _metadata_documentation_url(metadata) -> str | None:
    try:
        local = json.loads(metadata["metadata_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        local = {}
    return local.get("documentation_url") or metadata["source_documentation_url"]


def _source_document(metadata) -> dict[str, Any]:
    return {
        "provider": metadata["provider"],
        "name": metadata["source_name"],
        "documentation_url": _metadata_documentation_url(metadata),
    }


def _selic_series(connection: sqlite3.Connection) -> dict[str, Any]:
    metadata = _series_metadata(connection, SELIC_SERIES_KEY)
    if metadata is None:
        return _unavailable(
            key="selic", label="Selic", data_kind="observed",
            unit="percent_per_year", required_inputs=[SELIC_SERIES_KEY],
            note="A série oficial da meta Selic ainda não foi carregada no banco local.",
        )
    rows = observations_latest(connection, SELIC_SERIES_KEY)
    if not rows:
        return _unavailable(
            key="selic", label="Selic", data_kind="observed",
            unit=str(metadata["unit_normalized"]), required_inputs=[SELIC_SERIES_KEY],
            note="A série está cadastrada, mas ainda não possui observações.",
        )
    observations = [
        {"date": row["reference_period"], "value": row["value"], "available_at": row["available_at"]}
        for row in rows
    ]
    latest = rows[-1]
    return {
        "key": "selic", "series_key": metadata["key"], "label": "Selic",
        "title": metadata["title"], "description": metadata["description"],
        "status": "available", "data_kind": metadata["data_kind"],
        "unit": metadata["unit_normalized"], "display_unit": metadata["unit_original"],
        "frequency": metadata["frequency"], "transformation": metadata["transformation"],
        "required_inputs": [], "note": None,
        "latest": {"date": latest["reference_period"], "value": latest["value"], "available_at": latest["available_at"]},
        "observations": observations, "source": _source_document(metadata),
    }


def _focus_expected_inflation(connection: sqlite3.Connection) -> dict[str, Any]:
    metadata = _series_metadata(connection, FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY)
    if metadata is None:
        return _unavailable(
            key="expected_inflation", label="Inflação esperada", data_kind="derived",
            unit="percent_per_year", required_inputs=["focus.monthly.ipca", "policy_horizon"],
            note="A coleta Focus e a composição no horizonte relevante ainda não foram carregadas.",
        )
    rows = observations_latest(connection, FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY)
    if not rows:
        return _unavailable(
            key="expected_inflation", label="Inflação esperada", data_kind="derived",
            unit="percent_per_year", required_inputs=["focus.monthly.ipca", "policy_horizon"],
            note="Ainda não há doze medianas mensais Focus suficientes para compor o horizonte relevante do Copom.",
        )
    latest = rows[-1]
    return {
        "key": "expected_inflation", "series_key": metadata["key"],
        "label": "Inflação esperada", "title": metadata["title"],
        "description": metadata["description"], "status": "available",
        "data_kind": metadata["data_kind"], "unit": metadata["unit_normalized"],
        "display_unit": metadata["unit_original"], "frequency": metadata["frequency"],
        "transformation": metadata["transformation"], "required_inputs": [],
        "note": "Proxy derivada pela composição das medianas mensais do Focus; não é a mediana de previsões acumuladas por instituição.",
        "latest": {
            "date": latest["reference_period"], "value": latest["value"],
            "available_at": latest["available_at"], "source_observation_at": latest["source_observation_at"],
        },
        "observations": [], "source": _source_document(metadata),
    }


def _policy_horizon_document(generated_at: datetime) -> dict[str, Any] | None:
    try:
        horizon = resolve_br_policy_horizon(generated_at.date())
    except LookupError:
        return None
    return {
        "country": horizon.country, "reference": horizon.key,
        "effective_from": horizon.effective_from.isoformat(),
        "window_start": horizon.window_start.isoformat(), "window_end": horizon.window_end.isoformat(),
        "source_label": horizon.source_label, "source_url": horizon.source_url,
        "method": "explicit_source_backed_registry",
    }


def _parameter_series(
    connection: sqlite3.Connection, *, generated_at: datetime,
    parameter_key: str, key: str, label: str, fallback_kind: str, fallback_unit: str,
) -> dict[str, Any]:
    row = parameter_latest(connection, parameter_key, knowledge_cutoff=_iso_z(generated_at))
    if row is None:
        return _unavailable(
            key=key, label=label, data_kind=fallback_kind, unit=fallback_unit,
            required_inputs=[parameter_key],
            note=f"O parâmetro {label.lower()} ainda não possui versão documental disponível para esta data.",
        )
    metadata = json.loads(row["metadata_json"] or "{}")
    return {
        "key": key, "parameter_key": parameter_key, "label": label,
        "title": label, "description": row["methodology"], "status": "available",
        "data_kind": row["data_kind"], "unit": row["unit"], "display_unit": None,
        "frequency": "on_publication", "transformation": "identity",
        "required_inputs": [], "note": metadata.get("note"),
        "latest": {
            "date": metadata.get("reference_period") or row["effective_from"],
            "value": row["value"], "available_at": row["available_at"],
            "effective_from": row["effective_from"], "published_at": row["published_at"],
        },
        "observations": [],
        "source": {
            "provider": row["source_provider"], "name": metadata.get("source_label") or row["source_name"],
            "documentation_url": metadata.get("source_url") or row["source_documentation_url"],
            "reference": row["source_reference"],
        },
    }


def _derived_metric(
    *, key: str, label: str, unit: str, value: float | None,
    date_value: str | None, available_at: str | None, required_inputs: list[str],
    transformation: str, note: str, source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if value is None or date_value is None or available_at is None:
        return _unavailable(
            key=key, label=label, data_kind="derived", unit=unit,
            required_inputs=required_inputs, note=note,
        )
    return {
        "key": key, "label": label, "status": "available", "data_kind": "derived",
        "unit": unit, "frequency": "on_publication", "transformation": transformation,
        "required_inputs": [], "note": note,
        "latest": {"date": date_value, "value": value, "available_at": available_at},
        "observations": [], "source": source,
    }


def _ex_ante_real_rate(selic: dict[str, Any], expectation: dict[str, Any]) -> dict[str, Any]:
    if selic["status"] != "available" or expectation["status"] != "available":
        return _unavailable(
            key="ex_ante_real_rate", label="Juro real ex ante", data_kind="derived",
            unit="percent_per_year", required_inputs=["selic", "expected_inflation"],
            note="Depende da Selic e da expectativa de inflação no horizonte definido.",
        )
    return _derived_metric(
        key="ex_ante_real_rate", label="Juro real ex ante", unit="percent_per_year",
        value=float(selic["latest"]["value"]) - float(expectation["latest"]["value"]),
        date_value=expectation["latest"]["date"],
        available_at=max(selic["latest"]["available_at"], expectation["latest"]["available_at"]),
        required_inputs=["selic", "expected_inflation"],
        transformation="selic_minus_policy_horizon_expected_inflation",
        note="Aproximação linear da V1: Selic nominal menos inflação esperada no horizonte relevante.",
    )


def _taylor_series(
    expected: dict[str, Any], target: dict[str, Any], neutral: dict[str, Any],
    output_gap: dict[str, Any], generated_at: datetime,
) -> dict[str, Any]:
    inputs = [expected, target, neutral, output_gap]
    if any(item["status"] != "available" for item in inputs):
        return _unavailable(
            key="taylor_prospective", label="Taylor prospectiva", data_kind="derived",
            unit="percent_per_year",
            required_inputs=[item["key"] for item in inputs if item["status"] != "available"],
            note="O cálculo exige expectativa, meta, taxa neutra e hiato com proveniência explícita.",
        )
    result = prospective_taylor(
        expected_inflation=float(expected["latest"]["value"]),
        inflation_target=float(target["latest"]["value"]),
        neutral_real_rate=float(neutral["latest"]["value"]),
        output_gap=float(output_gap["latest"]["value"]),
    )
    available_at = max(item["latest"]["available_at"] for item in inputs)
    return {
        "key": "taylor_prospective", "label": "Taylor prospectiva", "status": "available",
        "data_kind": "derived", "unit": "percent_per_year", "frequency": "on_publication",
        "transformation": "canonical_taylor_alpha_0.5_beta_0.5", "required_inputs": [],
        "note": (
            "Benchmark corrente calculado com insumos de referências distintas; não é uma série histórica reconstruída. "
            f"Inflação: {expected['latest']['date']}; meta: {target['latest']['date']}; "
            f"r*: {neutral['latest']['date']}; hiato: {output_gap['latest']['date']}."
        ),
        "latest": {
            "date": generated_at.date().isoformat(), "value": result.nominal_rate,
            "available_at": available_at,
            "decomposition": {
                "neutral_real_rate": result.decomposition.neutral_real_rate,
                "inflation": result.decomposition.inflation,
                "inflation_gap_response": result.decomposition.inflation_gap_response,
                "output_gap_response": result.decomposition.output_gap_response,
            },
        },
        # Historical values require historically aligned r* and output-gap vintages.
        "observations": [], "source": None,
    }


def _current_gap(
    *, key: str, label: str, left: dict[str, Any], right: dict[str, Any],
    unit: str, transformation: str, note: str,
) -> dict[str, Any]:
    if left["status"] != "available" or right["status"] != "available":
        return _unavailable(
            key=key, label=label, data_kind="derived", unit=unit,
            required_inputs=[item["key"] for item in (left, right) if item["status"] != "available"],
            note=note,
        )
    return _derived_metric(
        key=key, label=label, unit=unit,
        value=float(left["latest"]["value"]) - float(right["latest"]["value"]),
        date_value=left["latest"]["date"],
        available_at=max(left["latest"]["available_at"], right["latest"]["available_at"]),
        required_inputs=[left["key"], right["key"]], transformation=transformation, note=note,
    )


def _year_month(value: str) -> tuple[int, int]:
    parsed = date.fromisoformat(value)
    return parsed.year, parsed.month


def _consecutive_months(rows: list[sqlite3.Row]) -> bool:
    if len(rows) != 12:
        return False
    months = [year * 12 + month for year, month in (_year_month(str(row["reference_start"])) for row in rows)]
    return all(current == previous + 1 for previous, current in zip(months, months[1:]))


def _macro_observed_card(
    connection: sqlite3.Connection, *, series_key: str, key: str, label: str,
) -> dict[str, Any]:
    metadata = _series_metadata(connection, series_key)
    rows = observations_latest(connection, series_key)
    if metadata is None or not rows:
        return _unavailable(
            key=key, label=label, data_kind="observed",
            unit=MACRO_SERIES_BY_KEY[series_key].unit_normalized,
            required_inputs=[series_key], note="A série SGS ainda não foi carregada.",
        )
    latest = rows[-1]
    return {
        "key": key, "series_key": series_key, "label": label, "title": metadata["title"],
        "description": metadata["description"], "status": "available", "data_kind": metadata["data_kind"],
        "unit": metadata["unit_normalized"], "display_unit": metadata["unit_original"],
        "frequency": metadata["frequency"], "transformation": metadata["transformation"],
        "required_inputs": [], "note": None,
        "latest": {"date": latest["reference_period"], "value": latest["value"], "available_at": latest["available_at"]},
        "observations": [], "source": _source_document(metadata),
    }


def _macro_12m_card(
    connection: sqlite3.Connection, *, series_key: str, key: str, label: str,
) -> dict[str, Any]:
    metadata = _series_metadata(connection, series_key)
    rows = observations_latest(connection, series_key)
    if metadata is None or len(rows) < 12:
        return _unavailable(
            key=key, label=label, data_kind="derived", unit="percent",
            required_inputs=[series_key], note="São necessárias 12 observações mensais consecutivas.",
        )
    last12 = rows[-12:]
    if not _consecutive_months(last12):
        return _unavailable(
            key=key, label=label, data_kind="derived", unit="percent",
            required_inputs=[series_key], note="As 12 observações mensais mais recentes não formam uma janela consecutiva.",
        )
    factor = math.prod(1.0 + float(row["value"]) / 100.0 for row in last12)
    latest = last12[-1]
    return {
        "key": key, "series_key": series_key, "label": label, "title": metadata["title"],
        "description": metadata["description"], "status": "available", "data_kind": "derived",
        "unit": "percent", "display_unit": "% em 12 meses", "frequency": "monthly",
        "transformation": "compound_last_12_monthly_percent_changes", "required_inputs": [],
        "note": "Acumulado em 12 meses composto a partir das variações mensais SGS.",
        "latest": {"date": latest["reference_period"], "value": (factor - 1.0) * 100.0, "available_at": max(row["available_at"] for row in last12)},
        "observations": [], "source": _source_document(metadata),
    }


def _ibc_mom_card(connection: sqlite3.Connection) -> dict[str, Any]:
    series_key = "br.ibc_br.sa"
    metadata = _series_metadata(connection, series_key)
    rows = observations_latest(connection, series_key)
    if metadata is None or len(rows) < 2:
        return _unavailable(
            key="ibc_br_mom", label="IBC-Br (m/m)", data_kind="derived", unit="percent",
            required_inputs=[series_key], note="São necessárias duas observações do IBC-Br dessazonalizado.",
        )
    previous, latest = rows[-2], rows[-1]
    denominator = float(previous["value"])
    if denominator == 0:
        return _unavailable(
            key="ibc_br_mom", label="IBC-Br (m/m)", data_kind="derived", unit="percent",
            required_inputs=[series_key], note="Não é possível calcular a variação com base anterior igual a zero.",
        )
    value = (float(latest["value"]) / denominator - 1.0) * 100.0
    return {
        "key": "ibc_br_mom", "series_key": series_key, "label": "IBC-Br (m/m)",
        "title": metadata["title"], "description": metadata["description"], "status": "available",
        "data_kind": "derived", "unit": "percent", "display_unit": "%",
        "frequency": "monthly", "transformation": "latest_index_over_previous_minus_one",
        "required_inputs": [], "note": "Variação mensal calculada sobre a série com ajuste sazonal.",
        "latest": {"date": latest["reference_period"], "value": value, "available_at": max(previous["available_at"], latest["available_at"])},
        "observations": [], "source": _source_document(metadata),
    }


def build_overview_document(connection: sqlite3.Connection, *, generated_at: datetime) -> dict[str, Any]:
    """Build a current-state view while preserving provenance and missingness."""

    selic = _selic_series(connection)
    expected = _focus_expected_inflation(connection)
    target = _parameter_series(
        connection, generated_at=generated_at, parameter_key="br.inflation.target",
        key="inflation_target", label="Meta de inflação", fallback_kind="observed", fallback_unit="percent_per_year",
    )
    neutral = _parameter_series(
        connection, generated_at=generated_at, parameter_key="br.neutral_real_rate.rpm",
        key="neutral_real_rate", label="Taxa real neutra", fallback_kind="estimated", fallback_unit="percent_per_year",
    )
    output_gap = _parameter_series(
        connection, generated_at=generated_at, parameter_key="br.output_gap.rpm",
        key="output_gap", label="Hiato do produto", fallback_kind="estimated", fallback_unit="percentage_points",
    )
    ex_ante = _ex_ante_real_rate(selic, expected)
    taylor = _taylor_series(expected, target, neutral, output_gap, generated_at)
    selic_taylor = _current_gap(
        key="selic_minus_taylor", label="Selic − Taylor", left=selic, right=taylor,
        unit="percentage_points", transformation="selic_minus_taylor_prospective",
        note="Diferença descritiva entre a Selic corrente e o benchmark de Taylor; não é uma recomendação de política.",
    )
    real_gap = _current_gap(
        key="real_monetary_gap", label="Gap monetário real", left=ex_ante, right=neutral,
        unit="percentage_points", transformation="ex_ante_real_rate_minus_neutral_real_rate",
        note="Diferença entre o juro real ex ante aproximado e a estimativa documental de taxa real neutra.",
    )

    series = {
        "selic": selic,
        "taylor_prospective": taylor,
        "selic_minus_taylor": selic_taylor,
        "ex_ante_real_rate": ex_ante,
        "real_monetary_gap": real_gap,
        "expected_inflation": expected,
        "inflation_target": target,
        "neutral_real_rate": neutral,
        "output_gap": output_gap,
        "ipca_12m": _macro_12m_card(connection, series_key="br.ipca.monthly", key="ipca_12m", label="IPCA (12m)"),
        "ipca_core_12m": _macro_12m_card(connection, series_key="br.ipca.core.trimmed_unsmoothed.monthly", key="ipca_core_12m", label="Núcleo IPCA (12m)"),
        "ipca_services_12m": _macro_12m_card(connection, series_key="br.ipca.services.monthly", key="ipca_services_12m", label="Serviços IPCA (12m)"),
        "ibc_br_mom": _ibc_mom_card(connection),
        "unemployment_rate": _macro_observed_card(connection, series_key="br.unemployment.pnadc", key="unemployment_rate", label="Desocupação"),
        "real_earnings": _macro_observed_card(connection, series_key="br.real_earnings.pnadc", key="real_earnings", label="Rendimento real"),
    }

    available = sum(item["status"] == "available" for item in series.values())
    return {
        "schema_version": OVERVIEW_SCHEMA_VERSION, "view": "overview", "country": "BR",
        "generated_at": _iso_z(generated_at), "knowledge_mode": "latest_revision",
        "policy_horizon": _policy_horizon_document(generated_at),
        "availability": {
            "status": "partial" if available < len(series) else "complete",
            "available_series": available, "total_series": len(series),
        },
        "series": series,
        "notes": [
            "Séries indisponíveis permanecem explícitas; o publicador não cria dados substitutos.",
            "Meta, taxa neutra e hiato são parâmetros documentais versionados; taxa neutra e hiato são estimativas, não observações.",
            "A Taylor publicada nesta sprint é apenas corrente: não há retropropagação de r* ou hiato para fabricar histórico.",
        ],
    }


def publish_overview_json(
    connection: sqlite3.Connection, *, output_path: str | Path, generated_at: datetime,
) -> Path:
    return write_json_atomic(build_overview_document(connection, generated_at=generated_at), output_path)
