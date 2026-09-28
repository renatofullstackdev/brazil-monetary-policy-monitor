# ADR 0008 — Manter modelos monetários puros e unidades explícitas

## Contexto

A V1 precisa calcular regras de Taylor, juro real ex ante e gap monetário a partir de valores que futuramente virão de banco, JSON publicado e simulações locais no navegador. Acoplar as fórmulas à persistência ou ao processo de coleta faria a mesma identidade econômica depender do caminho usado para obter o dado e tornaria testes de regressão mais difíceis.

Há também um risco de unidade: APIs, artigos e bibliotecas podem representar taxas como `0.045` ou `4.5`. Misturar essas convenções produziria resultados silenciosamente errados.

## Decisão

Os modelos monetários serão funções puras no pacote `models`, sem acesso a rede, banco, relógio ou estado global.

Todas as taxas, desvios e hiatos recebidos e produzidos pelo núcleo da V1 serão expressos em **pontos percentuais**. Assim, `4.5` representa 4,5%, e não `0.045`.

A Taylor canônica fixa `alpha = 0.5` e `beta = 0.5`. Uma função genérica aceita coeficientes explícitos para futuras especificações e simulações, mas as funções `classical_taylor` e `prospective_taylor` não os recebem como argumentos. Isso impede recalibração silenciosa do benchmark canônico.

A Taylor prospectiva difere da clássica apenas na semântica da inflação fornecida: expectativa no horizonte escolhido em vez de inflação realizada. A escolha do horizonte pertence à camada de dados/metodologia, não à fórmula.

O juro real ex ante da V1 usa a aproximação linear já definida no projeto:

```text
real_ex_ante = nominal_rate - expected_inflation
```

Ela não será substituída silenciosamente pela relação multiplicativa de Fisher.

## Consequências

- fórmulas podem ser testadas isoladamente e reproduzidas no JavaScript da interface;
- uma mudança de fonte ou banco não altera a matemática;
- erros de unidade ficam mais fáceis de detectar e documentar;
- especificações não canônicas precisam ser nomeadas explicitamente;
- a camada que seleciona Focus, hiato e taxa neutra continuará responsável por proveniência e horizonte;
- se uma taxa exata de Fisher for necessária posteriormente, será adicionada como indicador distinto, não como alteração retroativa da métrica V1.

## Alternativas consideradas

### Persistir todo cálculo como observação

Rejeitado para a Sprint 3. Resultados derivados podem ser publicados posteriormente, mas a identidade da fórmula não deve depender de armazenamento.

### Usar `Decimal` em todo o núcleo

Não adotado. Os indicadores serão reproduzidos por `Number` no navegador e não envolvem contabilidade monetária de centavos. `float`, com validação de finitude e testes numéricos, mantém a implementação simples e coerente entre Python e JavaScript.

### Aceitar taxas como frações decimais

Rejeitado por ser menos natural para as séries econômicas exibidas e aumentar o risco de conversão incorreta na UI.
