"""Curated, source-backed historical policy inputs for Brazil.

The catalog deliberately stores documentary regimes and vintages instead of
pretending that non-observable policy concepts are ordinary observed series.
Every entry has an explicit publication boundary that can be used by as-known
queries without retroactive knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PolicyInputSpec:
    key: str
    value: float
    unit: str
    data_kind: str
    effective_from: date
    effective_to: date | None
    published_on: date
    source_reference: str
    methodology: str
    reference_period: str
    source_url: str
    source_label: str
    note: str


@dataclass(frozen=True, slots=True)
class OutputGapVintageSpec:
    reference_period: str
    value: float
    published_on: date
    report_key: str
    source_reference: str
    source_url: str
    source_label: str
    note: str = ""


_TARGET_SOURCE_URL = "https://www.bcb.gov.br/controleinflacao/historicometas"

# Formal CMN target centres. 2003 and 2004 use the revised formal targets, not
# the operational adjusted targets announced in open letters.
_TARGETS = (
    (1999, 8.00, date(1999, 6, 30), "Resolução CMN nº 2.615, de 30/06/1999"),
    (2000, 6.00, date(1999, 6, 30), "Resolução CMN nº 2.615, de 30/06/1999"),
    (2001, 4.00, date(1999, 6, 30), "Resolução CMN nº 2.615, de 30/06/1999"),
    (2002, 3.50, date(2000, 6, 28), "Resolução CMN nº 2.744, de 28/06/2000"),
    (2003, 4.00, date(2002, 6, 27), "Resolução CMN nº 2.972, de 27/06/2002"),
    (2004, 5.50, date(2003, 6, 25), "Resolução CMN nº 3.108, de 25/06/2003"),
    (2005, 4.50, date(2003, 6, 25), "Resolução CMN nº 3.108, de 25/06/2003"),
    (2006, 4.50, date(2004, 6, 30), "Resolução CMN nº 3.210, de 30/06/2004"),
    (2007, 4.50, date(2005, 6, 23), "Resolução CMN nº 3.291, de 23/06/2005"),
    (2008, 4.50, date(2006, 6, 29), "Resolução CMN nº 3.378, de 29/06/2006"),
    (2009, 4.50, date(2007, 6, 26), "Resolução CMN nº 3.463, de 26/06/2007"),
    (2010, 4.50, date(2008, 7, 1), "Resolução CMN nº 3.584, de 01/07/2008"),
    (2011, 4.50, date(2009, 6, 30), "Resolução CMN nº 3.748, de 30/06/2009"),
    (2012, 4.50, date(2010, 6, 22), "Resolução CMN nº 3.880, de 22/06/2010"),
    (2013, 4.50, date(2011, 6, 30), "Resolução CMN nº 3.991, de 30/06/2011"),
    (2014, 4.50, date(2012, 6, 28), "Resolução CMN nº 4.095, de 28/06/2012"),
    (2015, 4.50, date(2013, 6, 28), "Resolução CMN nº 4.237, de 28/06/2013"),
    (2016, 4.50, date(2014, 6, 25), "Resolução CMN nº 4.345, de 25/06/2014"),
    (2017, 4.50, date(2015, 6, 25), "Resolução CMN nº 4.419, de 25/06/2015"),
    (2018, 4.50, date(2016, 6, 30), "Resolução CMN nº 4.499, de 30/06/2016"),
    (2019, 4.25, date(2017, 6, 29), "Resolução CMN nº 4.582, de 29/06/2017"),
    (2020, 4.00, date(2017, 6, 29), "Resolução CMN nº 4.582, de 29/06/2017"),
    (2021, 3.75, date(2018, 6, 26), "Resolução CMN nº 4.671, de 26/06/2018"),
    (2022, 3.50, date(2019, 6, 27), "Resolução CMN nº 4.724, de 27/06/2019"),
    (2023, 3.25, date(2020, 6, 25), "Resolução CMN nº 4.831, de 25/06/2020"),
    (2024, 3.00, date(2021, 6, 24), "Resolução CMN nº 4.918, de 24/06/2021"),
)

INFLATION_TARGET_INPUTS: tuple[PolicyInputSpec, ...] = tuple(
    PolicyInputSpec(
        key="br.inflation.target",
        value=value,
        unit="percent_per_year",
        data_kind="observed",
        effective_from=date(year, 1, 1),
        effective_to=date(year, 12, 31),
        published_on=published_on,
        source_reference=resolution,
        methodology="Centro da meta anual de inflação fixada pelo Conselho Monetário Nacional.",
        reference_period=str(year),
        source_url=_TARGET_SOURCE_URL,
        source_label="BCB — Histórico: meta de inflação vs. inflação efetiva",
        note="Centro formal da meta do CMN; não confundir com metas ajustadas operacionalmente em cartas abertas.",
    )
    for year, value, published_on, resolution in _TARGETS
) + (
    PolicyInputSpec(
        key="br.inflation.target",
        value=3.0,
        unit="percent_per_year",
        data_kind="observed",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        published_on=date(2024, 6, 26),
        source_reference="Resolução CMN nº 5.141, de 26/06/2024",
        methodology="Meta contínua para a variação do IPCA acumulada em doze meses.",
        reference_period="desde 2025-01",
        source_url=_TARGET_SOURCE_URL,
        source_label="BCB — Histórico: meta de inflação vs. inflação efetiva",
        note="Meta contínua de 3,00%, com intervalo de tolerância de ±1,5 p.p.",
    ),
)

NEUTRAL_RATE_INPUTS: tuple[PolicyInputSpec, ...] = (
    PolicyInputSpec(
        key="br.neutral_real_rate.rpm", value=4.0, unit="percent_per_year", data_kind="estimated",
        effective_from=date(2023, 2, 7), effective_to=date(2023, 6, 26), published_on=date(2023, 2, 7),
        source_reference="Ata da 252ª reunião do Copom — fevereiro de 2023",
        methodology="Hipótese de taxa de juros real neutra utilizada pelo Copom em suas projeções.",
        reference_period="Copom 2023-02", source_url="https://www.bcb.gov.br/publicacoes/atascopom/01022023",
        source_label="BCB — Ata do Copom, fevereiro de 2023",
        note="Variável não observável; a ata registra manutenção da hipótese em 4,0%.",
    ),
    PolicyInputSpec(
        key="br.neutral_real_rate.rpm", value=4.5, unit="percent_per_year", data_kind="estimated",
        effective_from=date(2023, 6, 27), effective_to=date(2024, 6, 24), published_on=date(2023, 6, 27),
        source_reference="Ata da 255ª reunião do Copom — junho de 2023",
        methodology="Hipótese de taxa de juros real neutra utilizada pelo Copom em suas projeções.",
        reference_period="Copom 2023-06", source_url="https://www.bcb.gov.br/publicacoes/atascopom/21062023",
        source_label="BCB — Ata do Copom, junho de 2023",
        note="O Copom elevou a hipótese de taxa neutra de 4,0% para 4,5%.",
    ),
    PolicyInputSpec(
        key="br.neutral_real_rate.rpm", value=4.75, unit="percent_per_year", data_kind="estimated",
        effective_from=date(2024, 6, 25), effective_to=date(2024, 12, 16), published_on=date(2024, 6, 25),
        source_reference="Ata da 263ª reunião do Copom — junho de 2024",
        methodology="Hipótese de taxa de juros real neutra utilizada pelo Copom em suas projeções.",
        reference_period="Copom 2024-06", source_url="https://www.bcb.gov.br/publicacoes/atascopom/19062024",
        source_label="BCB — Ata do Copom, junho de 2024",
        note="O Copom elevou a hipótese de taxa neutra para 4,75%.",
    ),
    PolicyInputSpec(
        key="br.neutral_real_rate.rpm", value=5.0, unit="percent_per_year", data_kind="estimated",
        effective_from=date(2024, 12, 17), effective_to=None, published_on=date(2024, 12, 17),
        source_reference="Ata da 267ª reunião do Copom — dezembro de 2024",
        methodology="Hipótese de taxa de juros real neutra utilizada pelo Copom em suas projeções.",
        reference_period="Copom 2024-12", source_url="https://www.bcb.gov.br/publicacoes/atascopom/11122024",
        source_label="BCB — Ata do Copom, dezembro de 2024",
        note="O Copom elevou a hipótese de taxa neutra para 5,0%; a hipótese permanece documental e não observável.",
    ),
)

POLICY_INPUTS: tuple[PolicyInputSpec, ...] = INFLATION_TARGET_INPUTS + NEUTRAL_RATE_INPUTS
POLICY_INPUTS_BY_KEY = {item.key: item for item in POLICY_INPUTS}

# Curated Copom output-gap vintages. Duplicate reference periods are deliberate:
# they preserve revisions as they became available in successive RI/RPM editions.
OUTPUT_GAP_VINTAGES: tuple[OutputGapVintageSpec, ...] = (
    OutputGapVintageSpec("2024-Q2", 0.5, date(2024, 9, 26), "RI-2024-09", "RI setembro/2024 — hiato do produto", "https://www.bcb.gov.br/publicacoes/ri/202409", "BCB — Relatório de Inflação, setembro de 2024"),
    OutputGapVintageSpec("2024-Q3", 0.5, date(2024, 9, 26), "RI-2024-09", "RI setembro/2024 — hiato do produto", "https://www.bcb.gov.br/publicacoes/ri/202409", "BCB — Relatório de Inflação, setembro de 2024"),
    OutputGapVintageSpec("2024-Q3", 0.7, date(2024, 12, 19), "RI-2024-12", "RI dezembro/2024 — hiato do produto", "https://www.bcb.gov.br/publicacoes/ri/202412", "BCB — Relatório de Inflação, dezembro de 2024"),
    OutputGapVintageSpec("2024-Q4", 0.7, date(2024, 12, 19), "RI-2024-12", "RI dezembro/2024 — hiato do produto", "https://www.bcb.gov.br/publicacoes/ri/202412", "BCB — Relatório de Inflação, dezembro de 2024"),
    OutputGapVintageSpec("2024-Q4", 0.8, date(2025, 3, 27), "RPM-2025-03", "RPM março/2025 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202503", "BCB — Relatório de Política Monetária, março de 2025"),
    OutputGapVintageSpec("2025-Q1", 0.6, date(2025, 3, 27), "RPM-2025-03", "RPM março/2025 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202503", "BCB — Relatório de Política Monetária, março de 2025"),
    OutputGapVintageSpec("2025-Q1", 0.9, date(2025, 6, 26), "RPM-2025-06", "RPM junho/2025 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202506", "BCB — Relatório de Política Monetária, junho de 2025"),
    OutputGapVintageSpec("2025-Q2", 0.5, date(2025, 6, 26), "RPM-2025-06", "RPM junho/2025 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202506", "BCB — Relatório de Política Monetária, junho de 2025"),
    OutputGapVintageSpec("2025-Q2", 0.7, date(2025, 9, 25), "RPM-2025-09", "RPM setembro/2025 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202509", "BCB — Relatório de Política Monetária, setembro de 2025"),
    OutputGapVintageSpec("2025-Q3", 0.5, date(2025, 9, 25), "RPM-2025-09", "RPM setembro/2025 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202509", "BCB — Relatório de Política Monetária, setembro de 2025"),
    OutputGapVintageSpec("2025-Q4", 0.4, date(2026, 3, 27), "RPM-2026-03", "RPM março/2026 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202603", "BCB — Relatório de Política Monetária, março de 2026"),
    OutputGapVintageSpec("2026-Q1", 0.1, date(2026, 3, 27), "RPM-2026-03", "RPM março/2026 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202603", "BCB — Relatório de Política Monetária, março de 2026"),
    OutputGapVintageSpec("2026-Q1", 0.5, date(2026, 6, 25), "RPM-2026-06", "RPM junho/2026 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202606", "BCB — Relatório de Política Monetária, junho de 2026"),
    OutputGapVintageSpec("2026-Q2", 0.4, date(2026, 6, 25), "RPM-2026-06", "RPM junho/2026 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202606", "BCB — Relatório de Política Monetária, junho de 2026"),
    OutputGapVintageSpec("2026-Q2", 0.5, date(2026, 9, 24), "RPM-2026-09", "RPM setembro/2026 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202609", "BCB — Relatório de Política Monetária, setembro de 2026"),
    OutputGapVintageSpec("2026-Q3", 0.4, date(2026, 9, 24), "RPM-2026-09", "RPM setembro/2026 — hiato do produto", "https://www.bcb.gov.br/publicacoes/rpm/202609", "BCB — Relatório de Política Monetária, setembro de 2026", "O valor do trimestre corrente incorpora variáveis de atividade parcialmente projetadas, conforme a ressalva do relatório."),
)
