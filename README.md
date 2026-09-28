# Painel de Política Monetária

Aplicação estática e auditável para investigar a política monetária brasileira a partir de dados oficiais, expectativas, parâmetros documentais e benchmarks explícitos. A Regra de Taylor é tratada como referência analítica, não como estimativa de uma “Selic correta”.

## Princípios

- **Fontes oficiais primeiro.** BCB, Tesouro Nacional, ANBIMA/B3 quando aplicável e fontes oficiais dos EUA.
- **Tempo econômico não é tempo de conhecimento.** `reference_period`, `source_observation_at` e `available_at` têm significados distintos.
- **Vintages são imutáveis.** Revisões novas não apagam o que foi observado anteriormente.
- **Derivações são reproduzíveis.** Fórmulas e insumos ficam explícitos.
- **Frontend estático.** O navegador consome JSON publicado; parsing de provedores e regras econômicas ficam no backend.
- **Ausência não vira aproximação silenciosa.** Indicadores incompletos permanecem `unavailable` e informam `missing_inputs`.
- **Sem dependências por conveniência.** A biblioteca padrão e JavaScript nativo continuam sendo o padrão até existir uma necessidade concreta.

## Arquitetura

```text
fontes oficiais
      │
      ▼
collectors/              transporte + parsing específico do provedor
      │
      ├──> data/raw/     snapshots dos bytes recebidos
      ▼
ingestion/               registro de fontes + persistência normalizada
      │
      ▼
SQLite                   observações, parâmetros, eventos e vintages
      │
      ▼
pipelines/               orquestração por domínio
      │
      ▼
publish/                 contratos JSON estáticos
      │
      ▼
web/                     HTML + CSS + ES modules + SVG nativo
```

As fronteiras estão descritas em [`docs/architecture.md`](docs/architecture.md). O modelo temporal está em [`docs/data-model.md`](docs/data-model.md) e os contratos do navegador em [`docs/frontend-contract.md`](docs/frontend-contract.md).

## Estrutura do projeto

```text
.
├── src/brazil_monetary_policy_monitor/
│   ├── collectors/      # HTTP e parsers por provedor
│   ├── db/              # conexão, migrations e queries
│   ├── ingestion/       # persistência normalizada por domínio
│   ├── models/          # cálculos econômicos puros
│   ├── pipelines/       # orquestração por domínio
│   ├── publish/         # contratos estáticos
│   ├── cli.py
│   └── temporal.py
├── data/
│   ├── database/
│   ├── published/
│   └── raw/
├── docs/
├── scripts/
├── tests/
└── web/
    ├── css/
    ├── data/
    └── js/
```

Não existem mais os módulos monolíticos `pipeline.py` e `ingestion.py`. Novos domínios devem entrar diretamente em `pipelines/<dominio>.py` e `ingestion/<dominio>.py`.

## Ambiente

Python **3.11+**. A suíte atual não exige dependências Python de runtime além da biblioteca padrão.

```bash
python3 -m venv .venv
source .venv/bin/activate
./scripts/test.sh
```

Também é possível instalar o pacote e usar a CLI:

```bash
python -m pip install -e .
bm-monitor --help
```

## Fluxo de desenvolvimento

Inicialize/migre o banco:

```bash
./scripts/init-db.sh
```

Atualize os domínios necessários:

```bash
./scripts/update-selic.sh
./scripts/update-focus.sh
./scripts/update-policy-history.sh
./scripts/rebuild-focus-history.sh
./scripts/update-macro.sh
./scripts/update-market-curves.sh
./scripts/update-credit.sh
./scripts/update-fiscal.sh
./scripts/update-external.sh
./scripts/update-us.sh
./scripts/update-copom.sh
```

Publique a visão principal e os checkpoints históricos:

```bash
./scripts/publish-overview.sh
./scripts/publish-vintages.sh
```

Sirva a aplicação:

```bash
./scripts/serve-web.sh
```

Acesse `http://127.0.0.1:8000/`. Abrir `web/index.html` por `file://` não é suportado porque os contratos são carregados por `fetch`.

## Semântica temporal

Uma observação pode ter, entre outros, estes tempos:

```text
reference_period       período econômico ou horizonte previsto
source_observation_at  data da estatística/vintage no provedor
published_at           data de publicação, quando conhecida
available_at           primeira data defensável em que o monitor pode usá-la
retrieved_at           instante da coleta
```

Para séries observadas convencionais, `observations_latest()` devolve a revisão mais recente de cada período. Para pesquisas e previsões, `observation_vintages()` preserva a evolução de estimativas sucessivas para o **mesmo** período-alvo. Isso é essencial para o histórico Focus e para reconstruções *as known at the time*.

## Contrato de indicadores V4

Indicadores exibidos em cartões e diálogos usam campos semanticamente separados:

```text
definition       o que mede
interpretation   como ler movimentos/distâncias
methodology      como é calculado, quando necessário
caveats[]        limitações reais
inputs[]         referências estruturadas dos insumos de indicadores derivados
missing_inputs[] subconjunto de referências ainda indisponíveis
```

Cada referência de insumo contém `key` para máquina e `label` em português para apresentação. `frequency` e `transformation` seguem o mesmo padrão `{key, label}`. A UI exibe somente os rótulos curados; identificadores internos, enums, nomes de variáveis e valores técnicos desconhecidos não são usados como texto de interface. O frontend também não copia silenciosamente um campo para preencher outro. Se um conteúdo não existe, a respectiva seção não aparece.

Tabelas são secundárias ao gráfico, recolhidas por padrão, usam o mesmo intervalo temporal selecionado, têm altura máxima com rolagem e cabeçalho fixo e paginam linhas extensas. Os ranges padrão ficam centralizados em `web/js/config.js`.

## Estado das curvas de mercado

O pipeline existente de `market_curves` ainda representa a implementação provisória anterior, baseada em ETTJ pública/DI1. Ele foi isolado e endurecido para que respostas malformadas, autenticação inválida, throttling ou falhas de transporte **não sejam confundidos com ausência de pregão**.

O antigo proxy histórico construído a partir de títulos ofertados pelo Tesouro Direto foi removido no Sprint 17C. O monitor não mantém uma terceira metodologia de curva apenas para preencher lacunas. Até a PRE/B3 entrar no Sprint 20, o diferencial nominal Brasil−EUA em aproximadamente 10 anos permanece explicitamente indisponível.

A substituição definitiva está planejada para o Sprint 20:

- B3 `TaxaSwap` / curva PRE como fonte primária da estrutura nominal;
- backfill histórico retomável;
- ANBIMA Feed autenticado quando configurado;
- fallback público sem alegar histórico inexistente;
- publicação web compacta, sem despejar todas as curvas brutas no navegador.

`.env.example` reserva as credenciais opcionais da ANBIMA sem versionar segredos.

## Estado do histórico monetário

Os Sprints 18 e 19 estão concluídos. A base contém metas históricas oficiais, hipóteses documentais de taxa neutra, vintages RI/RPM do hiato e expectativas Focus reconstruídas segundo o horizonte relevante conhecido em cada data. A partir desses insumos, o backend reconstrói semanalmente juro real ex ante, gap monetário real, Taylor prospectiva e Selic − Taylor com *as-of joins* e linhagem por ponto.

Os contratos JSON internos não usam número de versão duplicado entre publicador e navegador. Como ambos evoluem no mesmo repositório, os loaders validam `view` e a estrutura necessária; mudanças incompatíveis devem atualizar publisher, consumidor e testes na mesma alteração.

## Próximos sprints

O plano detalhado está em [`docs/roadmap.md`](docs/roadmap.md). Em resumo:

- **20:** curvas de mercado definitivas;
- **21:** histórico fiscal/Tesouro;
- **22:** operação, releases atômicos e consolidação.

## Testes

```bash
./scripts/test.sh
```

A suíte cobre parsers, persistência, idempotência, vintages, modelos, publishers e contratos do frontend. Testes que dependem de Node são executados quando `node` está disponível.

## Commits

Usar Conventional Commits e explicar principalmente **por que** a alteração foi necessária:

```text
refactor(pipelines): split orchestration by economic domain

Remove the monolithic pipeline module before historical backfills multiply
its responsibilities. Domain boundaries keep provider acquisition,
persistence and publication independently testable.
```
