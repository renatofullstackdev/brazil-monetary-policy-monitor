"""Audited US benchmark series retrieved through the Federal Reserve's FRED service."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class USSeriesSpec:
    key: str
    fred_id: str
    title: str
    description: str
    unit_original: str
    unit_normalized: str
    frequency: str
    data_kind: str
    transformation: str
    documentation_url: str

US_SERIES: tuple[USSeriesSpec, ...] = (
    USSeriesSpec("us.policy.effr", "DFF", "Federal Funds Effective Rate", "Taxa efetiva diária dos federal funds, influenciada pelo corredor operacional do Federal Reserve.", "Percent", "percent_per_year", "daily", "observed", "identity", "https://fred.stlouisfed.org/series/DFF"),
    USSeriesSpec("us.treasury.2y", "DGS2", "Treasury constant maturity — 2 anos", "Yield nominal de Treasury de maturidade constante em 2 anos.", "Percent", "percent_per_year", "daily", "observed", "identity", "https://fred.stlouisfed.org/series/DGS2"),
    USSeriesSpec("us.treasury.10y", "DGS10", "Treasury constant maturity — 10 anos", "Yield nominal de Treasury de maturidade constante em 10 anos.", "Percent", "percent_per_year", "daily", "observed", "identity", "https://fred.stlouisfed.org/series/DGS10"),
    USSeriesSpec("us.treasury.real_10y", "DFII10", "Treasury real — 10 anos", "Yield de Treasury indexado à inflação em maturidade constante de 10 anos.", "Percent", "percent_per_year", "daily", "observed", "identity", "https://fred.stlouisfed.org/series/DFII10"),
    USSeriesSpec("us.inflation.breakeven_10y", "T10YIE", "Inflação implícita EUA — 10 anos", "Breakeven de inflação em 10 anos publicado pelo Federal Reserve Bank of St. Louis.", "Percent", "percent_per_year", "daily", "derived", "identity_from_fred", "https://fred.stlouisfed.org/series/T10YIE"),
    USSeriesSpec("us.inflation.pce_index", "PCEPI", "PCE Price Index", "Índice de preços de gastos de consumo pessoal produzido pelo BEA; medida de inflação preferida pelo Federal Reserve.", "Index 2017=100", "index", "monthly", "observed", "identity", "https://fred.stlouisfed.org/series/PCEPI"),
    USSeriesSpec("us.gdp.real", "GDPC1", "PIB real dos EUA", "Produto interno bruto real, dessazonalizado e anualizado, produzido pelo BEA.", "Billions of chained 2017 dollars", "usd_billions_chained_2017", "quarterly", "observed", "identity", "https://fred.stlouisfed.org/series/GDPC1"),
    USSeriesSpec("us.gdp.potential", "GDPPOT", "PIB potencial real dos EUA", "Estimativa trimestral de PIB potencial real produzida pelo Congressional Budget Office.", "Billions of chained 2017 dollars", "usd_billions_chained_2017", "quarterly", "estimated", "identity", "https://fred.stlouisfed.org/series/GDPPOT"),
)
US_SERIES_BY_KEY = {item.key: item for item in US_SERIES}
