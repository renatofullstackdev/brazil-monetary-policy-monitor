# ADR 0006 — Modelar vintages como revisões coexistentes

## Contexto

Séries macroeconômicas podem ser revisadas. Se uma nova coleta simplesmente substituir o valor anterior de um período, o sistema perde a capacidade de reconstruir o conjunto de informação disponível no momento de uma decisão passada. Isso introduziria *look-ahead bias* justamente nas análises históricas em que a auditabilidade é mais importante.

Também não é seguro equiparar `retrieved_at` a data de publicação. Uma observação pode ter sido publicada dias, meses ou anos antes de ser coletada pelo monitor.

## Decisão

Cada versão conhecida de uma observação será persistida como registro próprio em `observations`.

A identidade de uma versão é formada por:

- série;
- período de referência;
- `vintage_key` fornecida ou construída pelo adaptador da fonte.

O registro preserva separadamente:

- `published_at`: momento informado pela fonte, quando conhecido;
- `available_at`: momento mais antigo em que podemos afirmar que aquela revisão estava disponível;
- `first_seen_at`: primeira vez em que o monitor observou aquela revisão;
- `last_seen_at`: última coleta que confirmou a mesma revisão.

Quando a fonte fornece a data de publicação/revisão, ela pode fundamentar `available_at`. Quando não fornece, o coletor deve usar `first_seen_at` como limite conservador, em vez de inferir uma disponibilidade anterior.

Consultas `as_known` só podem utilizar registros com `available_at <= knowledge_cutoff`. Consultas `latest_revision` escolhem a revisão de maior `available_at` para cada período.

## Consequências

- revisões não destroem o histórico;
- análises históricas podem evitar informação futura;
- a tabela cresce com revisões, mas o volume esperado é pequeno para séries macroeconômicas;
- cada adaptador precisa definir `vintage_key` de forma estável;
- fontes sem histórico de revisões completo só permitem reconstrução conservadora a partir do primeiro momento observado pelo monitor.

## Alternativas consideradas

### Sobrescrever `(series, reference_period)`

É mais simples, mas inviabiliza `as_known` e auditoria de revisões.

### Tratar cada coleta como novo vintage

Preserva tudo, mas duplica a mesma observação diariamente e confunde horário de coleta com mudança econômica. O monitor deve atualizar `last_seen_at` quando reencontrar a mesma revisão, não criar um novo valor apenas porque houve nova requisição.

### Manter uma tabela global de vintages

Algumas fontes possuem releases bem definidos, outras revisam séries com semânticas próprias. Forçar um objeto global de release na V1 criaria uma abstração comum que os provedores não necessariamente compartilham. A semântica fica inicialmente junto da observação e pode ser generalizada posteriormente se os coletores demonstrarem essa necessidade.
