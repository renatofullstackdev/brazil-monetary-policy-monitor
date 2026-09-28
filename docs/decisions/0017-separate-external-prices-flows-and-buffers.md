# ADR 0017 — Separar preços, fluxos e buffers do setor externo

## Status

Aceita na Sprint 11.

## Contexto

Movimentos do câmbio podem coincidir com diferenciais de juros, conta corrente, investimento direto, carteira, reservas, risco e condições globais. Colocar todas essas variáveis em um score ou narrar uma delas como causa automática produziria uma interpretação mais forte do que os dados observados permitem.

Além disso, o módulo combina grandezas de natureza diferente: USD/BRL é preço; transações correntes, IDP e carteira são fluxos/saldos de contas externas; reservas são estoque; o câmbio real efetivo é índice.

## Decisão

1. Preservar cada família com unidade e frequência próprias.
2. Não produzir “câmbio justo” ou desalinhamento cambial a partir do índice real efetivo.
3. Permitir derivações simples e auditáveis, como variação do USD/BRL e razão IDP/déficit corrente, sempre classificadas como `derived`.
4. Tratar a razão IDP/déficit como comparação de escala, não identidade de financiamento.
5. Manter investimento em carteira separado de investimento direto.
6. Manter reservas como estoque, sem convertê-las em indicador causal de câmbio.
7. Adiar diferenciais Brasil–EUA até a Sprint 12, quando benchmarks americanos oficiais estiverem homologados.

## Consequências

O painel exige mais leitura do usuário do que um score único, mas mantém rastreabilidade, reduz falsa causalidade e permite que novas fontes sejam adicionadas sem reescrever a semântica das séries existentes.
