# Modelo de dados — requisitos para a Sprint 1

Este documento define requisitos sem congelar prematuramente o DDL.

## Entidades mínimas

### `sources`

Identifica provedor e recurso oficial.

Campos conceituais:

- identificador interno;
- provider;
- nome;
- URL/documentação;
- licença/termos quando aplicável;
- metadados de proveniência.

### `series`

Descreve uma série normalizada.

Campos conceituais:

- chave estável interna;
- fonte;
- identificador original;
- título;
- unidade original;
- unidade normalizada;
- frequência;
- classificação epistemológica;
- descrição da transformação;
- status.

### `observations`

Uma observação deve conseguir representar:

- série;
- `reference_date` ou período;
- valor;
- `published_at` quando conhecido;
- `retrieved_at`;
- vintage/revisão quando aplicável;
- referência ao artefato bruto ou ingestão;
- flags de qualidade.

A Sprint 1 deve definir unicidade sem assumir que `(series, reference_date)` é suficiente, porque revisões podem coexistir.

### `parameters`

Parâmetros metodológicos versionados no tempo, por exemplo:

- meta de inflação;
- `r*`;
- coeficientes de uma especificação;
- outras hipóteses publicadas.

Deve guardar vigência, fonte e classificação.

### `events`

Eventos de política monetária e publicação:

- Copom;
- comunicado;
- ata;
- RPM;
- equivalentes americanos quando necessários.

### `ingestion_runs`

Auditoria operacional:

- provider;
- início/fim;
- status;
- registros recebidos/inseridos/atualizados;
- erro estruturado;
- versão do coletor quando útil.

## Regras

- valores simulados não entram em `observations` oficiais;
- revisões não apagam silenciosamente versões anteriores quando necessárias para `as_known`;
- uma transformação derivada precisa ser reproduzível;
- unidade deve ser explícita, nunca inferida apenas pelo nome da série;
- datas mensais/trimestrais precisam de convenção documentada para evitar falsas datas diárias.
