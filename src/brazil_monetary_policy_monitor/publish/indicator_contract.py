"""Public indicator metadata for browser-facing contracts.

Machine identifiers remain internal keys. Every value rendered in the indicator
metadata dialog must have an explicitly curated Portuguese label. Unknown values
fail publication instead of leaking implementation names into the UI.
"""

from __future__ import annotations

import re
from typing import Any


INPUT_LABELS: dict[str, str] = {
    # Monetary policy / macro
    "br.selic.target": "Meta Selic",
    "selic": "Meta Selic",
    "focus.monthly.ipca": "Medianas mensais do Focus para o IPCA",
    "policy_horizon": "Horizonte relevante da política monetária",
    "expected_inflation": "Inflação esperada no horizonte da política monetária",
    "br.inflation.target": "Meta de inflação",
    "inflation_target": "Meta de inflação aplicável ao horizonte",
    "br.neutral_real_rate.rpm": "Taxa real neutra assumida pelo Copom",
    "neutral_real_rate": "Taxa real neutra assumida pelo Copom",
    "br.output_gap.copom": "Hiato do produto estimado pelo Copom",
    "output_gap": "Hiato do produto",
    "ex_ante_real_rate": "Juro real ex ante",
    "taylor_prospective": "Taylor prospectiva",
    "br.ipca.monthly": "IPCA mensal",
    "br.ipca.services.monthly": "IPCA de serviços mensal",
    "br.ipca.core.trimmed_unsmoothed.monthly": "Núcleo do IPCA por médias aparadas sem suavização",
    "br.ibc_br.sa": "IBC-Br com ajuste sazonal",
    "br.unemployment.pnadc": "Taxa de desocupação — PNAD Contínua",
    "br.real_earnings.pnadc": "Rendimento médio real habitual — PNAD Contínua",

    # Crédito
    "br.credit.free.balance": "Saldo do crédito com recursos livres",
    "br.credit.directed.balance": "Saldo do crédito com recursos direcionados",
    "br.credit.free.interest_rate": "Taxa média de juros do crédito livre",
    "br.credit.directed.interest_rate": "Taxa média de juros do crédito direcionado",
    "br.credit.free.delinquency": "Inadimplência do crédito livre",
    "br.credit.directed.delinquency": "Inadimplência do crédito direcionado",
    "credit.free": "Crédito livre",
    "credit.directed": "Crédito direcionado",

    # Fiscal
    "br.fiscal.primary_result_12m_gdp": "Resultado primário em 12 meses / PIB",
    "br.fiscal.nominal_interest_12m_gdp": "Juros nominais em 12 meses / PIB",
    "br.fiscal.nominal_result_12m_gdp": "Resultado nominal em 12 meses / PIB",
    "br.fiscal.dbgg_gdp": "Dívida Bruta do Governo Geral / PIB",
    "br.fiscal.dlgg_gdp": "Dívida Líquida do Governo Geral / PIB",
    "br.fiscal.dlsp_gdp": "Dívida Líquida do Setor Público / PIB",

    # Setor externo
    "br.fx.usd_brl.sell": "Câmbio USD/BRL — venda",
    "br.fx.reer_ipca": "Taxa de câmbio real efetiva — IPCA",
    "br.external.current_account_12m_gdp": "Transações correntes em 12 meses / PIB",
    "br.external.idp_12m_gdp": "Investimento Direto no País em 12 meses / PIB",
    "br.external.portfolio_liabilities_net": "Investimento em carteira — passivos líquidos",
    "br.external.reserves_liquidity": "Reservas internacionais — conceito liquidez",

    # EUA
    "us.policy.effr": "Taxa efetiva dos Fed Funds (EFFR)",
    "us.treasury.2y": "Treasury nominal de 2 anos",
    "us.treasury.10y": "Treasury nominal de 10 anos",
    "us.treasury.real_10y": "Treasury real de 10 anos",
    "us.inflation.breakeven_10y": "Inflação implícita dos EUA em 10 anos",
    "us.inflation.pce_index": "Índice de preços PCE",
    "us.inflation.pce_12m": "Inflação PCE em 12 meses",
    "us.gdp.real": "PIB real dos EUA",
    "us.gdp.potential": "PIB potencial dos EUA",
    "us.output_gap.cbo": "Hiato do produto dos EUA — CBO",

    # Curvas de mercado definitivas/provisórias que permanecem no produto
    "br.anbima.ettj.real.10y": "ETTJ real ANBIMA em 10 anos",
    "br.b3.pre.10y": "Curva PRE da B3 em 10 anos",
}


FREQUENCY_LABELS: dict[str, str] = {
    "daily": "diária",
    "weekly": "semanal",
    "monthly": "mensal",
    "quarterly": "trimestral",
    "annual": "anual",
    "on_publication": "conforme cada publicação",
    "monthly_document_release": "mensal, conforme a publicação do relatório",
    "survey_date": "conforme a data da pesquisa Focus",
    "quarterly_document_vintage": "trimestral, conforme cada vintage publicado pelo Copom",
}


TRANSFORMATION_LABELS: dict[str, str] = {
    "identity": "sem transformação",
    "identidade": "sem transformação",
    "compound_12_monthly_focus_medians": "composição de 12 medianas mensais do Focus",
    "Selic menos a inflação esperada no horizonte da política": "Selic menos inflação esperada no horizonte da política monetária",
    "Taylor canônica (alpha=0.5, beta=0.5)": "regra de Taylor canônica, com pesos de 0,5 para inflação e hiato",
    "Selic menos Taylor prospectiva": "Selic menos Taylor prospectiva",
    "taxa real ex ante menos taxa real neutra": "juro real ex ante menos taxa real neutra",
    "variações percentuais mensais acumuladas dos últimos 12 meses": "composição das variações mensais nos últimos 12 meses",
    "índice mais recente sobre o anterior menos um": "variação percentual em relação à observação anterior",
    "nominal_balance_yoy_deflated_by_compounded_ipca_12m": "variação do saldo em 12 meses, descontada pela inflação acumulada no período",
    "idp_12m_gdp / abs(current_account_12m_gdp) * 100 when current_account < 0": "IDP em 12 meses dividido pelo módulo do déficit em transações correntes no mesmo período",
    "br_us.policy_spread": "Selic menos taxa efetiva dos Fed Funds (EFFR)",
    "br_b3_pre_10y_minus_us_treasury_10y": "curva PRE da B3 em 10 anos menos Treasury nominal dos EUA em 10 anos",
    "br_us.real_10y_spread": "ETTJ real ANBIMA em 10 anos menos Treasury real dos EUA em 10 anos",
    "us.inflation.pce_12m": "variação do índice de preços PCE em 12 meses",
    "us.output_gap.cbo": "PIB real menos PIB potencial, em proporção do PIB potencial",
    "us.taylor.classic": "regra de Taylor clássica para os EUA",
    "us.policy.real_ex_post": "taxa efetiva dos Fed Funds menos inflação PCE realizada em 12 meses",
    "us.treasury.slope_10y_2y": "Treasury nominal de 10 anos menos Treasury nominal de 2 anos",
    "identity_from_fred": "valor publicado diretamente pelo FRED",
    "free_minus_directed_same_reference_month": "crédito livre menos crédito direcionado na mesma referência mensal",
    "constant_tenor_10y_minus_2y": "taxa de 10 anos menos taxa de 2 anos da mesma curva",
    "ANBIMA ETTJ zero-coupon": "taxa zero-cupom da ETTJ ANBIMA",
    "published_rmd_value": "valor publicado no Relatório Mensal da Dívida",
}


_PERCENT_CHANGE_PATTERN = re.compile(
    r"^percent_change_vs_last_observation_on_or_before_(\d+)_calendar_days$"
)


def input_ref(key: str) -> dict[str, str]:
    try:
        label = INPUT_LABELS[key]
    except KeyError as exc:
        raise KeyError(f"missing public label for indicator input: {key}") from exc
    return {"key": key, "label": label}


def frequency_ref(key: str) -> dict[str, str]:
    try:
        label = FREQUENCY_LABELS[key]
    except KeyError as exc:
        raise KeyError(f"missing public label for indicator frequency: {key}") from exc
    return {"key": key, "label": label}


def transformation_ref(key: str) -> dict[str, str]:
    label = TRANSFORMATION_LABELS.get(key)
    if label is None:
        match = _PERCENT_CHANGE_PATTERN.fullmatch(key)
        if match:
            days = int(match.group(1))
            label = f"variação em relação à última observação disponível até {days} dias corridos antes"
    if label is None:
        raise KeyError(f"missing public label for indicator transformation: {key}")
    return {"key": key, "label": label}


def _is_indicator(value: dict[str, Any]) -> bool:
    return (
        isinstance(value.get("key"), str)
        and ("data_kind" in value or "kind" in value)
        and ("latest" in value or "observations" in value or "status" in value)
    )


def structure_indicator_contract(value: Any) -> Any:
    """Structure browser-facing indicator metadata recursively.

    ``inputs`` and ``missing_inputs`` become stable key/label references. For
    indicator objects, ``frequency`` and ``transformation`` become equivalent
    key/label references. This guarantees the browser never needs to humanize
    machine identifiers.
    """

    if isinstance(value, list):
        return [structure_indicator_contract(item) for item in value]
    if not isinstance(value, dict):
        return value

    indicator = _is_indicator(value)
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"inputs", "missing_inputs"} and isinstance(item, list):
            refs: list[dict[str, str]] = []
            for raw in item:
                if isinstance(raw, str):
                    refs.append(input_ref(raw))
                elif isinstance(raw, dict) and isinstance(raw.get("key"), str) and isinstance(raw.get("label"), str):
                    refs.append({"key": raw["key"], "label": raw["label"]})
                else:
                    raise TypeError(f"invalid indicator input reference: {raw!r}")
            result[key] = refs
        elif indicator and key == "frequency" and isinstance(item, str):
            result[key] = frequency_ref(item)
        elif indicator and key == "transformation" and isinstance(item, str):
            result[key] = transformation_ref(item)
        else:
            result[key] = structure_indicator_contract(item)
    return result
