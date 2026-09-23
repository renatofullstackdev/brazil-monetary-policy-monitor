"""Audited registry for Brazilian fiscal-flow and debt-stock SGS series."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FiscalSeriesSpec:
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


FISCAL_SERIES: tuple[FiscalSeriesSpec, ...] = (
    FiscalSeriesSpec(
        key="br.fiscal.primary_result_12m_gdp",
        code=5793,
        title="NFSP — resultado primário — setor público consolidado — 12 meses / PIB",
        description=(
            "Necessidades de Financiamento do Setor Público no conceito primário, "
            "setor público consolidado, fluxo acumulado em 12 meses como percentual do PIB."
        ),
        unit_original="Percentual",
        unit_normalized="percent_of_gdp",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://dadosabertos.bcb.gov.br/dataset/5793-nfsp-sem-desvalorizacao-cambial--pib---"
            "fluxo-acumulado-em-12-meses---resultado-primario---tota"
        ),
    ),
    FiscalSeriesSpec(
        key="br.fiscal.nominal_interest_12m_gdp",
        code=5760,
        title="NFSP — juros nominais — setor público consolidado — 12 meses / PIB",
        description=(
            "Juros nominais das Necessidades de Financiamento do Setor Público, "
            "setor público consolidado, fluxo acumulado em 12 meses como percentual do PIB."
        ),
        unit_original="Percentual",
        unit_normalized="percent_of_gdp",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://dadosabertos.bcb.gov.br/dataset/5760-nfsp-sem-desvalorizacao-cambial--pib---"
            "fluxo-acumulado-em-12-meses---juros-nominais---total---"
        ),
    ),
    FiscalSeriesSpec(
        key="br.fiscal.nominal_result_12m_gdp",
        code=5727,
        title="NFSP — resultado nominal — setor público consolidado — 12 meses / PIB",
        description=(
            "Necessidades de Financiamento do Setor Público no conceito nominal, "
            "setor público consolidado, fluxo acumulado em 12 meses como percentual do PIB."
        ),
        unit_original="Percentual",
        unit_normalized="percent_of_gdp",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://dadosabertos.bcb.gov.br/dataset/5727-nfsp-sem-desvalorizacao-cambial--pib---"
            "fluxo-acumulado-em-12-meses---resultado-nominal---total"
        ),
    ),
    FiscalSeriesSpec(
        key="br.fiscal.dbgg_gdp",
        code=13762,
        title="Dívida Bruta do Governo Geral — percentual do PIB",
        description=(
            "Dívida Bruta do Governo Geral segundo a metodologia do BCB utilizada a partir de 2008."
        ),
        unit_original="Percentual",
        unit_normalized="percent_of_gdp",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url=(
            "https://dadosabertos.bcb.gov.br/dataset/13762-divida-bruta-do-governo-geral--pib---"
            "metodologia-utilizada-a-partir-de-2008"
        ),
    ),
)

FISCAL_SERIES_BY_KEY = {spec.key: spec for spec in FISCAL_SERIES}
FISCAL_SERIES_BY_CODE = {spec.code: spec for spec in FISCAL_SERIES}
