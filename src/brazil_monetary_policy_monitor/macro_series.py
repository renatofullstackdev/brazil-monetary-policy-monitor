"""Audited registry for the Sprint 7 BCB SGS macro context series."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SGSSeriesSpec:
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


MACRO_SERIES: tuple[SGSSeriesSpec, ...] = (
    SGSSeriesSpec(
        key="br.ipca.monthly",
        code=433,
        title="Índice Nacional de Preços ao Consumidor Amplo (IPCA)",
        description="Variação percentual mensal do IPCA, produzido pelo IBGE e distribuído no SGS do BCB.",
        unit_original="Variação percentual mensal",
        unit_normalized="percent_per_month",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=433",
    ),
    SGSSeriesSpec(
        key="br.ipca.services.monthly",
        code=10844,
        title="IPCA — Serviços",
        description="Variação percentual mensal do segmento de serviços do IPCA, série do BCB/Depec.",
        unit_original="Variação percentual mensal",
        unit_normalized="percent_per_month",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://dadosabertos.bcb.gov.br/dataset/10844-indice-de-precos-ao-consumidor-amplo-ipca---servicos",
    ),
    SGSSeriesSpec(
        key="br.ipca.core.trimmed_unsmoothed.monthly",
        code=11426,
        title="IPCA — Núcleo de médias aparadas sem suavização",
        description="Variação percentual mensal do núcleo do IPCA por médias aparadas sem suavização.",
        unit_original="Variação percentual mensal",
        unit_normalized="percent_per_month",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://dadosabertos.bcb.gov.br/dataset/11426-indice-nacional-de-precos-ao-consumidor---amplo-ipca---nucleo-medias-aparadas-sem-suavizacao",
    ),
    SGSSeriesSpec(
        key="br.ibc_br.sa",
        code=24364,
        title="IBC-Br — com ajuste sazonal",
        description="Índice de Atividade Econômica do Banco Central com ajuste sazonal.",
        unit_original="Índice",
        unit_normalized="index",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://dadosabertos.bcb.gov.br/dataset/24364-indice-de-atividade-economica-do-banco-central-ibc-br---com-ajuste-sazonal",
    ),
    SGSSeriesSpec(
        key="br.unemployment.pnadc",
        code=24369,
        title="Taxa de desocupação — PNAD Contínua",
        description="Taxa de desocupação da PNAD Contínua disponibilizada no SGS do BCB.",
        unit_original="%",
        unit_normalized="percent",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=24369",
    ),
    SGSSeriesSpec(
        key="br.real_earnings.pnadc",
        code=24380,
        title="Rendimento médio real habitual — todos os trabalhos",
        description="Rendimento médio real habitual de todos os trabalhos da PNAD Contínua, disponibilizado no SGS do BCB.",
        unit_original="R$",
        unit_normalized="brl_real",
        frequency="monthly",
        data_kind="observed",
        transformation="identity",
        documentation_url="https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=24380",
    ),
)

MACRO_SERIES_BY_KEY = {spec.key: spec for spec in MACRO_SERIES}
MACRO_SERIES_BY_CODE = {spec.code: spec for spec in MACRO_SERIES}
