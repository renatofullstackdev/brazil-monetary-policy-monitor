# Arquitetura

## Objetivo

Manter o monitor pequeno, reproduzível e auditável sem acoplar a interface às APIs dos provedores. Aquisição, persistência, modelagem econômica e apresentação são responsabilidades separadas.

## Camadas

```text
┌────────────────────────────────────────────────────────────┐
│ Provedores oficiais                                        │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│ collectors/                                                │
│ HTTP, URL/formato do provedor, parsing e validação         │
└──────────────────────────┬─────────────────────────────────┘
                           │
                  snapshots em data/raw/
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│ ingestion/                                                 │
│ metadados de fontes, séries e persistência normalizada     │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│ SQLite                                                     │
│ observations, parameters, events, ingestion_runs, curvas   │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│ models/ + pipelines/                                       │
│ cálculos puros + orquestração por domínio                  │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│ publish/                                                   │
│ contratos JSON validados                                  │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│ web/                                                       │
│ HTML, CSS, ES modules e SVG nativo                         │
└────────────────────────────────────────────────────────────┘
```

## Fronteiras

### `collectors/`

Conhece o transporte e o formato externo. Não conhece a UI e não toma decisões econômicas. Um parser deve rejeitar conteúdo estruturalmente incompatível; não deve converter mudança de formato do provedor em “dia sem dados”.

### `ingestion/`

Conhece o schema persistente e a identidade canônica de fontes/séries. É dividido por domínio (`sgs`, `focus`, `policy`, `fiscal`, `market_curves`, `fred`, `tesouro`) e contém o ciclo de `ingestion_runs` em módulo próprio.

### `db/`

Contém migrations e queries. A camada expõe consultas com semântica temporal explícita. Em particular:

- `observations_latest`: última revisão de cada período;
- `observations_as_known`: última revisão de cada período conhecida até um corte;
- `observation_vintages`: evolução das estimativas/vintages sem colapsar datas sucessivas do provedor.

### `models/`

Cálculos econômicos puros. Não faz HTTP, não grava SQLite e não publica JSON. Regra de Taylor, crescimento real e transformações de curva devem ser testáveis com valores determinísticos.

### `pipelines/`

Orquestra um domínio. Um pipeline pode:

1. determinar janela incremental;
2. iniciar `ingestion_run`;
3. coletar e salvar snapshot;
4. validar/normalizar;
5. persistir;
6. publicar o contrato relevante somente após sucesso coerente.

Não existe `pipeline.py` central. Funcionalidade nova entra em um módulo de domínio; utilidades realmente compartilhadas ficam em `pipelines/runtime.py` ou `pipelines/sgs.py`.

### `publish/`

Transforma o estado normalizado em contratos de leitura. Não deve fazer chamadas de rede. Regras de alinhamento econômico entre frequências ficam aqui/backend quando afetam o significado do indicador; o frontend não deve escolher “o ponto mais próximo”.

### `web/`

Consome contratos estáticos. Estado de visualização, ranges e simulações locais ficam no navegador. Parsing de provedor, reconstrução de vintages e regras *as-of* econômicas não ficam aqui.

## Dependências permitidas

A direção desejada é:

```text
collectors ─┐
            ├─> pipelines -> publish
models ─────┤       │          │
ingestion -> db <────┘          │
            └───────────────────┘
```

Módulos de `db/` não importam `ingestion/`. Utilidades neutras de tempo ficam em `temporal.py`, evitando dependência invertida.

## Falhas e publicação

- snapshots são gravados antes do parsing sempre que tecnicamente possível;
- uma revisão válida anterior não é apagada por falha posterior;
- erros de autenticação, throttling, servidor, transporte e parsing são falhas, não “datas puladas”;
- ausência genuína de arquivo para uma data pode ser tratada como `skip` apenas quando o provedor a identifica de forma inequívoca;
- cada JSON individual é escrito por arquivo temporário + `os.replace()`.

O Sprint 22 evoluirá a atomicidade de **arquivo** para atomicidade de **release**, publicando todos os contratos sob um `publication_id` e alternando um manifesto `current` somente depois de validar a geração completa.

## Frontend sem framework

A aplicação continua em JavaScript nativo porque a complexidade atual é de contratos e estado pequeno, não de árvore de componentes. Utilitários compartilhados cobrem:

- ranges padrão (`config.js`);
- estado visual dos ranges (`ranges.js`);
- paginação e alinhamento *as-of* de apresentação (`table.js`);
- gráficos SVG reutilizáveis.

Framework frontend só deve ser introduzido se uma necessidade concreta superar o custo adicional.
