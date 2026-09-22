# Modelo de dados — Sprint 1

A persistência da V1 usa SQLite e migrations SQL *forward-only*. O schema não é um cache descartável: ele preserva proveniência e revisões necessárias para reconstruir o conjunto de informação disponível em uma data passada.

## Convenções temporais

Timestamps persistidos pela aplicação devem ser normalizados para UTC em formato RFC 3339, por exemplo:

```text
2026-09-22T12:30:00Z
```

Essa normalização é requisito porque algumas constraints e ordenações do SQLite usam comparação lexical.

Períodos econômicos não são reduzidos artificialmente a um único dia. `observations` guarda:

- `reference_period`: rótulo canônico do período, como `2026-08`, `2026-Q2` ou `2026-09-22`;
- `reference_start`;
- `reference_end`.

Isso permite representar mensal, trimestral e diário sem fingir que uma observação trimestral ocorreu em um dia arbitrário.

## `schema_migrations`

Registra migrations aplicadas. `PRAGMA user_version` replica a versão corrente para inspeção rápida, mas `schema_migrations` é o histórico autoritativo.

Migrations são numeradas sequencialmente e nunca devem ser reescritas depois de compartilhadas. Correções futuras recebem uma nova migration.

## `sources`

Identifica um recurso/provedor de origem.

Campos centrais:

- `key`: chave interna estável;
- `provider`;
- `name`;
- URL e documentação;
- licença quando aplicável;
- metadados adicionais.

A chave interna não deve depender de título traduzido ou texto de interface.

## `series`

Define uma série normalizada e sua semântica.

Inclui:

- chave interna estável;
- fonte;
- identificador da série no provedor;
- título e descrição;
- unidade original e unidade normalizada;
- frequência;
- classificação epistemológica;
- transformação;
- status.

A V1 persiste somente `observed`, `survey`, `estimated` e `derived`. Valores `simulated` pertencem à sessão do usuário e não podem ser gravados como se fossem dados da fonte.

A frequência permanece textual em vez de uma enumeração SQL fechada porque as fontes podem exigir semânticas como dias úteis ou periodicidade irregular. O vocabulário canônico será estabilizado quando os primeiros coletores fornecerem casos reais.

## `observations`

Cada linha representa **uma revisão conhecida** de uma observação, não apenas um período.

Campos temporais relevantes:

- `reference_period`, `reference_start`, `reference_end`: o período econômico;
- `published_at`: publicação/revisão informada pelo provedor, se conhecida;
- `available_at`: limite a partir do qual o monitor pode afirmar que essa revisão estava disponível;
- `first_seen_at`: primeira coleta em que o monitor encontrou a revisão;
- `last_seen_at`: última confirmação da mesma revisão.

`vintage_key` identifica a revisão de forma estável dentro de `(series, reference_period)`. A estratégia concreta será responsabilidade do adaptador da fonte.

A unicidade é:

```text
(series_id, reference_period, vintage_key)
```

Logo, revisões diferentes do mesmo período coexistem.

### `latest_revision`

Escolhe, para cada período, a revisão com maior `available_at`.

### `as_known`

Recebe `knowledge_cutoff` e primeiro elimina qualquer revisão com:

```text
available_at > knowledge_cutoff
```

Só depois escolhe a revisão mais recente de cada período. Isso impede utilizar revisões futuras em análises históricas.

Ver ADR 0006.

## `parameters`

Armazena parâmetros econômicos/metodológicos que precisam de vigência e proveniência, como meta de inflação ou estimativas de taxa neutra.

Inclui:

- chave e valor;
- unidade;
- classificação epistemológica;
- `effective_from` / `effective_to`;
- publicação, disponibilidade e coleta;
- `version_key`;
- fonte e metodologia.

Coeficientes fixos que fazem parte da definição de um modelo podem permanecer no código/metodologia quando não houver benefício em tratá-los como série temporal. A Sprint 3 decidirá isso para as variantes de Taylor sem forçar o schema a armazenar toda constante matemática.

## `events`

Registra eventos datados, por exemplo Copom, comunicados, atas e RPM. `event_key` é uma identidade estável fornecida pelo adaptador.

A tabela existe desde a Sprint 1 para evitar retrofit do schema, embora a ingestão de eventos só esteja prevista para sprint posterior.

## `ingestion_runs`

Registra cada execução operacional de coleta:

- provedor/fonte;
- início/fim;
- status;
- registros recebidos, inseridos, atualizados e inalterados;
- erro estruturado;
- versão do coletor.

Uma execução `running` não possui `finished_at`; execuções finalizadas precisam possuí-lo. Isso torna estados incompletos detectáveis.

## Integridade deliberadamente deixada para a aplicação

Campos `*_json` são `TEXT` na Sprint 1. Não há constraint `json_valid()` para evitar tornar o schema dependente da disponibilidade das extensões JSON do SQLite. Coletores e modelos deverão validar o conteúdo antes de persistir.

Da mesma forma, não se impõem enums SQL excessivamente restritos para frequências e tipos de evento antes de observar casos reais das fontes oficiais.
