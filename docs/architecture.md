# Arquitetura da V1

## 1. Objetivo arquitetural

Manter o sistema pequeno, reproduzível e auditável. A interface precisa continuar disponível mesmo quando BCB, IBGE, Tesouro ou fontes americanas estiverem temporariamente indisponíveis.

A consequência principal é separar **aquisição e preparação** de **visualização**.

```text
┌─────────────────────────────────────────────────────────────┐
│ Fontes oficiais                                             │
│ BCB | IBGE | Tesouro | Federal Reserve | BEA | BLS         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Coleta Python                                               │
│ HTTP -> validação -> snapshot bruto -> parsing              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Normalização                                                │
│ unidades | frequências | datas | proveniência | vintages   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ SQLite                                                      │
│ séries | observações | parâmetros | eventos | ingestões     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Publicação                                                  │
│ JSON estático validado + substituição atômica               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Frontend estático                                           │
│ HTML | CSS | JavaScript | SVG nativo                     │
└─────────────────────────────────────────────────────────────┘
```

## 2. Por que não consultar provedores diretamente no navegador

Consultas diretas fariam a disponibilidade do painel depender de várias APIs externas e espalhariam pelo frontend regras de parsing, revisão histórica e conversão de unidades. Isso também dificulta reproduzir o que estava disponível em determinada data.

O navegador deve consumir poucos contratos JSON controlados pelo projeto.

## 3. Por que SQLite

O workload previsto na V1 é de um único processo de atualização, séries macroeconômicas de baixa frequência e leitura publicada como arquivos estáticos. SQLite oferece:

- transações ACID;
- implantação sem serviço adicional;
- backup simples;
- consultas SQL suficientes para séries temporais e vintages;
- caminho de migração para PostgreSQL se concorrência de escrita ou API pública justificarem.

SQLite não será acessado pelo navegador.

## 4. Snapshots brutos

Quando tecnicamente razoável, cada coleta persistirá a resposta original ou um artefato equivalente, acompanhado por metadados e checksum. O objetivo é permitir auditoria de transformações sem depender de o provedor continuar oferecendo exatamente a mesma resposta.

Snapshots não devem ser versionados indiscriminadamente no Git. A política concreta de retenção será definida quando os primeiros coletores forem implementados.

## 5. Temporalidade e vintages

Uma observação pode possuir pelo menos três tempos semanticamente distintos:

- `reference_date`: período econômico a que o valor se refere;
- `published_at`: quando o provedor o tornou público;
- `retrieved_at`: quando nosso pipeline o coletou.

Quando o provedor expuser revisões ou versões, elas devem ser preservadas de forma suficiente para distinguir:

- **latest_revision**: conhecimento atual sobre o passado;
- **as_known**: informação disponível na data escolhida.

A implementação não deve assumir que todas as fontes possuem a mesma semântica de vintage.

## 6. Proveniência

Cada série e cada derivação devem permitir responder:

- qual é a fonte;
- qual o identificador original;
- qual a unidade original;
- qual a unidade normalizada;
- qual a frequência;
- qual transformação foi aplicada;
- qual a classificação epistemológica;
- qual a documentação metodológica relevante.

Classificações iniciais:

- `observed`;
- `survey`;
- `estimated`;
- `derived`;
- `simulated`.

## 7. Separação entre modelo e contexto

A Taylor não absorverá arbitrariamente câmbio, fiscal, crédito ou diferencial externo.

O núcleo do cálculo permanece explícito. Os demais módulos explicam canais de transmissão, condições financeiras, choques e possíveis razões para divergência entre regra simples e política observada.

Essa separação evita transformar o painel em uma regressão opaca calibrada para reproduzir decisões históricas.

## 8. Frontend

A V1 é uma aplicação estática, sem framework JavaScript. O estado permanece pequeno e explícito: data, vintage, país, intervalo temporal e, a partir da Sprint 5, parâmetros da simulação.

Na Sprint 4, o único gráfico histórico é implementado em SVG nativo. Isso evita introduzir uma biblioteca completa para uma única série simples e mantém o site sem dependência de runtime externa. Não será construído um framework gráfico próprio: a escolha será reavaliada quando a Sprint 8 introduzir curvas de juros e requisitos mais complexos de interação. Ver ADR 0009.

A tela consome exclusivamente `web/data/overview.json`, publicado a partir do SQLite. Séries ainda não incorporadas possuem estado explícito `unavailable`; o frontend não preenche lacunas com fixtures ou aproximações.

## 9. Operação

Quando o pipeline existir:

- atualização via `systemd service` + `systemd timer`;
- logs estruturados;
- registro de cada execução em `ingestion_runs`;
- validação antes da publicação;
- publicação atômica dos JSONs;
- falha de uma fonte não apaga dados válidos anteriores.

## 10. Critérios que justificariam evoluir a arquitetura

PostgreSQL ou uma API de aplicação só devem ser considerados se aparecer pelo menos um problema concreto como:

- múltiplos escritores concorrentes;
- consultas públicas arbitrárias;
- usuários/autenticação;
- volume ou latência incompatíveis com publicação estática;
- necessidade de atualizações transacionais remotas.

Framework frontend só deve ser considerado se a complexidade real de estado/componentização superar o custo adicional.


## 11. Persistência implementada na Sprint 1

O schema é versionado por migrations SQL sequenciais. Observações revisáveis são imutáveis por vintage: uma revisão nova não substitui a anterior. Consultas históricas usam `available_at` como fronteira de conhecimento, conforme ADR 0006.

O módulo `brazil_monetary_policy_monitor.db` usa apenas `sqlite3` da biblioteca padrão. Foreign keys são habilitadas em toda conexão aberta pelo projeto e as migrations são idempotentes.

## 12. Pipeline implementado na Sprint 2

A primeira implementação real usa BCB SGS 432 e estabelece o contrato operacional para novos coletores:

```text
HTTP oficial
  -> snapshot dos bytes recebidos
  -> validação integral
  -> normalização
  -> transação SQLite
  -> JSON temporário
  -> os.replace() para publicação atômica
```

Cada `ingestion_run` recebe um diretório de snapshot com payloads por janela, URL consultada, tamanho e SHA-256. Uma resposta recebida é preservada antes do parsing, inclusive quando seu conteúdo é inválido. Isso permite investigar mudanças de schema ou respostas anômalas.

A primeira carga da SGS 432 parte de 05/03/1999. Embora o provedor permita até dez anos por consulta, o pipeline usa janelas de um ano por padrão: o máximo aceito pelo contrato não é confundido com um tamanho operacional robusto, e janelas menores reduzem o trabalho por requisição quando o SGS está lento. Timeout, retries, backoff e tamanho de janela são parâmetros da CLI. Depois da carga inicial, a execução padrão consulta novamente uma pequena sobreposição de sete dias a partir do último período armazenado. O objetivo é detectar mudanças recentes sem baixar todo o histórico diariamente. Alterações de valor são novas revisões; valores idênticos apenas atualizam `last_seen_at`.

O endpoint SGS usado não oferece `published_at` histórico por linha. `available_at` registra a primeira observação pelo monitor, não uma data de publicação inferida. Essa limitação é deliberadamente preservada para não fabricar vintages retroativos.

Falhas antes da persistência deixam a execução como `failed`. Falhas posteriores à persistência usam `partial`. Em ambos os casos, um JSON previamente válido não é apagado. Ver ADR 0007.

## 13. Visão geral implementada na Sprint 4

O publicador da visão geral transforma o banco normalizado em um contrato estático versionado. A Selic já aparece como dado observado; Taylor prospectiva, juro real, gap monetário e suas premissas permanecem indisponíveis até que suas fontes oficiais sejam implementadas.

A interface oferece:

- cards centrais com classificação epistemológica;
- metadados por indicador em diálogo acessível;
- histórico com filtros de 1, 3, 5 e 10 anos ou série completa;
- tabela textual das observações recentes;
- erro explícito quando o JSON ainda não foi publicado;
- layout responsivo sem consulta direta a provedores externos.

O contrato está documentado em `docs/frontend-contract.md`.

## 14. Simulador local implementado na Sprint 5

A simulação permanece inteiramente no frontend. Os quatro parâmetros principais são inicializados a partir de valores publicados quando disponíveis; ausências permanecem vazias. O resultado não é enviado ao pipeline nem persistido no navegador ou no SQLite.

A fórmula canônica é espelhada em um módulo JavaScript puro para resposta imediata aos controles. A implementação Python permanece como referência e pode ser comparada automaticamente com o módulo do navegador quando Node.js estiver disponível no ambiente de teste. Ver ADR 0010.

### Focus ingestion and horizon alignment

Sprint 6 adds a second BCB ingestion path using the Focus OData service. It stores monthly IPCA medians as immutable vintages and derives a separate policy-horizon series. The raw survey and the derived horizon value remain separate series so downstream models cannot silently confuse source data with transformation output.

`source_observation_at` was added to the observation model because provider chronology and public availability are different concepts. This also provides a deterministic provider-revision ordering when historical rows are first ingested in one backfill run.

### Focus OData boundary

The Focus collector deliberately avoids `$skip` pagination and `$orderby`. The Olinda resource is queried through bounded date windows, then validated and sorted locally. A response that reaches the configured row ceiling is treated as potentially truncated and is not persisted. This keeps completeness under the monitor's control instead of depending on provider pagination behavior.

## 15. Contexto macro e parâmetros documentais da Sprint 7

O coletor SGS tornou-se reutilizável por especificação de série. `update-macro` executa um `ingestion_run` independente para cada código, preserva snapshots brutos separados e só republica `overview.json` depois que todas as séries solicitadas terminam com sucesso. Uma falha intermediária pode deixar séries já persistidas no banco, com seus próprios registros de auditoria, mas não substitui a última visão geral coerente.

Os parâmetros de meta, taxa neutra e hiato seguem outro caminho:

```text
publicação oficial
  -> registro curado com referência exata
  -> parameters (versionado)
  -> publicador da visão geral
```

Isso impede que estimativas documentais sejam disfarçadas de observações de alta frequência. Também permite selecionar o último parâmetro que já estava disponível **e** efetivo na data de conhecimento.

O publicador deriva IPCA/núcleo/serviços em 12 meses e IBC-Br m/m sem alterar as observações brutas. Taylor, Selic−Taylor e gap real são calculados somente na publicação. Nesta etapa, a Taylor tem apenas valor corrente; `observations` permanece vazio até que seja possível reconstruir seus insumos historicamente sem look-ahead.

## Curva de juros na Sprint 8

A curva do Tesouro Direto possui persistência própria em `yield_curve_quotes`, porque uma data contém várias combinações de tipo de título e vencimento e não se encaixa naturalmente na tabela escalar `observations`.

O fluxo é:

```text
CSV histórico oficial do Tesouro Transparente
  -> snapshot bruto completo
  -> parser CSV brasileiro validado
  -> yield_curve_quotes revision-aware
  -> transformação pura de curvas/vértices
  -> web/data/yield-curve.json
  -> SVG específico no navegador
```

O arquivo oficial é baixado integralmente por não oferecer filtro por data no recurso CSV. A retenção normalizada inicial é limitada a cinco anos por padrão. Revisões de uma mesma data/título/vencimento coexistem por `vintage_key`, da mesma forma que revisões de séries escalares não sobrescrevem observações antigas.

A reavaliação prevista no ADR 0009 não encontrou ainda justificativa suficiente para ECharts: a Sprint 8 exibe uma família por vez e no máximo duas datas. O componente continua específico e não vira framework gráfico interno. Ver ADR 0014.
