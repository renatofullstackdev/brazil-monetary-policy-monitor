# Modelo de dados e temporalidade

## Regra central

O monitor não possui uma única “data” universal. Uma observação pode representar um período econômico, uma estimativa para um horizonte futuro e um instante posterior em que aquela informação se tornou conhecida.

## Dimensões temporais

### `reference_period`

Período econômico ou alvo da observação. Exemplos:

- Selic em `2026-09-16`;
- IPCA de `2026-08`;
- expectativa Focus para `2028-Q1`;
- hiato estimado para `2026-Q2`.

### `reference_start` / `reference_end`

Limites normalizados do período de referência.

### `source_observation_at`

Data/timestamp atribuído pelo próprio conjunto de dados à estatística ou vintage. Em Focus, é a data da estatística. Para o hiato RI/RPM, identifica a publicação documental que originou o vintage. Ela **não implica**, por si só, que uma estatística Focus estivesse disponível ao público no mesmo instante.

### `published_at`

Instante/data oficial de publicação quando a fonte permite estabelecê-lo.

### `available_at`

Primeiro instante defensável em que o monitor admite o uso da informação em uma reconstrução histórica.

### `retrieved_at` / `first_seen_at`

Momento em que o monitor efetivamente coletou o dado. `first_seen_at` pode provar que uma informação já estava disponível, mas não autoriza retroagir além de evidência defensável.

## Revisões e vintages

Há três consultas diferentes:

```text
última revisão de cada período
→ observations_latest(...)

estado conhecido em uma data histórica
→ observations_as_known(...)

evolução das estimativas do mesmo período-alvo
→ observation_vintages(..., reference_period=...)
```

A terceira consulta é indispensável para Focus e hiato. Duas previsões para `2028-Q1`, ou duas estimativas sucessivas para `2026-Q2`, são vintages distintos mesmo quando compartilham `reference_period`.

## Natureza dos dados

`data_kind` distingue:

- `observed`: medida publicada/observada;
- `survey`: estatística de pesquisa de expectativas;
- `estimated`: variável não observável estimada por fonte/modelo;
- `derived`: cálculo determinístico do monitor;
- `simulated`: cenário local do usuário, não persistido como dado oficial.

## Parâmetros documentais versus séries revisáveis

`parameters` é usado para regimes ou hipóteses documentais com intervalo de aplicabilidade, como meta de inflação e hipótese de taxa real neutra. O hiato do produto não fica em `parameters`: ele é uma estimativa temporal revisável e é persistido em `observations`, preservando cada vintage de RI/RPM.

## Seleção *as known at the time*

Uma derivação histórica nunca pode usar informação com `available_at > t`.

Para unir frequências diferentes, a regra temporal padrão é:

```text
valor em t = última observação disponível em ou antes de t
```

Nunca se escolhe “a data mais próxima”, pois isso pode incorporar informação futura.

## Focus e horizonte de política

O Focus preserva simultaneamente:

```text
horizonte-alvo          reference_period
vintage da estatística  source_observation_at
conhecimento defensável available_at
```

O catálogo `BR_POLICY_HORIZONS` registra apenas mudanças documentadas do horizonte relevante e suas datas de publicação. Não existe regra genérica de calendário para inferir o horizonte. O histórico atualmente coberto começa no horizonte `2026-Q1`, documentado em setembro de 2024, e segue até `2028-Q1`.

O endpoint Focus fornece a data da estatística, mas não o timestamp histórico de cada publicação. Para o backfill, `available_at` usa o menor entre:

1. sete dias corridos depois de `source_observation_at`, como limite conservador compatível com a cadência semanal documentada pelo BCB;
2. `first_seen_at`, quando a coleta local comprova disponibilidade anterior.

Essa regra é uma fronteira de conhecimento, não uma afirmação de que a divulgação ocorreu exatamente sete dias depois.

## Disponibilidade histórica da Selic

Para `br.selic.target` (SGS 432), a primeira versão local de cada data histórica é tratada como a meta que já estava em vigor naquela data. Seu `available_at` é, conservadoramente, o fim do dia de referência, limitado por `first_seen_at` para observações correntes. Uma versão diferente observada posteriormente para a mesma data é revisão do provedor e mantém `available_at = first_seen_at`; ela não é retrodatada.

Essa exceção é específica da semântica da meta Selic em vigor e não é generalizada para outras séries SGS.

## Meta de inflação

O catálogo contém os centros formais das metas anuais desde 1999 e a meta contínua vigente desde janeiro de 2025.

Para a Taylor prospectiva histórica, a seleção deve satisfazer duas condições distintas:

1. a meta já era conhecida na data de avaliação;
2. a meta é aplicável ao período-alvo da expectativa.

`parameter_for_reference_date()` implementa essa distinção. Isso evita usar simplesmente “a última meta já vigente em t” quando o horizonte da expectativa está no futuro.

## Taxa real neutra

Não existe uma série observada de `r*`. O monitor preserva as hipóteses documentadas pelo Copom como regimes em degraus e não interpola entre elas. A cobertura curada começa na hipótese de 4,0% registrada em fevereiro de 2023 e inclui as alterações posteriores para 4,5%, 4,75% e 5,0%.

## Hiato do produto

O hiato é não observável e revisável. Cada edição de RI/RPM é um vintage. Por exemplo, uma estimativa publicada em junho pode ser substituída em setembro para o mesmo trimestre sem apagar o valor que era conhecido em junho.

O Sprint 18 persiste os vintages explicitamente publicados nos RI/RPM de setembro de 2024 a setembro de 2026. O Sprint 19 usa apenas o último vintage disponível em cada data de avaliação e registra no ponto derivado qual vintage foi selecionado.
