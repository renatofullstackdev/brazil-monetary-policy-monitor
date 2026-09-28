# ADR 0021 — Preservar revisões imutáveis de eventos de política monetária

## Decisão

Manter `events` como identidade estável e persistir cada representação conhecida em `event_revisions`, com `available_at`, `retrieved_at`, `last_seen_at` e `content_hash`.

## Contexto

Eventos não são necessariamente imutáveis do ponto de vista do monitor. Uma agenda futura muda de `scheduled` para `fulfilled`; metadados podem ser corrigidos; links podem ser enriquecidos depois. Sobrescrever a linha atual e conservar apenas a primeira disponibilidade faria um corte histórico enxergar informação que ainda não existia naquela data.

## Consequências

- `as_known` escolhe a revisão do evento disponível no cutoff;
- primeira representação pode usar data oficial de publicação quando defensável;
- alteração observada depois só fica disponível a partir da nova observação;
- calendário programado e documento publicado usam identidades distintas quando representam fatos diferentes;
- há pequeno aumento de armazenamento, aceitável porque eventos têm cardinalidade muito menor que séries diárias.
