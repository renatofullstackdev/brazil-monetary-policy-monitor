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

**Sprint 1 — persistência e proveniência.**

O repositório já contém o schema SQLite versionado, persistência de fontes, séries, revisões de observações, parâmetros, eventos e execuções de ingestão. Consultas `latest_revision` e `as_known` tornam a semântica de vintage explícita. Nenhum coletor externo foi implementado ainda; a Sprint 2 validará o primeiro fluxo ponta a ponta com dados oficiais.

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
│   ├── project-plan.md
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

Requisito inicial: Python 3.11 ou superior.

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

## Próxima sprint

Sprint 2 implementará o primeiro pipeline ponta a ponta com uma fonte oficial simples do BCB: snapshot bruto, validação, persistência e JSON publicado, incluindo comportamento seguro quando a fonte estiver indisponível.
