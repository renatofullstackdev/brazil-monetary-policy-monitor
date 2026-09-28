"""Publish the static overview contract consumed by the browser UI."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

from ..horizons import resolve_br_policy_horizon
from ..ingestion.focus import FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY
from ..ingestion.policy import OUTPUT_GAP_SERIES_KEY
from ..ingestion.sgs import SELIC_SERIES_KEY
from ..macro_series import MACRO_SERIES_BY_KEY
from ..monetary_history import build_monetary_posture_history
from ..vintages import KnowledgeContext, build_knowledge_context, observation_rows, parameter_row
from ..db.observations import observation_vintages
from .atomic import write_json_atomic
from .indicator_contract import structure_indicator_contract



def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _unavailable(
    *, key: str, label: str, data_kind: str, unit: str,
    missing_inputs: list[str], note: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": "unavailable",
        "data_kind": data_kind,
        "unit": unit,
        "inputs": missing_inputs if data_kind == "derived" else [],
        "missing_inputs": missing_inputs,
        "caveats": [note] if note else [],
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


def _selic_series(connection: sqlite3.Connection, context: KnowledgeContext) -> dict[str, Any]:
    metadata = _series_metadata(connection, SELIC_SERIES_KEY)
    if metadata is None:
        return _unavailable(
            key="selic", label="Selic", data_kind="observed",
            unit="percent_per_year", missing_inputs=[SELIC_SERIES_KEY],
            note="A série oficial da meta Selic ainda não foi carregada no banco local.",
        )
    rows = observation_rows(connection, SELIC_SERIES_KEY, context)
    if not rows:
        return _unavailable(
            key="selic", label="Selic", data_kind="observed",
            unit=str(metadata["unit_normalized"]), missing_inputs=[SELIC_SERIES_KEY],
            note="A série está cadastrada, mas ainda não possui observações.",
        )
    observations = [
        {"date": row["reference_period"], "value": row["value"], "available_at": row["available_at"]}
        for row in rows
    ]
    latest = rows[-1]
    return {
        "key": "selic", "series_key": metadata["key"], "label": "Selic",
        "title": metadata["title"], "definition": metadata["description"],
        "status": "available", "data_kind": metadata["data_kind"],
        "unit": metadata["unit_normalized"], "display_unit": metadata["unit_original"],
        "frequency": metadata["frequency"], "transformation": metadata["transformation"],
        "inputs": [], "missing_inputs": [], "caveats": [],
        "latest": {"date": latest["reference_period"], "value": latest["value"], "available_at": latest["available_at"]},
        "observations": observations, "source": _source_document(metadata),
    }


def _focus_expected_inflation(connection: sqlite3.Connection, context: KnowledgeContext) -> dict[str, Any]:
    metadata = _series_metadata(connection, FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY)
    if metadata is None:
        return _unavailable(
            key="expected_inflation", label="Inflação esperada", data_kind="derived",
            unit="percent_per_year", missing_inputs=["focus.monthly.ipca", "policy_horizon"],
            note="A coleta Focus e a composição no horizonte relevante ainda não foram carregadas.",
        )
    cutoff = context.cutoff if context.mode == "as_known" else None
    rows = observation_vintages(
        connection, FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY, knowledge_cutoff=cutoff
    )
    if not rows:
        return _unavailable(
            key="expected_inflation", label="Inflação esperada", data_kind="derived",
            unit="percent_per_year", missing_inputs=["focus.monthly.ipca", "policy_horizon"],
            note="Ainda não há doze medianas mensais Focus suficientes para compor um horizonte relevante documentado do Copom.",
        )
    latest = max(rows, key=lambda row: (row["available_at"], row["source_observation_at"] or ""))
    observations = [
        {
            "date": row["source_observation_at"] or row["available_at"][:10],
            "as_of_date": row["source_observation_at"],
            "reference_period": row["reference_period"],
            "value": row["value"],
            "available_at": row["available_at"],
        }
        for row in rows
    ]
    return {
        "key": "expected_inflation", "series_key": metadata["key"],
        "label": "Inflação esperada", "title": metadata["title"],
        "definition": metadata["description"], "status": "available",
        "data_kind": metadata["data_kind"], "unit": metadata["unit_normalized"],
        "display_unit": metadata["unit_original"], "frequency": metadata["frequency"],
        "transformation": metadata["transformation"],
        "inputs": ["focus.monthly.ipca", "policy_horizon"], "missing_inputs": [],
        "caveats": [
            "Proxy derivada pela composição das medianas mensais do Focus; não é a mediana de previsões acumuladas por instituição.",
            "A API Focus não informa o timestamp histórico de publicação; o backfill usa uma fronteira conservadora de até sete dias após a data da estatística, ou a primeira observação local quando anterior.",
        ],
        "latest": {
            "date": latest["reference_period"],
            "reference_period": latest["reference_period"],
            "as_of_date": latest["source_observation_at"],
            "value": latest["value"],
            "available_at": latest["available_at"],
        },
        "observations": observations, "source": _source_document(metadata),
    }


def _policy_horizon_document(generated_at: datetime) -> dict[str, Any] | None:
    try:
        horizon = resolve_br_policy_horizon(generated_at.date())
    except LookupError:
        return None
    return {
        "country": horizon.country, "reference": horizon.key,
        "meeting_end": horizon.meeting_end.isoformat(),
        "available_from": horizon.available_from.isoformat(),
        "window_start": horizon.window_start.isoformat(), "window_end": horizon.window_end.isoformat(),
        "source_label": horizon.source_label, "source_url": horizon.source_url,
        "method": "explicit_source_backed_registry",
    }


def _parameter_series(
    connection: sqlite3.Connection, *, context: KnowledgeContext,
    parameter_key: str, key: str, label: str, fallback_kind: str, fallback_unit: str,
) -> dict[str, Any]:
    row = parameter_row(connection, parameter_key, context)
    if row is None:
        return _unavailable(
            key=key, label=label, data_kind=fallback_kind, unit=fallback_unit,
            missing_inputs=[parameter_key],
            note=f"O parâmetro {label.lower()} ainda não possui versão documental disponível para esta data.",
        )
    metadata = json.loads(row["metadata_json"] or "{}")
    cutoff = context.cutoff if context.mode == "as_known" else _iso_z(context.generated_at)
    history_rows = connection.execute(
        """
        SELECT * FROM parameters
        WHERE key = ? AND available_at <= ?
        ORDER BY effective_from, available_at, id
        """,
        (parameter_key, cutoff),
    ).fetchall()
    observations = []
    for history_row in history_rows:
        history_metadata = json.loads(history_row["metadata_json"] or "{}")
        observations.append({
            "date": history_row["effective_from"],
            "reference_period": history_metadata.get("reference_period"),
            "value": history_row["value"],
            "available_at": history_row["available_at"],
            "effective_from": history_row["effective_from"],
            "effective_to": history_row["effective_to"],
        })
    return {
        "key": key, "parameter_key": parameter_key, "label": label,
        "title": label, "definition": row["methodology"], "status": "available",
        "data_kind": row["data_kind"], "unit": row["unit"], "display_unit": None,
        "frequency": "on_publication", "transformation": "identidade",
        "inputs": [], "missing_inputs": [], "caveats": [metadata["note"]] if metadata.get("note") else [],
        "latest": {
            "date": row["effective_from"],
            "reference_period": metadata.get("reference_period"),
            "value": row["value"], "available_at": row["available_at"],
            "effective_from": row["effective_from"], "published_at": row["published_at"],
        },
        "observations": observations,
        "source": {
            "provider": row["source_provider"], "name": metadata.get("source_label") or row["source_name"],
            "documentation_url": metadata.get("source_url") or row["source_documentation_url"],
            "reference": row["source_reference"],
        },
    }


def _output_gap_series(connection: sqlite3.Connection, context: KnowledgeContext) -> dict[str, Any]:
    metadata = _series_metadata(connection, OUTPUT_GAP_SERIES_KEY)
    if metadata is None:
        return _unavailable(
            key="output_gap", label="Hiato do produto", data_kind="estimated",
            unit="percentage_points", missing_inputs=[OUTPUT_GAP_SERIES_KEY],
            note="Os vintages documentais do hiato do produto ainda não foram carregados.",
        )
    rows = observation_rows(connection, OUTPUT_GAP_SERIES_KEY, context)
    if not rows:
        return _unavailable(
            key="output_gap", label="Hiato do produto", data_kind="estimated",
            unit="percentage_points", missing_inputs=[OUTPUT_GAP_SERIES_KEY],
            note="Nenhum vintage do hiato estava disponível na data de conhecimento selecionada.",
        )
    latest = max(rows, key=lambda row: (row["available_at"], row["reference_end"], row["id"]))

    def point_document(row: sqlite3.Row) -> dict[str, Any]:
        flags = json.loads(row["quality_flags_json"] or "[]")
        provenance = next((item for item in flags if isinstance(item, dict) and item.get("report_key")), {})
        return {
            "date": row["reference_period"],
            "value": row["value"],
            "available_at": row["available_at"],
            "as_of_date": row["source_observation_at"],
            "source_revision": row["source_revision"],
            "source_label": provenance.get("source_label"),
            "source_url": provenance.get("source_url"),
            "source_reference": provenance.get("source_reference"),
        }

    observations = [point_document(row) for row in rows]
    latest_point = point_document(latest)
    return {
        "key": "output_gap", "series_key": OUTPUT_GAP_SERIES_KEY,
        "label": "Hiato do produto", "title": metadata["title"],
        "definition": metadata["description"], "status": "available",
        "data_kind": metadata["data_kind"], "unit": metadata["unit_normalized"],
        "display_unit": metadata["unit_original"], "frequency": metadata["frequency"],
        "transformation": metadata["transformation"], "inputs": [], "missing_inputs": [],
        "caveats": ["O hiato é não observável e revisável; cada corte histórico usa apenas o vintage já publicado."],
        "latest": latest_point,
        "observations": observations, "source": _source_document(metadata),
    }


def _derived_history_series(
    *,
    key: str,
    label: str,
    unit: str,
    observations: list[dict[str, Any]],
    inputs: list[str],
    transformation: str,
    caveats: list[str],
) -> dict[str, Any]:
    if not observations:
        return _unavailable(
            key=key,
            label=label,
            data_kind="derived",
            unit=unit,
            missing_inputs=inputs,
            note=(
                "Ainda não há um ponto histórico em que todos os insumos necessários "
                "estejam defensavelmente disponíveis no mesmo corte de conhecimento."
            ),
        )
    return {
        "key": key,
        "label": label,
        "status": "available",
        "data_kind": "derived",
        "unit": unit,
        "frequency": "weekly",
        "transformation": transformation,
        "inputs": inputs,
        "missing_inputs": [],
        "caveats": caveats,
        "latest": observations[-1],
        "observations": observations,
        "source": None,
    }


def _posture_series(history: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    weekly_note = (
        "Reconstrução semanal orientada pelos vintages Focus: em cada semana é usado o último "
        "ponto com disponibilidade defensável e os demais insumos são unidos por corte as-of, "
        "sem informação futura."
    )
    return {
        "ex_ante_real_rate": _derived_history_series(
            key="ex_ante_real_rate",
            label="Juro real ex ante",
            unit="percent_per_year",
            observations=history["ex_ante_real_rate"],
            inputs=["selic", "expected_inflation"],
            transformation="Selic menos a inflação esperada no horizonte da política",
            caveats=[
                "Aproximação linear: Selic nominal menos inflação esperada no horizonte relevante.",
                weekly_note,
            ],
        ),
        "real_monetary_gap": _derived_history_series(
            key="real_monetary_gap",
            label="Gap monetário real",
            unit="percentage_points",
            observations=history["real_monetary_gap"],
            inputs=["ex_ante_real_rate", "neutral_real_rate"],
            transformation="taxa real ex ante menos taxa real neutra",
            caveats=[
                "Diferença entre o juro real ex ante aproximado e a hipótese documental de taxa real neutra.",
                weekly_note,
            ],
        ),
        "taylor_prospective": _derived_history_series(
            key="taylor_prospective",
            label="Taylor prospectiva",
            unit="percent_per_year",
            observations=history["taylor_prospective"],
            inputs=["expected_inflation", "inflation_target", "neutral_real_rate", "output_gap"],
            transformation="Taylor canônica (alpha=0.5, beta=0.5)",
            caveats=[
                "Benchmark mecânico; não é recomendação de política monetária.",
                "A meta é selecionada pelo período prospectivo da expectativa e precisa já ser conhecida no corte do ponto.",
                weekly_note,
            ],
        ),
        "selic_minus_taylor": _derived_history_series(
            key="selic_minus_taylor",
            label="Selic − Taylor",
            unit="percentage_points",
            observations=history["selic_minus_taylor"],
            inputs=["selic", "taylor_prospective"],
            transformation="Selic menos Taylor prospectiva",
            caveats=[
                "Diferença descritiva entre a Selic e o benchmark de Taylor; não é uma recomendação de política.",
                weekly_note,
            ],
        ),
    }


def _year_month(value: str) -> tuple[int, int]:
    parsed = date.fromisoformat(value)
    return parsed.year, parsed.month


def _consecutive_months(rows: list[sqlite3.Row]) -> bool:
    if len(rows) != 12:
        return False
    months = [year * 12 + month for year, month in (_year_month(str(row["reference_start"])) for row in rows)]
    return all(current == previous + 1 for previous, current in zip(months, months[1:]))


def _macro_observed_card(
    connection: sqlite3.Connection, *, context: KnowledgeContext, series_key: str, key: str, label: str,
) -> dict[str, Any]:
    metadata = _series_metadata(connection, series_key)
    rows = observation_rows(connection, series_key, context)
    if metadata is None or not rows:
        return _unavailable(
            key=key, label=label, data_kind="observed",
            unit=MACRO_SERIES_BY_KEY[series_key].unit_normalized,
            missing_inputs=[series_key], note="A série SGS ainda não foi carregada.",
        )
    latest = rows[-1]
    return {
        "key": key, "series_key": series_key, "label": label, "title": metadata["title"],
        "definition": metadata["description"], "status": "available", "data_kind": metadata["data_kind"],
        "unit": metadata["unit_normalized"], "display_unit": metadata["unit_original"],
        "frequency": metadata["frequency"], "transformation": metadata["transformation"],
        "inputs": [], "missing_inputs": [], "caveats": [],
        "latest": {"date": latest["reference_period"], "value": latest["value"], "available_at": latest["available_at"]},
        "observations": [
            {"date": row["reference_period"], "value": row["value"], "available_at": row["available_at"]}
            for row in rows
        ],
        "source": _source_document(metadata),
    }


def _macro_12m_card(
    connection: sqlite3.Connection, *, context: KnowledgeContext, series_key: str, key: str, label: str,
) -> dict[str, Any]:
    metadata = _series_metadata(connection, series_key)
    rows = observation_rows(connection, series_key, context)
    if metadata is None or len(rows) < 12:
        return _unavailable(
            key=key, label=label, data_kind="derived", unit="percent",
            missing_inputs=[series_key], note="São necessárias 12 observações mensais consecutivas.",
        )
    history: list[dict[str, Any]] = []
    for end in range(11, len(rows)):
        window = rows[end - 11:end + 1]
        if not _consecutive_months(window):
            continue
        factor = math.prod(1.0 + float(row["value"]) / 100.0 for row in window)
        latest_window = window[-1]
        history.append({
            "date": latest_window["reference_period"],
            "value": (factor - 1.0) * 100.0,
            "available_at": max(row["available_at"] for row in window),
        })
    if not history:
        return _unavailable(
            key=key, label=label, data_kind="derived", unit="percent",
            missing_inputs=[series_key], note="Não há janela de 12 observações mensais consecutivas.",
        )
    latest = history[-1]
    return {
        "key": key, "series_key": series_key, "label": label, "title": metadata["title"],
        "definition": metadata["description"], "status": "available", "data_kind": "derived",
        "unit": "percent", "display_unit": "% em 12 meses", "frequency": "monthly",
        "transformation": "variações percentuais mensais acumuladas dos últimos 12 meses",
        "inputs": [series_key], "missing_inputs": [],
        "caveats": ["Acumulado em 12 meses composto a partir das variações mensais SGS."],
        "latest": latest,
        "observations": history, "source": _source_document(metadata),
    }


def _ibc_mom_card(connection: sqlite3.Connection, context: KnowledgeContext) -> dict[str, Any]:
    series_key = "br.ibc_br.sa"
    metadata = _series_metadata(connection, series_key)
    rows = observation_rows(connection, series_key, context)
    if metadata is None or len(rows) < 2:
        return _unavailable(
            key="ibc_br_mom", label="IBC-Br (m/m)", data_kind="derived", unit="percent",
            missing_inputs=[series_key], note="São necessárias duas observações do IBC-Br dessazonalizado.",
        )
    history: list[dict[str, Any]] = []
    for previous, latest in zip(rows, rows[1:]):
        denominator = float(previous["value"])
        if denominator == 0:
            continue
        history.append({
            "date": latest["reference_period"],
            "value": (float(latest["value"]) / denominator - 1.0) * 100.0,
            "available_at": max(previous["available_at"], latest["available_at"]),
        })
    if not history:
        return _unavailable(
            key="ibc_br_mom", label="IBC-Br (m/m)", data_kind="derived", unit="percent",
            missing_inputs=[series_key], note="Não há pares consecutivos válidos para calcular a variação mensal.",
        )
    return {
        "key": "ibc_br_mom", "series_key": series_key, "label": "IBC-Br (m/m)",
        "title": metadata["title"], "definition": metadata["description"], "status": "available",
        "data_kind": "derived", "unit": "percent", "display_unit": "%",
        "frequency": "monthly", "transformation": "índice mais recente sobre o anterior menos um",
        "inputs": [series_key], "missing_inputs": [],
        "caveats": ["Variação mensal calculada sobre a série com ajuste sazonal."],
        "latest": history[-1],
        "observations": history, "source": _source_document(metadata),
    }


def build_overview_document(
    connection: sqlite3.Connection,
    *,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> dict[str, Any]:
    """Build a revision-aware overview without backdating unknown vintages."""

    context = build_knowledge_context(
        generated_at=generated_at,
        knowledge_mode=knowledge_mode,
        knowledge_cutoff=knowledge_cutoff,
    )
    selic = _selic_series(connection, context)
    expected = _focus_expected_inflation(connection, context)
    target = _parameter_series(
        connection, context=context, parameter_key="br.inflation.target",
        key="inflation_target", label="Meta de inflação", fallback_kind="observed", fallback_unit="percent_per_year",
    )
    neutral = _parameter_series(
        connection, context=context, parameter_key="br.neutral_real_rate.rpm",
        key="neutral_real_rate", label="Taxa real neutra", fallback_kind="estimated", fallback_unit="percent_per_year",
    )
    output_gap = _output_gap_series(connection, context)
    posture = _posture_series(
        build_monetary_posture_history(connection, context=context)
    )
    ex_ante = posture["ex_ante_real_rate"]
    real_gap = posture["real_monetary_gap"]
    taylor = posture["taylor_prospective"]
    selic_taylor = posture["selic_minus_taylor"]

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
        "ipca_12m": _macro_12m_card(connection, context=context, series_key="br.ipca.monthly", key="ipca_12m", label="IPCA (12m)"),
        "ipca_core_12m": _macro_12m_card(connection, context=context, series_key="br.ipca.core.trimmed_unsmoothed.monthly", key="ipca_core_12m", label="Núcleo IPCA (12m)"),
        "ipca_services_12m": _macro_12m_card(connection, context=context, series_key="br.ipca.services.monthly", key="ipca_services_12m", label="Serviços IPCA (12m)"),
        "ibc_br_mom": _ibc_mom_card(connection, context),
        "unemployment_rate": _macro_observed_card(connection, context=context, series_key="br.unemployment.pnadc", key="unemployment_rate", label="Desocupação"),
        "real_earnings": _macro_observed_card(connection, context=context, series_key="br.real_earnings.pnadc", key="real_earnings", label="Rendimento real"),
    }

    available = sum(item["status"] == "available" for item in series.values())
    return structure_indicator_contract({
        "view": "overview", "country": "BR",
        "generated_at": _iso_z(generated_at), **context.contract_fields(),
        "policy_horizon": _policy_horizon_document(context.effective_datetime),
        "availability": {
            "status": "partial" if available < len(series) else "complete",
            "available_series": available, "total_series": len(series),
        },
        "series": series,
        "notes": [
            "Séries indisponíveis permanecem explícitas; o publicador não cria dados substitutos.",
            "Meta e taxa neutra são regimes documentais versionados; o hiato é uma série de vintages RI/RPM e permanece uma estimativa não observável.",
            "As métricas prospectivas são reconstruídas semanalmente com joins as-of e linhagem por ponto; nenhum ponto usa informação posterior ao seu corte de conhecimento.",
        ],
    })


def publish_overview_json(
    connection: sqlite3.Connection,
    *,
    output_path: str | Path,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> Path:
    return write_json_atomic(
        build_overview_document(
            connection,
            generated_at=generated_at,
            knowledge_mode=knowledge_mode,
            knowledge_cutoff=knowledge_cutoff,
        ),
        output_path,
    )
