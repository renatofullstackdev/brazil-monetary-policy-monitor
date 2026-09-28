# ADR 0012 — Versionar insumos documentais de política separadamente

## Status

Aceita na Sprint 7.

## Contexto

Meta de inflação, taxa real neutra e hiato do produto não chegam ao monitor pelo mesmo contrato de séries temporais. A meta é uma decisão normativa publicada pelo CMN; taxa neutra e hiato são estimativas não observáveis publicadas pelo BCB em documentos de política monetária.

Persistir esses valores como se fossem observações SGS apagaria diferenças relevantes de natureza, referência, método e disponibilidade. Por outro lado, embuti-los como constantes no código impediria auditoria e versionamento.

## Decisão

Esses insumos são armazenados em `parameters`, com:

- chave estável;
- valor e unidade;
- `data_kind`;
- início de vigência;
- data de publicação com precisão explicitada;
- `available_at`;
- referência documental;
- metodologia;
- URL, período de referência e observações em metadados;
- `version_key` imutável.

A Sprint 7 incorpora inicialmente:

- meta contínua de inflação de 3,00%, vigente desde janeiro de 2025;
- taxa real neutra de 5,00% usada no cenário de referência do RPM de junho de 2026;
- hiato do produto de 0,4% para o 2º trimestre de 2026 no mesmo RPM.

Taxa neutra e hiato permanecem classificados como `estimated`. A meta é `observed` no sentido de decisão oficial observável, não de variável econômica realizada.

Quando a fonte fornece apenas a data, o monitor usa `23:59:59Z` daquele dia como limite conservador de disponibilidade e registra `metadata_json.publication_time_precision = "day"`. Esse horário é uma fronteira operacional, não uma alegação sobre o instante real da publicação.

## Consequências

A Taylor prospectiva corrente pode ser publicada quando Focus, meta, taxa neutra e hiato estiverem disponíveis. Entretanto, esses valores documentais **não são retropropagados**. O monitor não constrói histórico da Taylor até possuir vintages historicamente alinhados dos insumos não observáveis.

Atualizações futuras de RPM ou de meta entram como novas versões, preservando a versão anterior.
