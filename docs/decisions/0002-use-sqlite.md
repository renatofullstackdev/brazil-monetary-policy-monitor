# ADR 0002 — SQLite como persistência inicial

## Status

Aceito.

## Contexto

O volume esperado é pequeno para padrões de banco: séries macroeconômicas, normalmente diárias/mensais/trimestrais, escritas por um pipeline único. O frontend não acessará o banco diretamente.

## Decisão

Usar SQLite na V1.

## Consequências

- implantação sem serviço de banco separado;
- transações e constraints suficientes para integridade;
- backups simples;
- menor custo operacional para manutenção individual.

Se surgirem múltiplos escritores, consultas públicas arbitrárias ou necessidade operacional incompatível com SQLite, migrar para PostgreSQL.

## Alternativas consideradas

### PostgreSQL desde o início

Tecnicamente adequado, mas rejeitado por adicionar operação sem benefício proporcional no workload previsto.

### Apenas arquivos JSON/CSV

Rejeitado como armazenamento normalizado principal porque constraints, revisões/vintages e consultas de publicação ficariam mais frágeis.
