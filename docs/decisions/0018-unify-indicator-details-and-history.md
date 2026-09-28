# ADR 0018 — Unificar detalhes e histórico dos indicadores

## Status

Aceito.

## Contexto

Até a Sprint 10, os cartões da visão geral e do contexto macroeconômico abriam metadados, enquanto crédito, fiscal e curva de juros tinham interações próprias. Isso criava três problemas:

1. conceitos igualmente importantes recebiam níveis diferentes de explicação;
2. novas sprints tenderiam a replicar componentes de popup, tabela e histórico;
3. séries historicamente disponíveis podiam ficar acessíveis apenas no gráfico do módulo, sem um caminho uniforme a partir do próprio cartão.

Também havia risco de criar históricos artificiais para parâmetros documentais pontuais, como taxa neutra, hiato e indicadores do RMD.

## Decisão

O frontend terá um único componente de detalhes de indicador, acionável a partir de cartões de qualquer módulo.

O componente mostra, quando disponíveis:

- definição e interpretação;
- valor e referência;
- natureza de proveniência;
- unidade e frequência;
- transformação;
- fonte e documentação;
- ressalvas metodológicas;
- dependências quando o indicador estiver indisponível.

O botão **Ver série histórica** só aparece quando o contrato ou o próprio módulo conseguem fornecer pelo menos duas observações válidas. O histórico usa os dados já publicados no navegador e não dispara consultas externas.

Parâmetros e snapshots documentais sem histórico compatível continuam sem gráfico. O frontend informa a ausência em vez de repetir o valor atual para datas passadas.

Os períodos padronizados são 1, 3, 5 e 10 anos, além de toda a série. A tabela do diálogo limita a renderização às observações recentes do período selecionado para evitar DOM excessivo em séries diárias longas.

## Consequências

- módulos futuros devem fornecer metadados suficientes para reutilizar o mesmo componente;
- histórico deixa de ser uma capacidade específica de cada seção;
- indicadores derivados podem expor história quando a transformação é reproduzível sobre observações históricas compatíveis;
- a existência de um valor corrente não implica automaticamente a existência de histórico;
- nenhum backend adicional nem biblioteca JavaScript é introduzido.
