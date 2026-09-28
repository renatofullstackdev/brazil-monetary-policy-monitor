"""Versioned documentary snapshot of official Federal Public Debt indicators.

These RMD indicators are preserved as reported values rather than reconstructed
from a simpler stock dataset. Maturity, cost and liquidity have official
methodologies that the monitor should not silently approximate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class FiscalProfileInput:
    key: str
    value: float
    unit: str
    data_kind: str
    effective_from: date
    published_on: date
    source_reference: str
    methodology: str
    reference_period: str
    source_url: str
    source_label: str
    note: str


RMD_JULY_2026_URL = "https://www.tesourotransparente.gov.br/publicacoes/relatorio-mensal-da-divida-rmd/2026/7"


def _item(key: str, value: float, unit: str, source_reference: str, methodology: str, note: str) -> FiscalProfileInput:
    return FiscalProfileInput(
        key=key,
        value=value,
        unit=unit,
        data_kind="observed",
        effective_from=date(2026, 7, 31),
        published_on=date(2026, 8, 26),
        source_reference=source_reference,
        methodology=methodology,
        reference_period="2026-07",
        source_url=RMD_JULY_2026_URL,
        source_label="Tesouro Nacional — Relatório Mensal da Dívida, julho de 2026",
        note=note,
    )


FISCAL_PROFILE_INPUTS: tuple[FiscalProfileInput, ...] = (
    _item(
        "br.dpf.stock_brl_billions", 9288.78, "brl_billions", "RMD julho/2026, Tabela 2.1",
        "Estoque da Dívida Pública Federal em poder do público, conforme metodologia do RMD.",
        "DPF = DPMFi + DPFe em poder do público.",
    ),
    _item(
        "br.dpf.composition.fixed_rate_share", 19.22, "percent", "RMD julho/2026, Tabela 2.3",
        "Participação no estoque da DPF por indexador, conforme classificação oficial do RMD.",
        "Parcela prefixada do estoque da DPF.",
    ),
    _item(
        "br.dpf.composition.price_index_share", 26.02, "percent", "RMD julho/2026, Tabela 2.3",
        "Participação no estoque da DPF por indexador, conforme classificação oficial do RMD.",
        "Parcela vinculada a índices de preços.",
    ),
    _item(
        "br.dpf.composition.floating_rate_share", 51.11, "percent", "RMD julho/2026, Tabela 2.3",
        "Participação no estoque da DPF por indexador, conforme classificação oficial do RMD.",
        "Parcela remunerada por taxa flutuante.",
    ),
    _item(
        "br.dpf.composition.fx_share", 3.65, "percent", "RMD julho/2026, Tabela 2.3",
        "Participação no estoque da DPF por indexador, conforme classificação oficial do RMD.",
        "Parcela vinculada a câmbio.",
    ),
    _item(
        "br.dpf.maturing_12m_share", 18.91, "percent", "RMD julho/2026, Tabela 3.1",
        "Percentual do estoque da DPF com vencimento nos doze meses seguintes, conforme RMD.",
        "Indicador oficial; não é reconstruído pelo monitor a partir de vencimentos finais.",
    ),
    _item(
        "br.dpf.average_term_years", 4.05, "years", "RMD julho/2026, Tabela 3.3",
        "Prazo médio da DPF segundo a metodologia oficial do Tesouro Nacional.",
        "Não equivale a uma média simples das datas finais de vencimento.",
    ),
    _item(
        "br.dpf.average_cost_12m", 12.45, "percent_per_year", "RMD julho/2026, Tabela 4.1",
        "Custo médio acumulado em doze meses do estoque da DPF, conforme metodologia oficial do Tesouro.",
        "Não é a Selic nem o custo marginal de emissão.",
    ),
    _item(
        "br.dpf.liquidity_reserve_brl_billions", 1371.21, "brl_billions", "RMD julho/2026, seção 6",
        "Disponibilidades de caixa destinadas ao pagamento da dívida e saldo de emissões, conforme RMD.",
        "Reserva de liquidez nominal no fechamento de julho de 2026.",
    ),
    _item(
        "br.dpf.liquidity_index_months", 7.81, "months", "RMD julho/2026, seção 6",
        "Meses de vencimentos da DPMFi cobertos pela reserva de liquidez, segundo cálculo oficial do RMD.",
        "Índice de liquidez expresso em meses de vencimentos cobertos.",
    ),
)

FISCAL_PROFILE_BY_KEY = {item.key: item for item in FISCAL_PROFILE_INPUTS}
