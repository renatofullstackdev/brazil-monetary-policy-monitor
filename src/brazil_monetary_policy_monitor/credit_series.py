"""Audited registry for BCB SGS credit and monetary-transmission series."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreditSeriesSpec:
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


CREDIT_SERIES: tuple[CreditSeriesSpec, ...] = (
    CreditSeriesSpec(
        key="br.credit.free.balance",
        code=20542,
        title="Saldo da carteira de crédito com recursos livres — Total",
        description=(
            "Saldo em final de período das operações de crédito com taxas de juros "
            "livremente pactuadas entre mutuários e instituições financeiras."
        ),
        unit_original="Milhões de reais",
        unit_normalized="brl_millions",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://dadosabertos.bcb.gov.br/dataset/20542-saldo-da-carteira-de-credito-com-recursos-livres---total",
    ),
    CreditSeriesSpec(
        key="br.credit.directed.balance",
        code=20593,
        title="Saldo da carteira de crédito com recursos direcionados — Total",
        description=(
            "Saldo em final de período das operações de crédito regulamentadas pelo CMN "
            "ou vinculadas a recursos orçamentários e outras fontes direcionadas."
        ),
        unit_original="Milhões de reais",
        unit_normalized="brl_millions",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://dadosabertos.bcb.gov.br/dataset/20593-saldo-da-carteira-de-credito-com-recursos-direcionados---total",
    ),
    CreditSeriesSpec(
        key="br.credit.free.interest_rate",
        code=20717,
        title="Taxa média de juros das operações de crédito com recursos livres — Total",
        description=(
            "Taxa média de juros das novas operações de crédito com recursos livres, "
            "ponderada pelo valor das concessões."
        ),
        unit_original="Percentual ao ano",
        unit_normalized="percent_per_year",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://dadosabertos.bcb.gov.br/dataset/20717-taxa-media-de-juros-das-operacoes-de-credito-com-recursos-livres---total",
    ),
    CreditSeriesSpec(
        key="br.credit.directed.interest_rate",
        code=20756,
        title="Taxa média de juros das operações de crédito com recursos direcionados — Total",
        description=(
            "Taxa média de juros das novas operações de crédito com recursos direcionados, "
            "ponderada pelo valor das concessões."
        ),
        unit_original="Percentual ao ano",
        unit_normalized="percent_per_year",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://dadosabertos.bcb.gov.br/dataset/20756-taxa-media-de-juros-das-operacoes-de-credito-com-recursos-direcionados---total",
    ),
    CreditSeriesSpec(
        key="br.credit.free.delinquency",
        code=21085,
        title="Inadimplência da carteira de crédito com recursos livres — Total",
        description=(
            "Percentual da carteira de crédito livre com pelo menos uma parcela "
            "em atraso superior a 90 dias."
        ),
        unit_original="Percentual",
        unit_normalized="percent",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://dadosabertos.bcb.gov.br/dataset/21085-inadimplencia-da-carteira-de-credito-com-recursos-livres---total",
    ),
    CreditSeriesSpec(
        key="br.credit.directed.delinquency",
        code=21132,
        title="Inadimplência da carteira de crédito com recursos direcionados — Total",
        description=(
            "Percentual da carteira de crédito direcionado com pelo menos uma parcela "
            "em atraso superior a 90 dias."
        ),
        unit_original="Percentual",
        unit_normalized="percent",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://dadosabertos.bcb.gov.br/dataset/21132-inadimplencia-da-carteira-de-credito-com-recursos-direcionados---total",
    ),
)

CREDIT_SERIES_BY_KEY = {spec.key: spec for spec in CREDIT_SERIES}
CREDIT_SERIES_BY_CODE = {spec.code: spec for spec in CREDIT_SERIES}
