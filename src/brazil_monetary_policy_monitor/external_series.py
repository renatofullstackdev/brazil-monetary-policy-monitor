"""Audited registry for Brazilian external-sector and exchange-rate SGS series."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExternalSeriesSpec:
    key: str
    code: int
    title: str
    description: str
    unit_original: str
    unit_normalized: str
    frequency: str
    data_kind: str
    transformation: str
    documentation_url: str


EXTERNAL_SERIES: tuple[ExternalSeriesSpec, ...] = (
    ExternalSeriesSpec(
        key="br.fx.usd_brl.sell",
        code=1,
        title="Taxa de câmbio — Livre — Dólar americano (venda) — diário",
        description=(
            "Cotação diária de venda do dólar americano em reais, publicada pelo Banco Central do Brasil."
        ),
        unit_original="Taxa unidade monetária corrente/dólar americano",
        unit_normalized="brl_per_usd",
        frequency="daily",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://dadosabertos.bcb.gov.br/dataset/1-taxa-de-cambio---livre---dolar-americano-venda---diario"
        ),
    ),
    ExternalSeriesSpec(
        key="br.fx.reer_ipca",
        code=11752,
        title="Índice da taxa de câmbio real efetiva (IPCA) — Jun/1994=100",
        description=(
            "Índice mensal de taxa de câmbio real efetiva calculado pelo BCB com IPCA doméstico, "
            "índices de preços externos e ponderação por parceiros comerciais."
        ),
        unit_original="Índice",
        unit_normalized="index",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?"
            "method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=11752"
        ),
    ),
    ExternalSeriesSpec(
        key="br.external.current_account_12m_gdp",
        code=23079,
        title="Transações correntes acumuladas em 12 meses em relação ao PIB",
        description=(
            "Saldo das transações correntes acumulado em doze meses como percentual do PIB, "
            "incluindo bens, serviços, renda primária e renda secundária."
        ),
        unit_original="Percentual",
        unit_normalized="percent_of_gdp",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://dadosabertos.bcb.gov.br/dataset/23079-transacoes-correntes-acumulado-em-12-meses-em-relacao-ao-pib---mensal"
        ),
    ),
    ExternalSeriesSpec(
        key="br.external.idp_12m_gdp",
        code=23080,
        title="Investimento Direto no País acumulado em 12 meses em relação ao PIB",
        description=(
            "Ingresso líquido de investimento direto no país acumulado em doze meses, "
            "expresso como percentual do PIB."
        ),
        unit_original="Percentual",
        unit_normalized="percent_of_gdp",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?"
            "method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=23080"
        ),
    ),
    ExternalSeriesSpec(
        key="br.external.portfolio_liabilities_net",
        code=22924,
        title="Investimentos em carteira — passivos — mensal — líquido",
        description=(
            "Fluxo líquido mensal de passivos de investimento em carteira no balanço de pagamentos, "
            "abrangendo instrumentos de participação e títulos de dívida segundo o BPM6."
        ),
        unit_original="Milhões de dólares americanos",
        unit_normalized="usd_millions",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://dadosabertos.bcb.gov.br/dataset/22924-investimentos-em-carteira---passivos---mensal---liquido"
        ),
    ),
    ExternalSeriesSpec(
        key="br.external.reserves_liquidity",
        code=13982,
        title="Reservas internacionais — conceito liquidez — total — diária",
        description=(
            "Ativos externos prontamente disponíveis e controlados pelo BCB para necessidades do "
            "balanço de pagamentos, intervenção cambial e outros fins relacionados, no conceito liquidez."
        ),
        unit_original="Milhões de dólares americanos",
        unit_normalized="usd_millions",
        frequency="daily",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://dadosabertos.bcb.gov.br/dataset/13982-reservas-internacionais---conceito-liquidez---total---diaria"
        ),
    ),
)

EXTERNAL_SERIES_BY_KEY = {spec.key: spec for spec in EXTERNAL_SERIES}
EXTERNAL_SERIES_BY_CODE = {spec.code: spec for spec in EXTERNAL_SERIES}
EXTERNAL_DAILY_SERIES = tuple(spec for spec in EXTERNAL_SERIES if spec.frequency == "daily")
EXTERNAL_MONTHLY_SERIES = tuple(spec for spec in EXTERNAL_SERIES if spec.frequency == "monthly")
