# ADR 0004 — Proveniência e natureza epistemológica explícitas

## Status

Aceito.

## Contexto

O painel mistura observações, pesquisas de expectativas, estimativas não observáveis, cálculos derivados e simulações. Exibi-los sem distinção favorece interpretações incorretas.

## Decisão

Toda série/indicador deve declarar uma das categorias iniciais:

- `observed`;
- `survey`;
- `estimated`;
- `derived`;
- `simulated`.

Metadados de fonte e transformação serão acessíveis na interface.

## Consequências

- taxa neutra e hiato nunca aparecerão como fatos observados;
- Taylor será claramente um cálculo;
- alterações do usuário serão isoladas como simulação;
- componentes de UI precisam carregar metadados, não apenas valores.

## Alternativas consideradas

### Mostrar apenas a fonte textual

Insuficiente, pois fonte oficial não transforma uma estimativa publicada pelo órgão em observação direta.
