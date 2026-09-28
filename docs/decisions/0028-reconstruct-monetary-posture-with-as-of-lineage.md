# ADR 0028 — Reconstruir a postura monetária com cortes as-of e linhagem por ponto

## Status

Aceito no Sprint 19.

## Contexto

O Sprint 18 estabilizou os insumos históricos da Taylor prospectiva, mas as métricas derivadas ainda eram apenas correntes. Persistir diretamente Taylor, juro real ex ante ou gaps criaria uma segunda fonte de verdade e tornaria mais difícil reproduzir o resultado quando um vintage ou parâmetro documental fosse corrigido.

Além disso, a SGS 432 havia sido retrocarregada com `available_at` igual ao instante de ingestão local. Essa convenção é conservadora para séries comuns, mas é inadequada para a meta Selic: cada observação histórica descreve a meta que já estava publicamente em vigor naquela data. Sem corrigir essa semântica, nenhuma reconstrução anterior ao início do monitor poderia usar Selic.

## Decisão

- As métricas `ex_ante_real_rate`, `real_monetary_gap`, `taylor_prospective` e `selic_minus_taylor` permanecem derivadas e são reconstruídas no backend durante a publicação.
- O relógio da reconstrução prospectiva é o histórico Focus do horizonte relevante. Mantém-se o último vintage defensavelmente disponível em cada semana ISO.
- Em cada ponto, Selic, taxa neutra, meta aplicável ao horizonte e hiato são selecionados por *as-of join* usando o mesmo `knowledge_cutoff`.
- A meta de inflação é selecionada pela data do horizonte previsto, não pela data corrente do ponto, e ainda precisa ter sido anunciada até o corte de conhecimento.
- Cada ponto derivado publica a linhagem dos insumos efetivamente selecionados, incluindo disponibilidade, referência e vintage/revisão quando existente.
- Para SGS 432, somente a primeira versão local de uma data histórica pode herdar disponibilidade no fim da própria data de referência. Uma versão diferente descoberta depois mantém `available_at = first_seen_at` e nunca é retrodatada.
- A disponibilidade histórica da Selic não é usada como gatilho para materializar centenas de novos bundles `as_known`; ela continua disponível dentro de cada bundle selecionado pelos demais marcos de conhecimento.

## Consequências

- O histórico derivado é reproduzível a partir dos dados oficiais/vintages persistidos e não precisa de tabela própria.
- Nenhum ponto usa revisão ou parâmetro cuja disponibilidade seja posterior ao corte daquele ponto.
- A Taylor prospectiva, o juro real ex ante e os gaps passam a ter histórico semanal navegável e auditável.
- Correções futuras do SGS não contaminam retrospectivamente a informação que o monitor considera conhecida no passado.
- A reconstrução começa quando os insumos prospectivos necessários passam a coexistir; ausência anterior permanece explícita.
