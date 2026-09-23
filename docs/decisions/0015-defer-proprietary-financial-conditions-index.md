# ADR 0015 — Não criar índice proprietário de condições financeiras na Sprint 9

## Status

Aceita.

## Contexto

A Sprint 9 precisa mostrar transmissão monetária por crédito. Um único índice de "condições financeiras" poderia ser visualmente conveniente, mas exigiria escolhas de variáveis, transformação, sinal, normalização, janela histórica e pesos.

Essas escolhas mudam materialmente o significado do resultado. Sem uma fonte oficial ou uma metodologia externa suficientemente defensável, um índice criado apenas para resumir o painel daria aparência de objetividade a decisões arbitrárias.

## Decisão

A Sprint 9 mantém separadamente:

- crescimento real do saldo livre e direcionado;
- taxas médias das novas operações livres e direcionadas;
- inadimplência livre e direcionada.

Nenhuma média, PCA, z-score ponderado ou score manual será apresentado como índice de condições financeiras.

## Consequências

A interface exige que o usuário observe mais de uma dimensão, mas preserva conceitos oficiais e auditáveis. Um índice composto poderá ser adicionado depois se houver metodologia publicada, fonte oficial ou necessidade analítica clara que justifique e documente cada escolha.
