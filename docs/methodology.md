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

Valores simulados nunca sobrescrevem valores oficiais ou persistidos. Na Sprint 5, os cenários existem apenas em memória no navegador e são descartados ao recarregar a página. Quando um insumo publicado ainda não existe, o controle inicia vazio em vez de receber uma hipótese implícita.

Os controles deslizantes possuem limites amplos apenas como proteção de interface. Esses limites não representam intervalo de confiança, faixa histórica ou julgamento de plausibilidade econômica.

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

## 13. Contrato numérico dos modelos implementados

A partir da Sprint 3, o núcleo analítico usa pontos percentuais em todas as taxas e gaps. Assim:

```text
4.5 = 4,5%
```

e não `0.045`.

As funções `classical_taylor` e `prospective_taylor` mantêm `α = 0.5` e `β = 0.5` por definição. A função genérica `taylor_rule` admite coeficientes explícitos somente para especificações nomeadas ou simulações avançadas.

A Taylor prospectiva não decide qual expectativa é economicamente correta. Ela recebe uma expectativa já selecionada pela camada de dados. A futura integração com Focus deverá registrar horizonte, data de conhecimento e fonte antes de chamar o modelo.

A Taylor inercial implementa:

```text
i_t = ρ i_(t-1) + (1 - ρ) i_taylor
```

com `0 <= ρ <= 1`. Os extremos são aceitos porque têm interpretação transparente: `ρ = 0` reproduz integralmente a Taylor subjacente e `ρ = 1` mantém integralmente a taxa anterior.

O juro real ex ante da V1 permanece a aproximação linear:

```text
r_ex_ante = i - E[π]
```

O gap monetário real é:

```text
gap_real = r_ex_ante - r*
```

Nenhuma dessas duas medidas deve ser apresentada como observação direta: ambas são cálculos derivados, e o gap ainda depende de `r*`, que é estimado.

Os cenários em `tests/fixtures/monetary_model_scenarios.json` existem exclusivamente para regressão numérica. Eles não são dados oficiais nem substituem as futuras séries Focus, de hiato ou de taxa neutra.

## Focus inflation and the relevant policy horizon

The canonical prospective input must distinguish the market-expectation source from the transformation used to align it with the Copom horizon.

The monitor stores raw monthly IPCA medians from the Focus `ExpectativaMercadoMensais` endpoint as survey data. For a policy horizon expressed as a quarter, it selects the twelve reference months ending in that quarter and computes:

```text
100 * (Π(1 + monthly_median / 100) - 1)
```

This output is a **derived proxy**. The median of each monthly distribution compounded across months is not, in general, equal to the median of institution-level cumulative twelve-month forecasts. The UI and metadata must preserve that distinction.

The policy horizon is not inferred mechanically from the date. It is an explicit, source-backed configuration because the Copom can change the relevant horizon as the policy window moves. The initial registry contains the transition from 2027-Q4 after the June 2026 meeting to 2028-Q1 from the August 2026 meeting onward.

For Focus backfills, `Data` is a provider statistic date (`source_observation_at`). It is not backdated into `available_at`; the latter remains the first time this monitor actually retrieved the vintage unless a stronger publication timestamp is available.

## 14. Insumos documentais e contexto doméstico da Sprint 7

A meta, a taxa real neutra e o hiato não são armazenados como séries SGS. Eles são parâmetros documentais versionados porque têm natureza e cronologia próprias.

Na configuração corrente da Sprint 7:

- a meta contínua é 3,00% desde janeiro de 2025;
- `r* = 5,00%` é a estimativa considerada no cenário de referência do Relatório de Política Monetária de junho de 2026;
- o hiato de `0,4%` refere-se ao 2º trimestre de 2026 no mesmo relatório.

`r*` e hiato são `estimated`. Nenhum dos dois é transformado em observação direta por estar sendo usado no cálculo.

A Taylor prospectiva corrente pode combinar insumos com referências distintas, mas deve mostrá-las. O valor corrente não gera automaticamente uma série histórica: aplicar o último `r*` ou o último hiato a datas anteriores introduziria informação futura.

O contexto macroeconômico inicial é mantido fora da fórmula de Taylor e inclui:

- IPCA cheio em 12 meses, composto das variações mensais SGS 433;
- núcleo de médias aparadas sem suavização em 12 meses, SGS 11426;
- IPCA serviços em 12 meses, SGS 10844;
- variação mensal do IBC-Br dessazonalizado, SGS 24364;
- taxa de desocupação da PNAD Contínua, SGS 24369;
- rendimento médio real habitual de todos os trabalhos, SGS 24380.

Os acumulados em 12 meses só são publicados quando existem doze meses consecutivos. O núcleo escolhido é uma medida específica, identificada pelo nome; a interface não o rotula como "a inflação subjacente" de forma genérica.

Consumo das famílias e FBCF permanecem fora desta sprint. A ausência é preferível a incorporar contratos ainda não homologados apenas para preencher a interface.
