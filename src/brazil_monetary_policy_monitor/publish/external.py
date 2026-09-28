"""Publish the static external-sector and exchange-rate contract."""

from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from ..external_series import EXTERNAL_SERIES_BY_KEY
from ..vintages import KnowledgeContext, build_knowledge_context, observation_rows
from .atomic import write_json_atomic
from .indicator_contract import structure_indicator_contract


EXTERNAL_SCHEMA_VERSION = 4


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


def _history(connection: sqlite3.Connection, series_key: str, context: KnowledgeContext) -> list[dict[str, Any]]:
    return [
        {
            "date": str(row["reference_period"]),
            "value": float(row["value"]),
            "available_at": str(row["available_at"]),
        }
        for row in observation_rows(connection, series_key, context)
    ]


def _series_document(
    connection: sqlite3.Connection,
    *,
    context: KnowledgeContext,
    series_key: str,
    label: str,
    note: str,
    interpretation: str,
) -> dict[str, Any]:
    spec = EXTERNAL_SERIES_BY_KEY[series_key]
    metadata = _series_metadata(connection, series_key)
    values = _history(connection, series_key, context)
    return {
        "key": series_key,
        "label": label,
        "title": metadata["title"] if metadata is not None else spec.title,
        "definition": metadata["description"] if metadata is not None else spec.description,
        "interpretation": interpretation,
        "status": "available" if values else "unavailable",
        "data_kind": "observed",
        "unit": spec.unit_normalized,
        "frequency": spec.frequency,
        "transformation": "identity",
        "inputs": [],
        "missing_inputs": [] if values else [series_key],
        "caveats": [note] if note else [],
        "latest": values[-1] if values else None,
        "observations": values,
        "source": _source_document(metadata),
    }


def _change_history(
    base: dict[str, Any],
    *,
    days: int,
    key: str,
    label: str,
    note: str,
) -> dict[str, Any]:
    values = base.get("observations") or []
    parsed = [(date.fromisoformat(item["date"]), item) for item in values]
    dates = [item[0] for item in parsed]
    output: list[dict[str, Any]] = []
    for current_date, current in parsed:
        target = current_date - timedelta(days=days)
        index = bisect_right(dates, target) - 1
        if index < 0:
            continue
        previous = parsed[index][1]
        previous_value = float(previous["value"])
        if previous_value == 0:
            continue
        change = (float(current["value"]) / previous_value - 1.0) * 100.0
        output.append(
            {
                "date": current["date"],
                "value": change,
                "available_at": max(str(current["available_at"]), str(previous["available_at"])),
            }
        )
    return {
        "key": key,
        "label": label,
        "title": label,
        "definition": f"Variação percentual derivada da cotação USD/BRL em uma janela de {days} dias corridos.",
        "interpretation": "Valor positivo indica que são necessários mais reais por dólar do que na observação de comparação; valor negativo indica o movimento oposto.",
        "status": "available" if output else "unavailable",
        "data_kind": "derived",
        "unit": "percent_change",
        "frequency": "daily",
        "transformation": f"percent_change_vs_last_observation_on_or_before_{days}_calendar_days",
        "inputs": [base["key"]],
        "missing_inputs": [] if output else [base["key"]],
        "caveats": [note] if note else [],
        "latest": output[-1] if output else None,
        "observations": output,
        "source": base.get("source"),
    }


def _coverage_history(current_account: dict[str, Any], idp: dict[str, Any]) -> list[dict[str, Any]]:
    ca = {item["date"]: item for item in current_account.get("observations") or []}
    result: list[dict[str, Any]] = []
    for item in idp.get("observations") or []:
        current = ca.get(item["date"])
        if current is None:
            continue
        current_value = float(current["value"])
        if current_value >= 0:
            continue
        value = float(item["value"]) / abs(current_value) * 100.0
        result.append(
            {
                "date": item["date"],
                "value": value,
                "available_at": max(str(item["available_at"]), str(current["available_at"])),
            }
        )
    return result


def _coverage_document(current_account: dict[str, Any], idp: dict[str, Any]) -> dict[str, Any]:
    values = _coverage_history(current_account, idp)
    return {
        "key": "br.external.idp_current_account_deficit_coverage",
        "label": "IDP / déficit em transações correntes",
        "title": "Cobertura descritiva do déficit em transações correntes pelo IDP",
        "definition": (
            "Razão entre o IDP acumulado em 12 meses e o valor absoluto do déficit em transações "
            "correntes no mesmo período, quando a conta corrente é deficitária."
        ),
        "interpretation": (
            "É uma razão descritiva de escala, não uma identidade de financiamento nem prova de que "
            "o IDP financiou diretamente um déficit específico."
        ),
        "status": "available" if values else "unavailable",
        "data_kind": "derived",
        "unit": "percent",
        "frequency": "monthly",
        "transformation": "idp_12m_gdp / abs(current_account_12m_gdp) * 100 when current_account < 0",
        "inputs": [current_account["key"], idp["key"]],
        "missing_inputs": [] if values else [current_account["key"], idp["key"]],
        "caveats": ["Calculado apenas em meses com déficit em transações correntes; ambos os insumos usam o mesmo denominador de PIB."],
        "latest": values[-1] if values else None,
        "observations": values,
        "source": {
            "provider": "BCB",
            "name": "Derivado das séries SGS 23079 e 23080",
            "documentation_url": current_account.get("source", {}).get("documentation_url") if current_account.get("source") else None,
        },
    }


def build_external_document(
    connection: sqlite3.Connection,
    *,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> dict[str, Any]:
    context = build_knowledge_context(
        generated_at=generated_at, knowledge_mode=knowledge_mode, knowledge_cutoff=knowledge_cutoff
    )
    usd = _series_document(
        connection,
        context=context,
        series_key="br.fx.usd_brl.sell",
        label="USD/BRL — venda",
        note="Cotação nominal observada. Movimento cambial não é atribuído a uma única causa.",
        interpretation="Mostra quantos reais correspondem a um dólar na cotação de venda publicada pelo BCB.",
    )
    usd_30d = _change_history(
        usd,
        days=30,
        key="br.fx.usd_brl.change_30d",
        label="USD/BRL — variação 30 dias",
        note="Compara a observação atual à última observação disponível em ou antes de 30 dias corridos atrás.",
    )
    usd_365d = _change_history(
        usd,
        days=365,
        key="br.fx.usd_brl.change_365d",
        label="USD/BRL — variação 12 meses",
        note="Compara a observação atual à última observação disponível em ou antes de 365 dias corridos atrás.",
    )
    reer = _series_document(
        connection,
        context=context,
        series_key="br.fx.reer_ipca",
        label="Câmbio real efetivo (IPCA)",
        note="Índice com base em junho de 1994; não representa um nível de câmbio de equilíbrio ou 'câmbio justo'.",
        interpretation="Combina câmbio nominal, inflação doméstica e externa e pesos de parceiros comerciais. Alta do índice corresponde, em geral, a depreciação real efetiva na metodologia da série.",
    )
    current_account = _series_document(
        connection,
        context=context,
        series_key="br.external.current_account_12m_gdp",
        label="Transações correntes — 12m / PIB",
        note="Valor negativo representa déficit em transações correntes; positivo representa superávit.",
        interpretation="Dimensiona o saldo externo corrente acumulado em doze meses em relação ao tamanho da economia.",
    )
    idp = _series_document(
        connection,
        context=context,
        series_key="br.external.idp_12m_gdp",
        label="IDP — 12m / PIB",
        note="Investimento direto envolve relação de controle ou influência relevante; não deve ser confundido com investimento em carteira.",
        interpretation="Dimensiona o ingresso líquido de investimento direto no país acumulado em doze meses em relação ao PIB.",
    )
    coverage = _coverage_document(current_account, idp)
    portfolio = _series_document(
        connection,
        context=context,
        series_key="br.external.portfolio_liabilities_net",
        label="Carteira — passivos líquidos",
        note="O sinal segue a convenção estatística do balanço de pagamentos/BPM6. Não representa todo o fluxo financeiro de estrangeiros para o Brasil.",
        interpretation="Mostra o fluxo líquido mensal de passivos de investimento em carteira, separado do investimento direto.",
    )
    reserves = _series_document(
        connection,
        context=context,
        series_key="br.external.reserves_liquidity",
        label="Reservas internacionais — liquidez",
        note="O conceito liquidez inclui, além dos ativos de reserva, determinadas operações de linhas com recompra e empréstimos em moeda estrangeira do BCB.",
        interpretation="Estoque de ativos externos prontamente disponíveis ao BCB para finalidades de balanço de pagamentos, intervenção e confiança.",
    )

    groups = {
        "fx_nominal": {
            "label": "Câmbio nominal",
            "metrics": [usd, usd_30d, usd_365d],
            "chart_series": [usd],
        },
        "fx_real": {
            "label": "Câmbio real efetivo",
            "metrics": [reer],
            "chart_series": [reer],
        },
        "external_balance": {
            "label": "Conta externa",
            "metrics": [current_account, idp, coverage],
            "chart_series": [current_account, idp],
        },
        "portfolio": {
            "label": "Investimento em carteira",
            "metrics": [portfolio],
            "chart_series": [portfolio],
        },
        "reserves": {
            "label": "Reservas internacionais",
            "metrics": [reserves],
            "chart_series": [reserves],
        },
    }
    all_metrics = [metric for group in groups.values() for metric in group["metrics"]]
    available = sum(metric["status"] == "available" for metric in all_metrics)
    latest_dates = [
        metric["latest"]["date"]
        for metric in all_metrics
        if metric.get("latest") is not None
    ]
    return structure_indicator_contract({
        "schema_version": EXTERNAL_SCHEMA_VERSION,
        "view": "external_sector",
        "country": "BR",
        "generated_at": _iso_z(generated_at),
        **context.contract_fields(),
        "status": "available" if available else "unavailable",
        "availability": {"available_metrics": available, "total_metrics": len(all_metrics)},
        "latest_reference": max(latest_dates) if latest_dates else None,
        "groups": groups,
        "methodology": {
            "exchange_rate_boundary": "The panel describes exchange-rate and external-sector indicators but does not estimate a fair exchange rate or assign exchange-rate movements to a single cause.",
            "br_us_spreads": "Brazil-US nominal and real rate differentials are published only when the required official US benchmarks are available.",
        },
    })


def publish_external_json(
    connection: sqlite3.Connection,
    *,
    output_path: str | Path,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> Path:
    return write_json_atomic(
        build_external_document(
            connection, generated_at=generated_at, knowledge_mode=knowledge_mode, knowledge_cutoff=knowledge_cutoff
        ),
        Path(output_path),
    )
