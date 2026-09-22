"""Source-backed monetary-policy inputs curated from official BCB publications.

These values are documentary inputs, not API observations.  Each entry preserves
its source, publication date and reference period so that the monitor never
turns an unobservable estimate into an unlabeled constant.
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
    published_on: date
    source_reference: str
    methodology: str
    reference_period: str
    source_url: str
    source_label: str
    note: str


POLICY_INPUTS: tuple[PolicyInputSpec, ...] = (
    PolicyInputSpec(
        key="br.inflation.target",
        value=3.0,
        unit="percent_per_year",
        data_kind="observed",
        effective_from=date(2025, 1, 1),
        published_on=date(2024, 6, 26),
        source_reference="Resolução CMN nº 5.141, de 26/06/2024",
        methodology="Meta contínua para a variação do IPCA acumulada em doze meses.",
        reference_period="desde 2025-01",
        source_url="https://www.bcb.gov.br/controleinflacao/historicometas",
        source_label="BCB — Histórico: meta de inflação vs. inflação efetiva",
        note="Meta de 3,00%, com intervalo de tolerância de ±1,5 p.p.",
    ),
    PolicyInputSpec(
        key="br.neutral_real_rate.rpm",
        value=5.0,
        unit="percent_per_year",
        data_kind="estimated",
        effective_from=date(2026, 6, 25),
        published_on=date(2026, 6, 25),
        source_reference="RPM junho/2026, p. 65",
        methodology="Taxa de juros real neutra considerada nas projeções do cenário de referência do Copom.",
        reference_period="RPM 2026-06",
        source_url="https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606p.pdf",
        source_label="BCB — Relatório de Política Monetária, junho de 2026",
        note="Variável não observável; o próprio BCB ressalta elevada incerteza e uso de múltiplas metodologias.",
    ),
    PolicyInputSpec(
        key="br.output_gap.rpm",
        value=0.4,
        unit="percentage_points",
        data_kind="estimated",
        effective_from=date(2026, 4, 1),
        published_on=date(2026, 6, 25),
        source_reference="RPM junho/2026, p. 68; 2º trimestre de 2026",
        methodology="Hiato do produto do cenário de referência, combinando modelos, outras metodologias e julgamento do Copom.",
        reference_period="2026-Q2",
        source_url="https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606p.pdf",
        source_label="BCB — Relatório de Política Monetária, junho de 2026",
        note="Estimativa de 0,4% para o 2º trimestre de 2026; é o último valor documental incorporado até esta sprint, não uma observação corrente.",
    ),
)

POLICY_INPUTS_BY_KEY = {item.key: item for item in POLICY_INPUTS}
