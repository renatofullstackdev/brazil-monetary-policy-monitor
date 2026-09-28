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

Valores simulados nunca sobrescrevem valores oficiais ou persistidos. Na interface atual, os cenários existem apenas em memória no navegador e são descartados ao recarregar a página. Quando um insumo publicado ainda não existe, o controle inicia vazio em vez de receber uma hipótese implícita.

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

O painel não produz “câmbio justo”. Câmbio nominal e real, transações correntes, investimento direto, carteira e reservas são mantidos como indicadores distintos. Diferenciais de juros e condições financeiras globais só entram quando suas próprias fontes são homologadas.

Relações visuais não são rotuladas como causalidade.

## 10. Brasil e Estados Unidos

A comparação deve harmonizar conceitos sem fingir equivalência onde as instituições e estatísticas diferem. Cada indicador americano deve manter sua própria fonte e metodologia.

## 11. Revisões históricas

Sempre que possível, cálculos históricos destinados a avaliar decisões passadas devem usar dados disponíveis à época. A interface deverá distinguir `as_known` de `latest_revision`.

## 12. Limite interpretativo

O painel fornece evidência e benchmarks. Não classifica decisões do Copom ou do Federal Reserve como corretas/incorretas e não atribui causalidade apenas por correlação temporal.

## 13. Contrato numérico dos modelos implementados

O núcleo analítico usa pontos percentuais em todas as taxas e gaps. Assim:

```text
4.5 = 4,5%
```

e não `0.045`.

As funções `classical_taylor` e `prospective_taylor` mantêm `α = 0.5` e `β = 0.5` por definição. A função genérica `taylor_rule` admite coeficientes explícitos somente para especificações nomeadas ou simulações avançadas.

A Taylor prospectiva não decide qual expectativa é economicamente correta. Ela recebe uma expectativa já selecionada pela camada de dados. A integração Focus registra horizonte, data da estatística e fronteira de conhecimento antes de chamar o modelo; a reconstrução histórica do Sprint 19 usa esses campos e nunca seleciona insumo com `available_at` posterior ao corte do ponto.

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

The policy horizon is not inferred mechanically from the date. It is an explicit, source-backed registry because the Copom can change the relevant horizon as the policy window moves. The Sprint 18 registry covers documented transitions from 2026-Q1 (September 2024) through 2028-Q1 (August 2026), using the publication date of the corresponding minute as the knowledge boundary.

For Focus backfills, `Data` is a provider statistic date (`source_observation_at`). The historical endpoint does not expose the exact publication timestamp. Because the BCB catalog documents weekly publication, `available_at` uses a conservative seven-calendar-day boundary after `Data`, or an earlier `first_seen_at` when local collection proves that the vintage was already accessible. The seven-day date is a defensible upper bound, not an asserted release timestamp.

## 14. Insumos documentais e contexto doméstico

Meta de inflação e taxa real neutra são regimes/hipóteses documentais versionados. O hiato do produto é diferente: como é uma estimativa trimestral revisável, o Sprint 18 o modela em `observations` e preserva cada vintage de RI/RPM.

A cobertura histórica curada é:

- meta formal do CMN: centros anuais de 1999 a 2024 e meta contínua de 3,00% desde janeiro de 2025;
- `r*` do Copom: 4,0% em fevereiro de 2023, 4,5% em junho de 2023, 4,75% em junho de 2024 e 5,0% em dezembro de 2024;
- hiato: vintages explicitamente publicados nos RI/RPM entre setembro de 2024 e setembro de 2026.

`r*` e hiato são `estimated`; nenhum deles é transformado em observação direta por estar sendo usado no cálculo. O Sprint 19 reconstrói semanalmente as derivações prospectivas a partir do último vintage Focus defensavelmente disponível em cada semana. No mesmo corte de conhecimento, seleciona a Selic conhecida, a hipótese de `r*`, o último vintage de hiato aplicável e a meta correspondente ao horizonte previsto. Cada ponto publicado preserva essa linhagem.

Na SGS 432, a primeira versão local de uma data histórica representa a meta Selic que já estava publicamente em vigor naquela data. Para permitir reconstrução histórica sem confundir data de ingestão local com disponibilidade econômica, essa primeira versão usa o fim do próprio dia de referência como fronteira conservadora. Se o provedor posteriormente alterar o valor da mesma data, a nova revisão só fica disponível a partir de `first_seen_at`; revisões posteriores nunca são retrodatadas.

Para a meta, o horizonte prospectivo exige uma seleção adicional: a meta deve já ser conhecida em `t` **e** aplicar-se ao período futuro previsto. Essa seleção é feita por data de referência, não pela última meta vigente na data corrente.

O contexto macroeconômico inicial é mantido fora da fórmula de Taylor e inclui:

- IPCA cheio em 12 meses, composto das variações mensais SGS 433;
- núcleo de médias aparadas sem suavização em 12 meses, SGS 11426;
- IPCA serviços em 12 meses, SGS 10844;
- variação mensal do IBC-Br dessazonalizado, SGS 24364;
- taxa de desocupação da PNAD Contínua, SGS 24369;
- rendimento médio real habitual de todos os trabalhos, SGS 24380.

Os acumulados em 12 meses só são publicados quando existem doze meses consecutivos. O núcleo escolhido é uma medida específica, identificada pelo nome; a interface não o rotula como "a inflação subjacente" de forma genérica.

Consumo das famílias e FBCF permanecem fora da base atual. A ausência é preferível a incorporar contratos ainda não homologados apenas para preencher a interface.

## 15. Curva de juros do Tesouro Direto

A visualização não pretende estimar uma curva zero-cupom soberana completa. Ela organiza os yields dos títulos que o Tesouro Direto ofertou em cada data-base.

Para cada título elegível:

```text
prazo_em_anos = (data_vencimento - data_base) / 365,2425
```

A curva nominal usa títulos prefixados; a curva real usa títulos IPCA+. As duas podem misturar variantes com e sem cupom, razão adicional para o rótulo **proxy de yields ofertados**, em vez de curva zero-cupom.

### Vértices constantes

São calculados 2, 3, 5, 7 e 10 anos. Um vértice só existe quando há dois vencimentos observados que o envolvam (ou um ponto exatamente naquele prazo). A interpolação é linear entre esses pontos. Não há extrapolação antes do menor ou depois do maior vencimento.

Essa regra faz com que um cartão de 2 anos possa aparecer como indisponível mesmo quando há títulos próximos. O monitor não substitui ausência de cobertura por um vencimento arbitrariamente próximo.

### Inflação implícita

Quando o mesmo vértice possui taxa nominal `n` e taxa real `r`, a inflação implícita é:

```text
(1 + n) / (1 + r) - 1
```

com taxas convertidas de percentual para fração antes da operação e devolvidas em percentual depois.

Não se usa simplesmente `n - r`. Também não se rotula o resultado como expectativa pura: o spread pode incorporar prêmios de risco, liquidez, diferenças de estrutura de cupom e outras características dos instrumentos.

### Inclinação

A inclinação apresentada é `10 anos - 2 anos` dentro da mesma família (nominal, real ou inflação implícita). Se um dos dois vértices não puder ser interpolado, a inclinação permanece indisponível.

### Comparação temporal

Uma data solicitada utiliza a última data-base existente **na própria data ou antes dela**. A UI sempre informa a data efetiva usada. Os presets de 1 mês e 1 ano são calculados em relação à curva mais recente. O preset de Copom anterior fica disponível quando eventos do Copom estão persistidos e resolve a decisão anterior respeitando o mesmo corte de conhecimento da curva.


## 16. Crédito e transmissão monetária

O bloco de crédito é descritivo. Uma taxa Selic mais alta pode afetar taxas bancárias, demanda por crédito, composição das concessões, risco e inadimplência, mas o painel não transforma co-movimento temporal em atribuição causal.

### Crescimento real do saldo

Para cada carteira (livre e direcionada), a crédito e transmissão monetária parte do saldo nominal observado no SGS e calcula, quando há cobertura mensal completa:

```text
crescimento_real_12m = ((saldo_t / saldo_t-12) / fator_IPCA_12m - 1) * 100
```

`fator_IPCA_12m` é o produto dos doze fatores mensais do IPCA que ligam o nível de preços de `t-12` a `t`. O cálculo só é publicado quando existem o saldo corrente, o saldo do mesmo mês do ano anterior e os doze IPCA mensais do intervalo.

O resultado é `derived`; os saldos originais permanecem `observed` e inalterados no SQLite.

### Taxas médias

As séries 20717 e 20756 são taxas médias anuais das novas operações, ponderadas pelo valor das concessões. Elas são úteis para acompanhar transmissão para condições efetivamente contratadas, mas mudanças de composição entre modalidades, tomadores e risco também afetam a média.

Por isso, a diferença entre crédito livre e direcionado é mostrada apenas como diferença descritiva em pontos percentuais; não é interpretada como prêmio puro nem como efeito isolado da política monetária.

### Inadimplência

As séries 21085 e 21132 medem a proporção da carteira com ao menos uma parcela vencida há mais de 90 dias. São exibidas no nível observado e não transformadas em indicador causal de aperto monetário.

### Índice composto

A camada de crédito e transmissão monetária não cria um índice proprietário de condições financeiras. Um índice desse tipo exigiria uma metodologia explícita para transformação, sinal, padronização e pesos. Até existir fonte oficial ou metodologia que justifique essas escolhas, o painel mantém os canais separadamente observáveis.


## 17. Fiscal

O módulo fiscal é descritivo e separa **fluxo**, **estoque** e **perfil de financiamento**. Ele não tenta condensar essas dimensões em um score nem inferir causalidade a partir de co-movimentos.

### Fluxos das NFSP

Primário, juros nominais e resultado nominal são apresentados em `% do PIB`, acumulados em 12 meses, conforme as séries SGS homologadas. O sinal não é invertido: na convenção das NFSP, positivo indica déficit/necessidade de financiamento e negativo indica superávit.

O resultado nominal incorpora juros nominais, mas o monitor não interpreta mecanicamente sua variação como efeito da Selic. O custo financeiro observado também depende da composição e indexação do passivo, do estoque, de defasagens e de outras taxas e preços. Da mesma forma, o bloco fiscal não transforma o primário observado em uma estimativa automática de impulso sobre a demanda agregada.

### Estoques: DBGG, DLGG e DLSP

A DBGG/PIB é mostrada como estoque bruto do Governo Geral segundo a metodologia do BCB. A DLGG/PIB complementa essa leitura ao balancear débitos e créditos do Governo Federal, estados e municípios, permitindo observar a posição líquida dentro do perímetro do Governo Geral.

A DLSP/PIB é mantida separada porque seu perímetro institucional é mais amplo: setor público não financeiro mais Banco Central. Ela também é o conceito de dívida associado à apuração do déficit público "abaixo da linha". Portanto, DLSP não é tratada como simples versão líquida da DBGG.

O painel compara as três séries porque respondem a perguntas distintas, mas não as soma nem transforma suas diferenças em ativos implícitos sem uma reconciliação metodológica explícita. Nenhuma delas é renomeada como DPF.

### Perfil: DPF

Composição, vencimentos em 12 meses, prazo médio, custo e liquidez vêm do RMD do Tesouro Nacional. Esses valores são preservados como publicados. O sistema não calcula um prazo médio simplificado a partir das datas finais dos títulos e não usa Selic corrente como substituto para custo médio do estoque.

Essa escolha mantém a cobertura e a metodologia oficiais visíveis e evita falsa precisão em métricas cujo cálculo depende de detalhes não presentes nas tabelas escalares do painel.

## 18. Setor externo e câmbio

O módulo externo é descritivo. Ele reúne preços relativos, saldos/fluxos do balanço de pagamentos e ativos de reserva sem condensá-los em um score nem atribuir causalidade a partir de co-movimentos.

### USD/BRL

A cotação de venda USD/BRL é observada diretamente. As variações de 30 e 365 dias são derivadas pela comparação com a última observação disponível em ou antes da data-alvo. Valor positivo indica aumento de reais por dólar; isso não é rotulado automaticamente como deterioração econômica, choque fiscal, diferencial de juros ou qualquer causa específica.

### Câmbio real efetivo

O índice de taxa de câmbio real efetiva é exibido como índice. Ele incorpora câmbio nominal e preços relativos de parceiros comerciais, mas o seu nível não é convertido em “valor justo”, taxa de equilíbrio ou recomendação cambial.

### Transações correntes e IDP

Transações correntes em 12 meses/PIB e IDP em 12 meses/PIB são apresentados lado a lado porque usam a mesma escala macroeconômica, mas representam contas distintas. Quando a conta corrente é negativa, o monitor calcula:

```text
cobertura_descritiva = IDP_12m_PIB / abs(transacoes_correntes_12m_PIB) * 100
```

O resultado é apenas uma razão de magnitudes. Não é identidade de financiamento e não permite afirmar que o IDP observado “financiou” mecanicamente o déficit corrente do mesmo período.

### Investimento em carteira

Passivos líquidos de investimento em carteira permanecem na unidade e sinal da fonte. Não são somados ao IDP para formar um indicador proprietário de “fluxo estrangeiro”, pois as categorias obedecem classificações próprias do balanço de pagamentos.

### Reservas

Reservas internacionais no conceito liquidez são estoque de ativos externos disponíveis ao Banco Central. O nível pode ser relevante para resiliência externa, mas o painel não infere uma meta de câmbio, capacidade ilimitada de intervenção ou efeito causal sobre a cotação apenas pelo estoque observado.

### Brasil versus Estados Unidos

Diferenciais nominais e reais de juros só serão construídos na benchmarks dos EUA, após homologação das fontes e transformações americanas. Até lá, a setor externo e câmbio não mistura benchmarks externos improvisados com séries brasileiras oficiais.

## United States benchmark and Brazil–US comparisons

benchmarks dos EUA adds an external monetary-policy benchmark rather than a second policy recommendation engine.

The US classic Taylor benchmark is:

`i = r* + pi + 0.5(pi - pi*) + 0.5(output_gap)`

with `r*=2%` and `pi*=2%` as explicit canonical assumptions. `pi` is realized 12-month PCE inflation. The output gap is `(real GDP / CBO potential GDP - 1) * 100`. The 2% inflation target is the FOMC's longer-run PCE objective; the 2% real neutral rate is only a canonical Taylor assumption and is not labeled as an HLW estimate.

The real policy-rate approximation is `EFFR - realized PCE inflation`, so it is explicitly ex post. Treasury breakeven inflation is a market-implied measure, not a pure inflation forecast.

Brazil–US comparisons include the Selic-minus-EFFR policy-rate differential and, when the Brazilian curve layer has a valid non-extrapolated 10-year proxy, nominal and real 10-year yield differentials. The latter compare instruments constructed differently and therefore do not isolate country risk.

US histories currently use the newest stored revision for BEA/CBO/FRED observations. They are not reconstructed as provider-native real-time vintages; the local vintage layer only uses availability that the monitor can defend.
## Vintages, revisões e look-ahead

`reference_period` responde a que período econômico o número se refere; não responde quando o número era conhecido. Para reconstruções históricas, o monitor usa `available_at` como fronteira de conhecimento. A sequência é obrigatória: primeiro eliminar revisões posteriores ao cutoff; somente depois escolher a revisão mais nova de cada período.

Uma série retroativa coletada hoje não passa a ser conhecida no passado apenas porque contém observações antigas. Quando a fonte não fornece cronologia de publicação/revisão suficientemente confiável, `available_at` permanece a primeira observação pelo monitor. Isso torna alguns cortes antigos incompletos por desenho.

O modo `latest_revision` responde "o que sabemos hoje sobre aquele período?". O modo `as_known` responde "o que este banco consegue defender que estava disponível até aquela data?". Esses conceitos não devem ser comparados sem observar a cobertura de vintage da fonte.

No caso FRED/ALFRED, a API oficial suporta real-time periods e vintage dates, mas exige API key. A coleta V1 permanece no CSV sem chave; assim, os dados americanos acumulam revisões localmente daqui para frente, sem alegar reconstrução ALFRED retroativa.

## Eventos de política monetária e comunicação

A camada de comunicação do Copom trata documentos como **cronologia observável**, não como variável causal ou indicador de sentimento.

O título do comunicado pode fornecer duas propriedades estritamente descritivas: taxa Selic anunciada e direção da decisão (`cut`, `hold`, `hike`) quando a própria redação torna isso explícito. O monitor não classifica o comunicado como hawkish/dovish, não faz análise de sentimento e não infere a motivação da decisão.

Uma linha vertical de Copom sobre o histórico informa que uma decisão ocorreu naquela data. Ela não significa que o evento causou sozinho a variação subsequente de juros, inflação, câmbio ou ativos.

### Disponibilidade e revisões

- comunicado: disponibilidade diária na data oficial da decisão;
- ata: `dataPublicacao` do BCB;
- RPM publicado: data retornada pela API oficial de relatórios publicados;
- agenda do RPM sem timestamp de anúncio: primeira observação local;
- calendário Copom com ato normativo datado: data oficial do ato;
- calendário sem publicação histórica explicitada: primeira observação local.

Mudanças posteriores na representação de um evento geram uma linha em `event_revisions`. A revisão nova recebe como `available_at` o momento em que foi observada, a menos que seja a primeira representação e exista uma data de publicação oficial defensável. Isso impede que correções posteriores apareçam em um corte `as_known` anterior.

Agenda e publicação são conceitos separados. Uma data programada não prova que um documento foi efetivamente publicado; por isso `rpm_schedule` e `rpm_release` nunca são a mesma identidade.


## Exploração analítica

A interface distingue cinco operações cognitivas: **observar**, **decompor**, **comparar**, **testar** e **relacionar**. Essa distinção evita transformar toda correlação visual em explicação econômica.

### Sensibilidade e robustez da Taylor

A Taylor principal continua usando os parâmetros documentados do cenário-base. Alterações de inflação esperada, meta, `r*`, hiato, `alpha`, `beta` ou `rho` são simulações locais. O mapa de sensibilidade não cria cenários probabilísticos: ele apenas recalcula deterministicamente a regra em uma grade de hipóteses.

A regra inercial é exibida separadamente quando `rho > 0` e existe Selic de referência. Ela não substitui a Taylor prospectiva no contrato publicado.

### Relações entre séries

O explorador mensal é descritivo. A normalização para índice 100 usa a primeira data comum após aplicar recorte e defasagem, evitando bases temporais diferentes. A transformação de 12 meses é uma diferença absoluta na unidade original, não taxa percentual genérica.

Uma defasagem escolhida pelo usuário é uma hipótese de timing. Não estabelece direção causal. Por isso a interface não calcula regressões, coeficientes de determinação, causalidade de Granger ou rankings de "explicação" automaticamente.

### Geometria dos gráficos

A forma gráfica acompanha a natureza do dado quando possível: estoques, taxas e índices permanecem linhas; o fluxo mensal de investimento em carteira é mostrado em barras em torno de zero; mudanças da curva são barras em pontos-base. Comparações de unidades distintas usam pequenos múltiplos ou normalização explícita, em vez de eixos Y duplos ajustáveis.

### Resultado fiscal

A conferência `resultado primário + juros nominais -> resultado nominal` usa somente observações com a mesma data de referência e preserva a convenção de sinais da NFSP. Um resíduo é mostrado em vez de ser zerado artificialmente. A relação é contábil/descritiva e não significa que a Selic seja a única determinante dos juros nominais.


Na exploração avançada, `ρ` não usa a Selic corrente implicitamente como `iₜ₋₁`. Quando há histórico suficiente, a interface sugere a última meta Selic distinta anterior à atual como taxa de partida; o valor permanece editável. Se `ρ > 0` e `iₜ₋₁` não estiver disponível, o resultado inercial fica indisponível até o usuário informar explicitamente a taxa de partida.

## 19. Estrutura a termo e expectativas de mercado

A implementação provisória de curvas de mercado separa dois objetos que respondem a perguntas diferentes:

1. **ETTJ ANBIMA** — curva zero-cupom estimada e publicada pela ANBIMA;
2. **DI1 B3** — taxas/preços de ajuste de contratos futuros de DI.

O proxy anteriormente construído com yields de títulos ofertados pelo Tesouro Direto foi removido no Sprint 17C. Vencimentos discretos de títulos com estruturas de cupom distintas não são mantidos como substituto de uma curva zero-cupom ou da PRE/B3 apenas para ampliar cobertura histórica.

A ETTJ passa a ser a referência principal da seção quando disponível. As curvas prefixada, real IPCA e de inflação implícita são ingeridas diretamente dos vértices em dias úteis publicados pela ANBIMA; o monitor não reestima os parâmetros Svensson.

Para comparações históricas da ETTJ, o JSON público conserva apenas vértices constantes de 2, 3, 5, 7 e 10 anos. A base SQLite mantém os pontos recebidos do provedor. Quando um vértice constante não coincide com um ponto publicado, admite-se interpolação linear **somente dentro da faixa observada**, sem extrapolação.

### DI futuro e forwards

O relatório BVBG.187.01 da B3 fornece `AdjstdQt` e `AdjstdQtTax` por contrato DI1. O prazo em dias úteis é recuperado da própria identidade de preço do contrato:

```text
PU = 100000 / (1 + i)^(DU/252)
DU = 252 * ln(100000 / PU) / ln(1 + i)
```

O resultado é arredondado ao dia útil mais próximo. Isso evita introduzir no coletor um calendário de feriados independente da convenção já refletida nos próprios preço e taxa de ajuste.

Para dois contratos com fatores de desconto `D1`, `D2` e prazos `DU1 < DU2`, a taxa forward anualizada é:

```text
f = (D1 / D2)^(252 / (DU2 - DU1)) - 1
```

A interface distingue explicitamente duas leituras. **Taxa até o vencimento** é a taxa DI1 anualizada acumulada de hoje até cada contrato; **taxa entre vencimentos (forward)** isola o intervalo entre dois contratos adjacentes. A primeira é comparada visualmente com a Selic corrente; a segunda é mais adequada para observar segmentos futuros. Ambas são taxas **implícitas nos preços observados**, não previsões puras da Selic. Prêmios de prazo, risco, liquidez e outras condições de mercado podem afastar a precificação da expectativa média de taxa curta futura.

### Inflação implícita

A inflação implícita publicada na ETTJ também é medida de mercado, não previsão pura. O painel não a usa como substituto automático do Focus nem elimina os prêmios incorporados aos instrumentos nominais e reais.

### Continuidade histórica

Enquanto o histórico ANBIMA local for curto, presets sem observação comparável permanecem indisponíveis. O monitor prefere uma lacuna explícita a preencher o período com uma metodologia diferente. Em particular, o diferencial nominal Brasil−EUA de aproximadamente 10 anos permanece indisponível até a adoção da curva PRE/B3 no Sprint 20; a série real pode usar a ETTJ real ANBIMA quando o vértice correspondente estiver disponível.
