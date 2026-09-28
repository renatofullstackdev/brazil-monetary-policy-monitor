# ADR 0010 — Manter simulações locais ao navegador

## Contexto

A Sprint 5 permite alterar inflação esperada, meta, taxa real neutra e hiato para observar a reação da Taylor prospectiva. Esses valores são hipóteses do usuário, não observações, pesquisas ou estimativas publicadas pelas fontes oficiais.

Persistir esses cenários no SQLite os aproximaria indevidamente do pipeline de dados oficiais e criaria dúvidas sobre autoria, validade e temporalidade. Enviar cada alteração a um backend também adicionaria infraestrutura sem necessidade: o cálculo é pequeno, determinístico e já possui implementação de referência em Python.

## Decisão

A simulação será mantida apenas no estado em memória da página.

- nenhum cenário é gravado no SQLite;
- nenhum cenário é enviado por HTTP;
- não será usado `localStorage`, `sessionStorage` ou IndexedDB na V1;
- os quatro controles são inicializados com valores publicados quando disponíveis;
- se um insumo oficial estiver indisponível, o campo correspondente permanece vazio;
- a função JavaScript replica somente a Taylor prospectiva canônica com `alpha = beta = 0.5`;
- a implementação Python continua sendo a referência metodológica e testes opcionais de paridade verificam ambas quando Node.js estiver disponível.

Os limites mínimos e máximos dos controles deslizantes são guardrails de interface para evitar entradas acidentais extremas; não são intervalos de confiança nem afirmações sobre valores economicamente plausíveis.

## Consequências

A interação é imediata e o site continua completamente estático. Também fica impossível confundir, no banco, uma hipótese digitada pelo usuário com um valor de fonte oficial.

Ao recarregar a página, a simulação é perdida. Isso é intencional na V1. Se futuramente houver requisito explícito para cenários compartilháveis ou persistentes, será necessário definir um contrato separado de dados e proveniência antes de adicionar armazenamento.

## Alternativas consideradas

### Persistir cenários no SQLite

Rejeitado porque mistura estado pessoal/transitório com o repositório auditável de dados macroeconômicos.

### Persistir no armazenamento do navegador

Rejeitado na V1 porque acrescenta estado implícito e pode fazer o usuário retornar a uma página com premissas antigas sem perceber.

### Calcular no backend

Rejeitado porque o cálculo é simples, não usa segredos nem dados adicionais, e uma requisição por movimento de slider pioraria a experiência sem benefício metodológico.
