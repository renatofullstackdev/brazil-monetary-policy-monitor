# ADR 0013 — Modelar o Tesouro Direto como proxy de yields ofertados, não como curva zero-cupom

## Contexto

O conjunto oficial **Taxas dos Títulos Ofertados pelo Tesouro Direto** publica diariamente taxas e preços dos títulos ofertados e declara que esses valores refletem o mercado secundário. Ele contém vencimentos discretos e diferentes estruturas de cupom.

Transformar diretamente esses pontos em uma "curva soberana contínua" esconderia hipóteses importantes. Um ajuste Nelson-Siegel/Svensson, bootstrap zero-cupom ou extrapolação exigiria escolhas adicionais de instrumento, convenção, ponderação e tratamento de cupom que ainda não foram homologadas.

## Decisão

A Sprint 8 publica uma **proxy da estrutura a termo dos títulos ofertados**:

- taxa usada: `Taxa Compra Manha`;
- curva nominal: Tesouro Prefixado e Tesouro Prefixado com Juros Semestrais;
- curva real: Tesouro IPCA+ e Tesouro IPCA+ com Juros Semestrais;
- prazo: dias entre `Data Base` e `Data Vencimento`, dividido por 365,2425;
- vértices constantes: 2, 3, 5, 7 e 10 anos;
- interpolação: linear somente quando o prazo está entre dois vencimentos observados;
- extrapolação: proibida;
- inflação implícita: relação de Fisher exata entre taxas nominal e real interpoladas no mesmo prazo.

A inflação implícita é rotulada como **proxy de mercado**, não como expectativa pura. Diferenças entre instrumentos, risco, liquidez, convexidade e outros prêmios podem afetar o spread nominal-real.

## Consequências

O monitor ganha comparação temporal auditável sem apresentar um modelo de curva mais sofisticado do que a fonte suporta diretamente. Alguns vértices, especialmente 2 anos, podem ficar indisponíveis quando não houver vencimentos dos dois lados do prazo. Essa ausência é preferível à extrapolação silenciosa.

Um modelo zero-cupom poderá ser acrescentado posteriormente como transformação separada, com metodologia e testes próprios, sem redefinir os dados brutos desta sprint.
