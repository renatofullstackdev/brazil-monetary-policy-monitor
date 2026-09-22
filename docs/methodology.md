# Metodologia — princípios da V1

Este documento registra regras metodológicas que devem permanecer estáveis durante a implementação. Fórmulas específicas ganharão testes e referências quando forem implementadas.

## 1. Regra de Taylor como benchmark

A forma canônica adotada como referência é:

```text
i = r* + π + α(π - π*) + βx
```

com:

- `i`: taxa nominal indicada;
- `r*`: taxa real neutra;
- `π`: inflação relevante;
- `π*`: meta;
- `x`: hiato do produto.

Na especificação canônica:

```text
α = 0.5
β = 0.5
```

Esses coeficientes não devem ser recalibrados silenciosamente. Qualquer outra parametrização deve ser identificada como outra especificação ou simulação.

## 2. Três especificações iniciais

### Taylor clássica

Usará inflação observada, meta, taxa neutra e hiato.

### Taylor prospectiva

Usará expectativa de inflação no horizonte relevante, meta, taxa neutra e hiato. O horizonte não deve ser substituído automaticamente por 12 ou 24 meses quando houver evidência oficial de outro horizonte relevante.

### Taylor inercial

Representará ajuste parcial em direção ao valor indicado pela regra:

```text
i_t = ρ i_(t-1) + (1 - ρ) i_taylor
```

`ρ` será explícito e documentado.

## 3. Postura monetária real

A V1 também calculará:

```text
juro_real_ex_ante = taxa_nominal - inflação_esperada
```

```text
gap_monetario_real = juro_real_ex_ante - r*
```

A aproximação linear deve ser identificada como tal se for usada; uma versão exata multiplicativa pode ser adicionada e comparada quando o modelo for implementado.

## 4. Simulação

A experiência principal permite alterar somente:

- inflação;
- meta;
- taxa neutra;
- hiato.

`α`, `β`, `ρ`, medida de inflação, método do hiato e horizonte ficam em modo avançado.

Valores simulados nunca sobrescrevem valores oficiais ou persistidos.

## 5. Inflação

O painel distinguirá, conforme disponibilidade e metodologia oficial:

- IPCA cheio;
- inflação subjacente;
- serviços;
- expectativas;
- inflação implícita de mercado.

Inflação implícita não deve ser rotulada como expectativa pura porque pode incorporar prêmio de risco e liquidez.

## 6. Hiato e taxa neutra

Ambos são não observáveis. Valores publicados ou inferidos serão classificados como `estimated` e sempre exibirão fonte, período e metodologia disponível.

Uma proxy própria baseada em IBC-Br, caso criada, não será chamada de “hiato oficial”.

## 7. Curva de juros

Taxas de mercado de prazo maior podem refletir expectativa de taxas curtas futuras **e** prêmios. DI futuro não será apresentado automaticamente como expectativa pura da Selic.

Pontos interpolados devem ser identificados e o método de interpolação documentado.

## 8. Fiscal

O painel separará:

### Fluxo

- resultado primário;
- juros nominais;
- resultado nominal.

### Estoque

- DBGG/PIB.

### Perfil

- indexadores;
- vencimentos em 12 meses;
- prazo médio;
- reserva de liquidez;
- custo, quando metodologicamente adequado.

Não inferir que déficit nominal maior significa automaticamente impulso fiscal maior; juros altos podem deteriorar o próprio resultado nominal.

## 9. Setor externo

O painel não produzirá “câmbio justo”. O câmbio será estudado junto de:

- diferencial de juros;
- diferencial real;
- transações correntes;
- investimento direto;
- fluxos de carteira;
- reservas;
- condições financeiras globais.

Relações visuais não serão rotuladas como causalidade.

## 10. Brasil e Estados Unidos

A comparação deve harmonizar conceitos sem fingir equivalência onde as instituições e estatísticas diferem. Cada indicador americano deve manter sua própria fonte e metodologia.

## 11. Revisões históricas

Sempre que possível, cálculos históricos destinados a avaliar decisões passadas devem usar dados disponíveis à época. A interface deverá distinguir `as_known` de `latest_revision`.

## 12. Limite interpretativo

O painel fornece evidência e benchmarks. Não classifica decisões do Copom ou do Federal Reserve como corretas/incorretas e não atribui causalidade apenas por correlação temporal.
