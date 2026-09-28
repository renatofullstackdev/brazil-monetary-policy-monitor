# ADR 0024 — Separar pipelines por domínio e tornar a semântica temporal explícita

## Status

Aceito.

## Contexto

A implementação acumulou coleta, persistência e orquestração de múltiplos domínios em dois módulos centrais. Ao mesmo tempo, séries prospectivas como Focus precisam distinguir o período previsto da data da estimativa e da data em que a informação estava disponível. Uma única noção genérica de “data” não representa corretamente esse problema.

## Decisão

1. Não haverá `pipeline.py` nem `ingestion.py` monolíticos.
2. Pipelines e persistência de ingestão serão separados por domínio.
3. Utilidades transversais pequenas ficarão em módulos neutros, sem criar uma hierarquia abstrata de pipelines.
4. Observações manterão explicitamente três dimensões quando aplicáveis:
   - `reference_period`: período econômico ao qual o valor se refere;
   - `source_observation_at` / `as_of_date`: data da estimativa ou observação na fonte;
   - `available_at`: instante a partir do qual o monitor pode considerar a informação conhecida.
5. Consultas de estado mais recente e consultas de evolução de vintages serão operações distintas.
6. Junções entre séries de frequências diferentes usarão regra *as-of*: último valor disponível em ou antes da data de avaliação.
7. O frontend não decidirá regras econômicas de alinhamento nem preencherá campos semânticos por fallback silencioso.

## Consequências

Backfills de Focus, hiato e demais estimativas podem preservar o que era conhecido em cada momento sem apagar revisões sucessivas. Novos domínios entram em módulos próprios, e a ampliação histórica não aumenta novamente um ponto central de acoplamento. Há mais arquivos e contratos explícitos, mas menos ambiguidade temporal e menor risco de dependências circulares.
