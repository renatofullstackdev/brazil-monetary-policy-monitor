# Fontes de dados — inventário inicial

Este é um inventário de fontes candidatas, não uma lista de endpoints já homologados. Cada coletor deverá validar schema, unidade, frequência, política de revisão e condições de uso antes de ser incorporado.

## Banco Central do Brasil

### SGS / BCData

Uso esperado: Selic e diversas séries macrofinanceiras.

O catálogo de Dados Abertos do BCB expõe séries SGS com recursos JSON e CSV, código da série, unidade, periodicidade e metadados.

- Portal: https://dadosabertos.bcb.gov.br/

#### Série homologada na Sprint 2: SGS 432

- chave interna: `br.selic.target`;
- conceito oficial: taxa de juros que representa a meta definida pelo Copom para a taxa Selic;
- código SGS: `432`;
- frequência: diária;
- unidade original: `% a.a.`;
- início informado pelo catálogo: `1999-03-05`;
- recurso JSON: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados`;
- parâmetros usados: `dataInicial`, `dataFinal`, `formato=json`;
- licença indicada no catálogo: Open Data Commons Open Database License (ODbL).

O catálogo informa que, desde 26/03/2025, consultas JSON/CSV de séries históricas diárias exigem filtro por datas e cada intervalo está limitado a dez anos. Dez anos é tratado apenas como **limite máximo do contrato**, não como tamanho recomendado de requisição. Depois de uma consulta histórica de dez anos exceder o timeout em uso real, o coletor passou a usar janelas operacionais de um ano por padrão. O valor pode ser configurado entre 1 e 10 anos sem alterar a semântica dos dados.

O JSON da série fornece `data` e `valor`, mas não um timestamp histórico de publicação por observação. Consequentemente:

- `reference_period` vem de `data`;
- `published_at` fica `NULL`;
- `available_at` é a primeira coleta em que o monitor observou aquela versão do valor;
- uma mudança posterior de valor para a mesma data cria novo vintage;
- não alegamos reconstruir vintages anteriores ao início do nosso próprio monitoramento apenas a partir desse endpoint.

Decisão geral: outros códigos SGS só serão adicionados depois de conferência na fonte oficial. Não copiar listas de códigos de sites terceiros.

### Expectativas de Mercado / Focus

Uso esperado: inflação, Selic, PIB, câmbio e outras expectativas em diferentes horizontes.

Decisão: a API OData e sua semântica de datas/horizontes serão verificadas na Sprint 6 antes de criar contratos estáveis.

### Copom e Relatório de Política Monetária

Uso esperado:

- decisões;
- atas/comunicados;
- eventos de calendário;
- horizonte relevante;
- referências oficiais de hiato e taxa neutra quando publicadas.

Valores extraídos de documentos devem preservar publicação, referência e página/seção quando possível.

## IBGE / SIDRA

Uso esperado:

- IPCA e componentes;
- PNAD Contínua;
- Contas Nacionais;
- consumo das famílias;
- FBCF.

O IBGE oferece o SIDRA e interface de API. A modelagem deve preservar códigos de tabela, variável, classificação e unidade para auditoria.

- SIDRA: https://sidra.ibge.gov.br/
- API: https://apisidra.ibge.gov.br/

## Tesouro Nacional / Tesouro Transparente

### Taxas dos títulos ofertados pelo Tesouro Direto

Uso esperado: insumo oficial aberto para taxas de títulos públicos e construção de visualizações da estrutura a termo com as limitações documentadas.

O Tesouro informa que o conjunto é diário e que as taxas/preços refletem o mercado secundário dos títulos ofertados no Tesouro Direto.

- https://www.tesourotransparente.gov.br/temas/divida-publica-federal/tesouro-direto

Limitação: o conjunto de títulos ofertados não deve ser confundido automaticamente com uma curva soberana contínua completa. Interpolação e cobertura de maturidades precisam ser avaliadas.

### Relatório Mensal da Dívida

Uso esperado:

- composição da DPF;
- vencimentos;
- prazo médio;
- custo;
- reserva de liquidez.

Preferir tabelas/dados estruturados quando disponíveis; PDF deve ser último recurso para coleta recorrente.

## Estados Unidos

### Federal Reserve

Uso esperado:

- Federal Funds;
- decisões/eventos monetários;
- referências metodológicas sobre regras de política.

- https://www.federalreserve.gov/

### FRED / ALFRED — Federal Reserve Bank of St. Louis

Uso potencial: séries econômicas e, especialmente, suporte a real-time periods/vintages através de ALFRED.

- https://fred.stlouisfed.org/docs/api/fred/

A API tradicional exige chave. O projeto não deve incorporar segredo ao repositório; se FRED/ALFRED for adotado, a configuração será externa e haverá estratégia de desenvolvimento/teste sem segredo versionado.

### BEA / BLS / U.S. Treasury

Uso esperado conforme a série:

- produto/contas nacionais;
- inflação/trabalho;
- Treasury yields.

Sempre preferir o órgão produtor quando isso melhorar proveniência ou disponibilidade de vintage.

## Critérios de homologação de uma fonte

Antes de criar um coletor, registrar:

1. órgão produtor;
2. URL oficial;
3. identificador da série/conjunto;
4. unidade;
5. frequência;
6. timezone/data de referência;
7. política de revisão;
8. disponibilidade de histórico/vintage;
9. formato e schema;
10. licença/termos quando relevante;
11. limites operacionais;
12. transformação necessária.

## BCB Focus — monthly IPCA expectations

- Dataset: **Expectativas de Mercado** (`EXP`)
- Official catalog: <https://dadosabertos.bcb.gov.br/dataset/expectativas-mercado>
- OData entity set: `ExpectativaMercadoMensais`
- Indicator used: `IPCA`
- Client-side basis selection: retain `baseCalculo = 0` / `false`; discard `1` / `true`
- Fields retained: `Data`, `DataReferencia`, `Mediana`, `numeroRespondentes`, `baseCalculo`
- Retrieval strategy: bounded date windows (30 days by default), with no dependency on `$skip` or server-side ordering.
- `$top=10000` is a safety ceiling; if a window reaches the ceiling, ingestion fails and requires a smaller window rather than silently assuming completeness.
- Records are sorted and de-duplicated locally after validation.
- Local raw series: `br.focus.ipca.monthly_median`
- Derived series: `br.focus.ipca.policy_horizon`

`Data` is stored as `source_observation_at`, not automatically as `published_at`. The BCB catalog says the statistics are calculated daily and published on the first business day of the week, so a backfill must not invent historical public-availability timestamps.

The horizon-aligned series compounds the twelve monthly medians ending in the current source-backed Copom policy horizon. It is explicitly classified as `derived` rather than `survey`.

#### Focus OData query encoding

The Focus query string uses RFC 3986 encoding for OData expressions. In
particular, spaces inside `$filter` are encoded as `%20`, not `+`. Python's
default `urlencode()` behavior follows form encoding and represents spaces as
`+`; the active Olinda parser can interpret that character as an OData
operator and return misleading type errors such as `Edm.Boolean` versus
`Edm.String`.

`baseCalculo` is intentionally not filtered server-side. The collector accepts
both the historical integer representation (`0`/`1`) and boolean representation
(`false`/`true`) and retains only the current-expectation basis locally. This
keeps the economic selection independent from provider representation details.

## Séries domésticas homologadas na Sprint 7

A Sprint 7 reutiliza o coletor SGS já auditado e adiciona seis séries. Cada uma mantém código e documentação no metadata da própria série, embora compartilhem a fonte lógica `bcb.sgs`.

| Chave interna | SGS | Conceito | Frequência | Uso no painel |
| --- | ---: | --- | --- | --- |
| `br.ipca.monthly` | 433 | IPCA, variação mensal | mensal | acumulado 12 meses |
| `br.ipca.services.monthly` | 10844 | IPCA — serviços, variação mensal | mensal | acumulado 12 meses |
| `br.ipca.core.trimmed_unsmoothed.monthly` | 11426 | núcleo de médias aparadas sem suavização | mensal | acumulado 12 meses |
| `br.ibc_br.sa` | 24364 | IBC-Br com ajuste sazonal | mensal | variação m/m |
| `br.unemployment.pnadc` | 24369 | taxa de desocupação — PNAD Contínua | mensal | valor observado mais recente |
| `br.real_earnings.pnadc` | 24380 | rendimento médio real habitual — todos os trabalhos | mensal | valor observado mais recente |

A produção continua consultando diretamente `api.bcb.gov.br`; nenhum servidor MCP ou catálogo de terceiros é dependência do pipeline. Implementações externas podem ser usadas em desenvolvimento como referência cruzada, nunca como substituto silencioso da fonte oficial.

As seis séries desta etapa são mensais. O SGS pode devolver a mesma observação mensal quando duas consultas adjacentes cortam o mesmo mês, ainda que os intervalos de dias não se sobreponham. Por isso o pipeline macro normaliza o início de cada coleta para o primeiro dia do mês e cria chunks anuais em fronteiras mensais. Como defesa adicional, uma repetição entre chunks só é coalescida quando data e valor são idênticos; a mesma data com valores distintos continua sendo erro de ingestão. Essa tolerância não é aplicada à Selic diária.

### Parâmetros documentais

A Sprint 7 também registra, separadamente das séries SGS:

- `br.inflation.target`: meta contínua de 3,00%, Resolução CMN nº 5.141/2024;
- `br.neutral_real_rate.rpm`: 5,00%, RPM junho/2026, p. 65;
- `br.output_gap.rpm`: 0,4%, 2º trimestre de 2026, RPM junho/2026, p. 68.

Esses valores carregam URL, referência, período, metodologia, publicação e natureza (`observed` ou `estimated`). A sincronização é idempotente e não depende de scraping do PDF: os valores curados fazem parte do registro metodológico auditável e qualquer atualização exige nova versão explícita.

## Sprint 8 — Taxas dos Títulos Ofertados pelo Tesouro Direto

Fonte produtora: **Secretaria do Tesouro Nacional / Tesouro Transparente**.

Conjunto: `Taxas dos Títulos Ofertados pelo Tesouro Direto`.

Recurso CSV oficial:

`https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv`

O metadado oficial informa periodicidade diária, divulgação no primeiro dia útil após o fechamento do mercado secundário e possibilidade de revisão dos valores. O CSV contém tipo de título, vencimento, data-base, taxas de compra/venda e PUs.

A coleta salva o CSV completo recebido antes do parsing. Como o recurso é um arquivo histórico completo, e não uma API parametrizada por datas, o pipeline baixa o arquivo oficial inteiro em cada execução. Para limitar banco e payload da interface, a primeira ingestão normaliza por padrão apenas os últimos cinco anos de títulos relevantes; atualizações posteriores reprocessam uma sobreposição recente. O snapshot bruto, contudo, preserva exatamente o arquivo recebido.

Somente quatro famílias alimentam a proxy de curva:

- Tesouro Prefixado;
- Tesouro Prefixado com Juros Semestrais;
- Tesouro IPCA+;
- Tesouro IPCA+ com Juros Semestrais.

Tesouro Selic, Renda+ e Educa+ podem existir no arquivo, mas não entram nas curvas nominal/real desta metodologia.

A taxa selecionada é `Taxa Compra Manha`, descrita pela fonte como a taxa disponível para o investidor comprar o título. `Taxa Venda Manha` e PUs continuam preservados no SQLite para auditoria, mas não são usados no gráfico da Sprint 8.

Licença declarada pelo conjunto: **Open Data Commons Open Database License (ODbL)**.


## Séries de crédito homologadas na Sprint 9

A Sprint 9 reutiliza o mesmo coletor SGS auditado para seis séries mensais do Departamento de Estatísticas do BCB. Os saldos representam estoque em fim de período; as taxas são médias das **novas operações**; inadimplência corresponde à parcela da carteira com pelo menos uma prestação em atraso superior a 90 dias.

| Chave interna | SGS | Conceito | Unidade | Uso |
| --- | ---: | --- | --- | --- |
| `br.credit.free.balance` | 20542 | saldo da carteira com recursos livres — total | R$ milhões | crescimento real 12m |
| `br.credit.directed.balance` | 20593 | saldo da carteira com recursos direcionados — total | R$ milhões | crescimento real 12m |
| `br.credit.free.interest_rate` | 20717 | taxa média de juros — recursos livres — total | % a.a. | observado |
| `br.credit.directed.interest_rate` | 20756 | taxa média de juros — recursos direcionados — total | % a.a. | observado |
| `br.credit.free.delinquency` | 21085 | inadimplência — recursos livres — total | % | observado |
| `br.credit.directed.delinquency` | 21132 | inadimplência — recursos direcionados — total | % | observado |

Catálogo oficial:

- https://dadosabertos.bcb.gov.br/dataset/20542-saldo-da-carteira-de-credito-com-recursos-livres---total
- https://dadosabertos.bcb.gov.br/dataset/20593-saldo-da-carteira-de-credito-com-recursos-direcionados---total
- https://dadosabertos.bcb.gov.br/dataset/20717-taxa-media-de-juros-das-operacoes-de-credito-com-recursos-livres---total
- https://dadosabertos.bcb.gov.br/dataset/20756-taxa-media-de-juros-das-operacoes-de-credito-com-recursos-direcionados---total
- https://dadosabertos.bcb.gov.br/dataset/21085-inadimplencia-da-carteira-de-credito-com-recursos-livres---total
- https://dadosabertos.bcb.gov.br/dataset/21132-inadimplencia-da-carteira-de-credito-com-recursos-direcionados---total

Como todas são mensais, `update-credit` aplica a mesma defesa já aprendida na Sprint 7: início alinhado ao primeiro dia do mês, chunks anuais e coalescência apenas de repetições idênticas entre chunks. `404 Value(s) not found` continua significando janela vazia somente quando o corpo do próprio SGS confirma essa condição.

Nenhum índice composto de condições financeiras foi homologado nesta sprint. A ausência é intencional: um índice próprio exigiria escolhas de padronização, pesos, sinal e janela que poderiam parecer objetivas sem uma fonte ou metodologia institucional defensável.
