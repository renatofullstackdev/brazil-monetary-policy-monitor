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
