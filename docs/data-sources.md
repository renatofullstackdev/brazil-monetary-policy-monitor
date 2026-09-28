# Fontes de dados — inventário inicial

Este é um inventário de fontes candidatas, não uma lista de endpoints já homologados. Cada coletor deverá validar schema, unidade, frequência, política de revisão e condições de uso antes de ser incorporado.

## Banco Central do Brasil

### SGS / BCData

Uso esperado: Selic e diversas séries macrofinanceiras.

O catálogo de Dados Abertos do BCB expõe séries SGS com recursos JSON e CSV, código da série, unidade, periodicidade e metadados.

- Portal: https://dadosabertos.bcb.gov.br/

#### Série homologada: SGS 432

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

O JSON da série fornece `data` e `valor`, mas não um timestamp histórico de publicação por observação. Para a SGS 432 há uma distinção semântica importante: o valor descreve a meta Selic que estava publicamente em vigor na data de referência. Consequentemente:

- `reference_period` vem de `data`;
- `published_at` fica `NULL`;
- a primeira versão local de uma data histórica recebe `available_at` no fim do próprio dia de referência, sem ultrapassar `first_seen_at`;
- uma mudança posterior de valor para a mesma data cria novo vintage e só fica disponível a partir de `first_seen_at`;
- revisões posteriores nunca são retrodatadas;
- essa regra é específica da meta Selic e não é aplicada automaticamente às demais séries SGS.

Decisão geral: outros códigos SGS só serão adicionados depois de conferência na fonte oficial. Não copiar listas de códigos de sites terceiros.

### Expectativas de Mercado / Focus

Uso atual: medianas mensais do IPCA e composição de doze meses no horizonte relevante do Copom.

A API OData fornece `Data` como data da estatística. O catálogo do BCB informa cálculo diário e divulgação semanal das estatísticas, mas o endpoint histórico não fornece o timestamp exato de cada publicação. O monitor mantém `Data` como `source_observation_at` e usa uma fronteira conservadora de sete dias para `available_at`, antecipada somente quando `first_seen_at` comprova disponibilidade anterior.

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

## Séries domésticas homologadas no contexto macroeconômico doméstico

A camada macroeconômica doméstica reutiliza o coletor SGS já auditado e adiciona seis séries. Cada uma mantém código e documentação no metadata da própria série, embora compartilhem a fonte lógica `bcb.sgs`.

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

A camada monetária histórica registra, separadamente das séries SGS:

- `br.inflation.target`: regimes oficiais dos centros das metas anuais desde 1999 e meta contínua de 3,00% desde 2025;
- `br.neutral_real_rate.rpm`: hipóteses documentais do Copom em degraus, com cobertura curada desde fevereiro de 2023;
- `br.output_gap.copom`: vintages trimestrais revisáveis extraídos dos RI/RPM, com cobertura curada de setembro de 2024 a setembro de 2026.

Meta e taxa neutra são `parameters`, pois representam regimes/hipóteses documentais. O hiato é uma série `estimated` em `observations`, porque um mesmo trimestre pode ser revisado em relatórios posteriores. A sincronização é idempotente e preserva URL, referência, data de publicação e vintage.

## Séries de crédito homologadas na camada de crédito e transmissão monetária

A camada de crédito e transmissão monetária reutiliza o mesmo coletor SGS auditado para seis séries mensais do Departamento de Estatísticas do BCB. Os saldos representam estoque em fim de período; as taxas são médias das **novas operações**; inadimplência corresponde à parcela da carteira com pelo menos uma prestação em atraso superior a 90 dias.

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

Como todas são mensais, `update-credit` aplica a mesma defesa já aprendida no contexto macroeconômico doméstico: início alinhado ao primeiro dia do mês, chunks anuais e coalescência apenas de repetições idênticas entre chunks. `404 Value(s) not found` continua significando janela vazia somente quando o corpo do próprio SGS confirma essa condição.

Nenhum índice composto de condições financeiras foi homologado na implementação atual. A ausência é intencional: um índice próprio exigiria escolhas de padronização, pesos, sinal e janela que poderiam parecer objetivas sem uma fonte ou metodologia institucional defensável.


## Fiscal — séries homologadas na camada fiscal

### BCB / SGS

Seis séries mensais são usadas diretamente, sem alteração de sinal:

| Chave interna | SGS | Conceito | Unidade normalizada |
| --- | ---: | --- | --- |
| `br.fiscal.primary_result_12m_gdp` | 5793 | NFSP, resultado primário, setor público consolidado, acumulado em 12 meses | `% do PIB` |
| `br.fiscal.nominal_interest_12m_gdp` | 5760 | NFSP, juros nominais, setor público consolidado, acumulado em 12 meses | `% do PIB` |
| `br.fiscal.nominal_result_12m_gdp` | 5727 | NFSP, resultado nominal, setor público consolidado, acumulado em 12 meses | `% do PIB` |
| `br.fiscal.dbgg_gdp` | 13762 | Dívida Bruta do Governo Geral, metodologia a partir de 2008 | `% do PIB` |
| `br.fiscal.dlgg_gdp` | 4536 | Dívida Líquida do Governo Geral | `% do PIB` |
| `br.fiscal.dlsp_gdp` | 4513 | Dívida Líquida do Setor Público, total, setor público consolidado | `% do PIB` |

Nas NFSP, a convenção oficial de financiamento é preservada: positivo representa déficit/necessidade de financiamento; negativo, superávit. O monitor não inverte o sinal para produzir uma convenção visual própria.

### Tesouro Nacional / RMD

O Relatório Mensal da Dívida é a fonte do perfil da Dívida Pública Federal. Na camada fiscal, o snapshot homologado é julho de 2026, publicado em 26/08/2026, e preserva os valores reportados para estoque, composição por indexador, vencimentos em 12 meses, prazo médio, custo médio em 12 meses, reserva de liquidez e índice de liquidez.

Esses valores são mantidos como registros documentais versionados em `parameters`. O monitor **não** estima prazo médio, custo ou liquidez a partir de vencimentos finais ou de uma base de estoque simplificada, porque isso substituiria a metodologia oficial por uma aproximação não equivalente.

A cobertura também permanece explícita: DBGG e DLGG referem-se ao Governo Geral, mas a primeira mede o estoque bruto e a segunda balanceia débitos e créditos. A DLSP tem perímetro mais amplo, abrangendo o setor público não financeiro e o Banco Central, e é a base da apuração fiscal "abaixo da linha". A DPF, por sua vez, é a dívida federal administrada pelo Tesouro. Esses conceitos não são combinados em uma única série.

## Setor externo e câmbio — séries homologadas na camada de setor externo e câmbio

Todas as séries desta camada vêm do BCB/SGS. O monitor mantém frequência, unidade e significado estatístico explícitos; não transforma preço, fluxo e estoque em um indicador único.

| Chave interna | SGS | Conceito | Frequência | Unidade normalizada |
| --- | ---: | --- | --- | --- |
| `br.fx.usd_brl.sell` | 1 | taxa de câmbio livre, dólar americano, venda | diária | `R$/US$` |
| `br.fx.reer_ipca` | 11752 | índice da taxa de câmbio real efetiva baseada em IPCA | mensal | índice |
| `br.external.current_account_12m_gdp` | 23079 | transações correntes acumuladas em 12 meses / PIB | mensal | `% do PIB` |
| `br.external.idp_12m_gdp` | 23080 | investimento direto no país acumulado em 12 meses / PIB | mensal | `% do PIB` |
| `br.external.portfolio_liabilities_net` | 22924 | investimentos em carteira, passivos, mensal, líquido | mensal | US$ milhões |
| `br.external.reserves_liquidity` | 13982 | reservas internacionais, conceito liquidez, total | diária | US$ milhões |

### USD/BRL e séries diárias

A série 1 é a cotação diária de venda USD/BRL. A série 13982 mede o estoque diário de reservas internacionais no conceito liquidez. Desde 26/03/2025, o BCB exige filtros de data para séries diárias em JSON/CSV e limita cada consulta a no máximo dez anos; o pipeline usa janelas menores por padrão e preserva cada payload bruto.

As variações de 30 e 365 dias do USD/BRL são `derived`: cada observação corrente é comparada à última observação disponível em ou antes da data-alvo. Valor positivo significa mais reais por dólar em relação à comparação; o monitor não interpreta automaticamente a causa.

### Câmbio real efetivo

A série 11752 é preservada como índice observado. Ela combina câmbio nominal e preços relativos com ponderação externa. O painel não converte seu nível em uma estimativa de “câmbio justo”, equilíbrio ou desalinhamento.

### Conta externa e fluxos financeiros

A série 23079 agrega bens, serviços, renda primária e renda secundária em transações correntes e expressa o saldo acumulado em doze meses como percentual do PIB. Valor negativo é déficit; positivo, superávit.

A série 23080 expressa o IDP acumulado em doze meses como percentual do PIB. O monitor também calcula, apenas quando a conta corrente é deficitária, `IDP_12m_PIB / abs(conta_corrente_12m_PIB) * 100`. Essa razão é uma comparação descritiva de escala: não é identidade de financiamento e não demonstra que um fluxo específico financiou outro.

A série 22924 representa passivos líquidos de investimento em carteira no balanço de pagamentos. Ela não é confundida com IDP nem rotulada como “todo o fluxo estrangeiro”. O sinal é preservado conforme a convenção estatística da fonte.

### Reservas internacionais

A série 13982 usa o conceito liquidez do BCB: ativos externos prontamente disponíveis e controlados pelo Banco Central, incluindo determinadas operações de linhas com recompra e empréstimos em moeda estrangeira. É um **estoque**, não um fluxo cambial.

### Diferenciais Brasil–Estados Unidos

Não são calculados na camada de setor externo e câmbio. Eles pertencem ao módulo de benchmarks dos Estados Unidos, que possui contratos próprios de fonte, frequência e transformação.

## Benchmarks dos Estados Unidos

The US module uses the keyless FRED graph-CSV transport while preserving the original source identity documented by FRED.

| Monitor key | FRED | Underlying source | Frequency | Meaning |
| --- | --- | --- | --- | --- |
| `us.policy.effr` | DFF | Federal Reserve Board / H.15 | daily | Effective federal funds rate |
| `us.treasury.2y` | DGS2 | Federal Reserve Board / H.15 | daily | 2-year constant-maturity Treasury yield |
| `us.treasury.10y` | DGS10 | Federal Reserve Board / H.15 | daily | 10-year constant-maturity Treasury yield |
| `us.treasury.real_10y` | DFII10 | Federal Reserve Board / H.15 | daily | 10-year inflation-indexed Treasury yield |
| `us.inflation.breakeven_10y` | T10YIE | Federal Reserve Bank of St. Louis | daily | 10-year breakeven inflation measure |
| `us.inflation.pce_index` | PCEPI | Bureau of Economic Analysis | monthly | PCE price index |
| `us.gdp.real` | GDPC1 | Bureau of Economic Analysis | quarterly | Real GDP |
| `us.gdp.potential` | GDPPOT | Congressional Budget Office | quarterly | Estimated real potential GDP |

No LLM API key and no FRED API key are required by `update-us.sh`. Raw CSV responses are retained under `data/raw/fred/`.

## Cobertura de vintages por fonte

`as_known` does not imply that every provider has a complete real-time archive. The publication layer uses the strongest chronology already persisted by each collector and never substitutes `reference_period` for a missing availability date.

- BCB/SGS and other backfilled series without authoritative per-observation publication timestamps accumulate revisions locally from the first monitor observation onward.
- Focus preserves the provider statistic date separately as `source_observation_at`; historical `available_at` uses the conservative weekly-publication boundary documented in the Sprint 18 temporal model, never the statistic date itself.
- FRED/BEA/CBO series collected through the keyless graph CSV accumulate local revisions only. The official FRED/ALFRED real-time/vintage web-service endpoints require an API key, so A camada de vintages does not silently add that operational dependency.

The vintage UI therefore describes its historical mode as **local defensible vintages**, not as a guarantee of complete provider-native real-time history.

## Documentos do Copom e Relatórios de Política Monetária

Fonte produtora: **Banco Central do Brasil**.

Conjunto oficial de atas e comunicados:

`https://dadosabertos.bcb.gov.br/dataset/atas-comunicados-copom`

Endpoints utilizados:

- `https://www.bcb.gov.br/api/servico/sitebcb/copom/comunicados?quantidade=N`;
- `https://www.bcb.gov.br/api/servico/sitebcb/copom/comunicados_detalhes?nro_reuniao=N`;
- `https://www.bcb.gov.br/api/servico/sitebcb/copom/atas?quantidade=N`;
- `https://www.bcb.gov.br/api/servico/sitebcb/copom/atas_detalhes?nro_reuniao=N`.

O catálogo do BCB documenta que a decisão é comunicada no próprio dia da reunião e que a ata é publicada posteriormente. Por isso, o comunicado usa a data da decisão como disponibilidade oficial em resolução diária, enquanto a ata usa `dataPublicacao`. O monitor não inventa horário histórico intradiário; internamente, datas oficiais sem horário recebem um marcador estável dentro do dia e os bundles `as_known` operam por corte de fim de dia.

Conjunto oficial de RPM:

`https://dadosabertos.bcb.gov.br/dataset/relatorios-de-politica-monetaria-publicados`

Endpoints utilizados:

- `https://www.bcb.gov.br/api/servico/sitebcb/rpm/relatorios?quantidade=N` para relatórios efetivamente publicados;
- `https://www.bcb.gov.br/api/servico/sitebcb/rpm/proximos-relatorios?inicioAgenda=YYYY-MM-DD` para o calendário de divulgação.

`rpm_release` e `rpm_schedule` são eventos distintos. Um item de calendário nunca é convertido em publicação apenas porque a data passou. Quando uma agenda previamente observada é cumprida, o estado da agenda ganha uma nova revisão disponível somente a partir da observação dessa mudança; o relatório publicado é persistido como evento próprio com sua data oficial.

As reuniões futuras de 2027 são registradas a partir do **Comunicado BCB nº 45.452, de 23/06/2026**, que formalizou o calendário anual. Datas futuras de 2026 visíveis no calendário do Copom sem timestamp histórico de anúncio são conservadoras: tornam-se conhecidas apenas na primeira observação local.

Licença dos conjuntos no Portal de Dados Abertos do BCB: **Open Data Commons Open Database License (ODbL)**.

## Curvas de mercado — implementação provisória ANBIMA ETTJ e B3 DI1

### ANBIMA — Estrutura a Termo das Taxas de Juros

- chave interna da fonte: `anbima.ettj`;
- página pública: `https://www.anbima.com.br/informacoes/est-termo/CZ.asp`;
- download legado usado pelo coletor: `https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp`;
- formato: CSV separado por `;`;
- dimensões persistidas: data de referência, vértice em dias úteis e taxa;
- curvas: prefixada (`anbima.pre`), real IPCA (`anbima.ipca`) e inflação implícita (`anbima.breakeven`);
- metodologia: ETTJ ANBIMA/Svensson, sem reestimação pelo monitor.

No CSV, vértices acima de 999 dias úteis usam ponto como separador de milhar (`1.008`, `2.520`). O parser os interpreta como 1008 e 2520 DU; tratá-los como números decimais truncaria silenciosamente a curva em 882 DU.

A página legada expõe apenas uma janela recente curta. O coletor não atribui datas antigas a valores recém-observados: `available_at` continua sendo a data de coleta local. Um backfill histórico só deve ser adicionado após homologação de uma fonte que exponha explicitamente esse histórico.

### B3 — BVBG.187.01 / DI1

- chave interna da fonte: `b3.di1`;
- relatório: **Simplified Price Report - Derivatives (BVBG.187.01)**;
- arquivo diário público: `SPRDyymmdd.zip`;
- instrumento selecionado: ticker iniciado por `DI1`;
- campos usados: `TradDt/Dt`, `TckrSymb`, `AdjstdQt` e `AdjstdQtTax`;
- formato recebido: ZIP contendo XML;
- transformação: recuperação de `DU` pela identidade preço/taxa do DI1 e cálculo de forwards entre contratos adjacentes em base 252 dias úteis.

O transporte B3 fica confinado ao coletor. Mudanças futuras no mecanismo de download não devem alterar persistência, modelos, contrato do frontend ou cálculo de forwards.
