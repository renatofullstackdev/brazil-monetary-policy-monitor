# Painel de Política Monetária

Painel interativo, auditável e orientado a dados oficiais para investigar a política monetária brasileira. A Regra de Taylor é tratada como **benchmark analítico**, não como estimador de uma “Selic correta”.

## Objetivos da V1

A V1 deve permitir:

- comparar Selic, Taylor clássica, Taylor prospectiva e Taylor inercial;
- decompor a Regra de Taylor em inflação, meta, taxa real neutra e hiato;
- simular apenas essas quatro premissas na experiência principal;
- acompanhar juro real ex ante e gap monetário real;
- investigar inflação, expectativas, atividade, trabalho, crédito e transmissão;
- explorar curva nominal, curva real e inflação implícita sem confundi-las com expectativas puras;
- separar fiscal em fluxo, estoque e perfil da dívida;
- investigar câmbio, setor externo e diferencial Brasil–Estados Unidos;
- reproduzir, quando os dados permitirem, o conjunto de informação disponível em uma data passada;
- exibir fonte, transformação, data de referência, publicação e coleta de cada indicador.

O painel não emitirá conclusão automática sobre se determinada decisão do Copom foi “correta”.

## Princípios

1. **Fontes oficiais primeiro.** BCB, IBGE, Tesouro Nacional e fontes públicas oficiais dos EUA têm prioridade.
2. **Proveniência explícita.** Todo valor é classificado como observado, pesquisa/expectativa, estimativa, cálculo ou simulação.
3. **Vintages desde o início.** `reference_date`, `published_at` e `retrieved_at` são dimensões distintas.
4. **Frontend estático.** O navegador consome JSON preparado; não depende diretamente das APIs dos provedores.
5. **Arquitetura mínima.** Python + SQLite + snapshots + JSON + HTML/CSS/JavaScript.
6. **Sem modelo monolítico de “taxa correta”.** Taylor permanece simples; os demais módulos servem para investigar divergências e canais de transmissão.
7. **Decisões documentadas.** Mudanças arquiteturais ou metodológicas relevantes exigem documentação e, quando apropriado, ADR.

## Arquitetura

```text
Fontes oficiais
     |
     v
Coletores Python
     |----> snapshots brutos
     v
Normalização / transformações
     v
SQLite
     v
Publicador de JSON
     v
Frontend estático
HTML + CSS + JavaScript
```

Detalhes: [`docs/architecture.md`](docs/architecture.md).

## Estado atual

**Sprint 7 — inflação, atividade e trabalho.**

O repositório coleta a meta Selic, expectativas Focus e seis séries domésticas de inflação, atividade e trabalho pelo BCB. Meta de inflação, taxa real neutra e hiato entram como parâmetros documentais versionados, com referência explícita ao ato ou ao Relatório de Política Monetária. Com esses insumos, o painel publica a Taylor prospectiva corrente, Selic−Taylor, juro real ex ante e gap monetário real, sem fabricar histórico para `r*` ou hiato. O contexto macro mostra IPCA, núcleo, serviços, IBC-Br, desocupação e rendimento real em seção separada da fórmula.

## Estrutura

```text
.
├── README.md
├── pyproject.toml
├── docs/
│   ├── architecture.md
│   ├── methodology.md
│   ├── data-model.md
│   ├── data-sources.md
│   └── decisions/
├── src/brazil_monetary_policy_monitor/
│   └── db/
│       └── migrations/
├── tests/
├── collector/
├── data/
│   ├── raw/
│   ├── database/
│   └── published/
├── scripts/
└── web/
```

## Ambiente de desenvolvimento

Requisito inicial: Python 3.14 ou superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
./scripts/test.sh
```

Os testes fundamentais da Sprint 0 não exigem acesso à internet nem instalação de dependências: o script usa `PYTHONPATH=src` e a biblioteca padrão. Um `pyproject.toml` já descreve o pacote para ferramentas de build, mas instalação editável não é pré-requisito para validar esta sprint.

A V1 evita dependências Python de runtime enquanto elas não forem necessárias. Dependências futuras devem resolver um problema concreto e ser justificadas.

## Convenção de commits

Usar Conventional Commits:

```text
<type>(<scope>): <descrição curta>
```

Decisões relevantes devem ter corpo explicando principalmente **por que** a mudança foi necessária.

Exemplo:

```text
feat(data): add SQLite persistence for normalized observations

Store normalized series separately from raw provider snapshots so the
frontend does not depend on provider-specific schemas.

SQLite is sufficient for the expected single-host workload and keeps
operations simple while preserving a migration path if concurrent
writers or a public query API become necessary later.
```

## Banco local

Inicialize ou migre o banco de desenvolvimento com:

```bash
./scripts/init-db.sh
```

O arquivo padrão é `data/database/monitor.sqlite3` e não deve ser versionado.

## Atualização da meta Selic

A primeira execução busca o histórico desde 05/03/1999. O BCB aceita no máximo dez anos por consulta de série diária, mas esse limite não é tratado como tamanho operacional recomendado: a carga usa, por padrão, janelas de **um ano** para reduzir o custo de cada consulta e a exposição a timeouts do SGS. O tamanho pode ser ajustado entre 1 e 10 anos com `--window-years`. Execuções posteriores, sem `--start`, reutilizam o banco e consultam novamente os últimos sete dias para detectar eventuais alterações sem refazer todo o histórico.

```bash
./scripts/update-selic.sh
```

Para um intervalo explícito:

```bash
./scripts/update-selic.sh --start 2026-09-01 --end 2026-09-22
```

Parâmetros operacionais de rede e particionamento podem ser ajustados sem alterar o código:

```bash
./scripts/update-selic.sh \
  --window-years 1 \
  --timeout 30 \
  --retries 2 \
  --backoff-seconds 1
```

`--window-years 10` continua permitido porque respeita o limite publicado pelo BCB, mas não é o padrão: uma requisição válida segundo o contrato do provedor ainda pode ser lenta o suficiente para exceder o timeout em condições reais.

Artefatos padrão:

```text
data/database/monitor.sqlite3
data/raw/bcb/<data>/sgs-432/run-*/
data/published/br-selic-target.json
```

A série SGS 432 não fornece, no endpoint utilizado, um timestamp histórico de publicação por observação. Por isso `published_at` permanece vazio e `available_at` registra quando o monitor efetivamente observou uma revisão. O sistema não inventa disponibilidade histórica anterior à primeira coleta.

## Interface local

Depois de atualizar os dados, publique o contrato da tela inicial:

```bash
./scripts/publish-overview.sh
```

Sirva a pasta estática por HTTP:

```bash
./scripts/serve-web.sh
```

Acesse `http://127.0.0.1:8000/`. Abrir `web/index.html` diretamente por `file://` não é suportado porque o navegador precisa carregar `web/data/overview.json` por `fetch`.

Enquanto os insumos restantes da Sprint 7 ainda não estiverem incorporados, Taylor prospectiva e gap monetário continuam indisponíveis. A expectativa de inflação passa a vir do Focus e, quando Selic e Focus estiverem carregados, o juro real ex ante já pode ser calculado. O simulador deixa os campos ausentes vazios e só calcula depois que o usuário informar os quatro valores. Quando as séries oficiais existirem, os mesmos controles abrirão com os valores publicados e poderão ser restaurados por um único comando.

A simulação é mantida apenas em memória: não usa SQLite, API de aplicação nem armazenamento persistente do navegador. Detalhes do contrato: [`docs/frontend-contract.md`](docs/frontend-contract.md).

## Atualização do contexto doméstico

Depois de Selic e Focus estarem carregados, execute:

```bash
./scripts/update-macro.sh
```

A primeira execução busca aproximadamente cinco anos por série; as seguintes reutilizam o banco e refazem apenas uma sobreposição recente. O comando também sincroniza os três parâmetros documentais e republica `web/data/overview.json` somente depois que todas as séries macro solicitadas forem atualizadas com sucesso.

## Próxima sprint

Sprint 8 implementará a curva de juros, começando pela validação dos contratos oficiais do Tesouro e separando taxas nominais, reais e inflação implícita.

## Estado de implementação

- Sprint 0: fundação e decisões arquiteturais — concluída;
- Sprint 1: persistência, proveniência e vintages — concluída;
- Sprint 2: primeiro pipeline oficial BCB/SGS — concluída;
- Sprint 3: núcleo monetário (Taylor, postura real e decomposição) — concluída;
- Sprint 4: contrato JSON e primeira interface estática — concluída;
- Sprint 5: simulador local da Taylor prospectiva — concluída.

### Focus expectations (Sprint 6)

Update the official Focus IPCA monthly medians and the horizon-aligned derived expectation with:

```bash
./scripts/update-focus.sh
```

The first run intentionally backfills only the last two years by default. This is an operational default, not a claim about the beginning of the Focus database. Use `--start YYYY-MM-DD` for a deeper historical backfill. Subsequent runs overlap recent source dates to capture revisions.

The dashboard distinguishes the Focus survey rows from the compounded policy-horizon proxy and does not backdate historical API rows into public-availability timestamps.
