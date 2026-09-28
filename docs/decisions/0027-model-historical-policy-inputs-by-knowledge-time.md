# ADR 0027 — Modelar insumos históricos de política pelo tempo de conhecimento

## Status

Aceito no Sprint 18.

## Contexto

A Taylor prospectiva histórica precisa distinguir o período econômico descrito pela informação do momento em que essa informação poderia ter sido conhecida. Tratar meta, taxa neutra, hiato e Focus como snapshots correntes produziria retropropagação de revisões e parâmetros futuros.

## Decisão

- Meta de inflação é persistida como regime documental em `parameters`, com intervalo de aplicabilidade (`effective_from`/`effective_to`) e fronteira de publicação (`available_at`).
- A hipótese de taxa real neutra do Copom permanece em `parameters`, em degraus documentais. Não é tratada como série observada.
- O hiato do produto passa para `observations`, porque é uma estimativa trimestral revisável. Cada RI/RPM gera um vintage imutável com `reference_period`, `source_revision` e `available_at` próprios.
- O horizonte relevante de política monetária usa um catálogo documental explícito. Uma mudança só passa a valer para reconstruções quando a ata que a documenta foi publicada.
- A data `Data` do Focus continua sendo `source_observation_at`, não `available_at`. Como o endpoint histórico não fornece o timestamp da publicação, o backfill usa uma fronteira conservadora de sete dias corridos após a data da estatística, antecipada apenas quando `first_seen_at` prova disponibilidade anterior.
- A seleção da meta para uma expectativa futura usa simultaneamente `knowledge_cutoff` e a data de referência do horizonte; uma meta anunciada para o futuro pode ser conhecida hoje sem estar vigente hoje.

## Consequências

- Reconstruções `as known at the time` podem fazer *as-of joins* sem incorporar informação futura.
- Revisões do hiato não apagam o valor que estava disponível em vintages anteriores.
- O histórico Focus passa a representar a evolução da expectativa para um mesmo horizonte, em vez de colapsar todas as datas da pesquisa em um único ponto.
- A disponibilidade histórica do Focus é deliberadamente conservadora enquanto não houver uma fonte oficial com timestamp histórico de cada divulgação.
- As séries derivadas históricas de postura monetária ficaram fora deste sprint e foram implementadas no Sprint 19 conforme o ADR 0028.
