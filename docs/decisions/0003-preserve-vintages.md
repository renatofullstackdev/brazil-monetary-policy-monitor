# ADR 0003 — Preservar temporalidade e vintages desde o schema inicial

## Status

Aceito.

## Contexto

Séries econômicas podem ser revisadas. Avaliar uma decisão histórica com dados revisados posteriormente cria look-ahead bias e pode alterar a interpretação da política monetária.

## Decisão

O modelo distinguirá `reference_date`, `published_at` e `retrieved_at`. Quando a fonte oferecer revisões identificáveis, o banco deverá preservar informação suficiente para reconstruir `as_known` e `latest_revision`.

## Consequências

- unicidade de observações não pode assumir apenas série + data de referência;
- coletores precisam entender semântica temporal de cada fonte;
- armazenamento cresce, mas permanece pequeno para a escala do projeto;
- análises históricas ficam metodologicamente defensáveis.

## Alternativas consideradas

### Guardar somente o último valor

Rejeitada porque impede reconstrução fiel do conjunto informacional passado.

### Adicionar vintages apenas em fase posterior

Rejeitada porque exigiria retrofit do schema e perda de informação desde as primeiras coletas.
