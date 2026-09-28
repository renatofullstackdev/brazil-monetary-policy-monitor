# Modelo de dados e temporalidade

## Regra central

O monitor não possui uma única “data” universal. Uma observação pode representar um período econômico, uma estimativa para um horizonte futuro e um instante posterior em que aquela informação se tornou conhecida.

## Dimensões temporais

### `reference_period`

Período econômico ou alvo da observação. Exemplos:

- Selic em `2026-09-16`;
- IPCA de `2026-08`;
- expectativa Focus para `2028-Q1`.

### `reference_start` / `reference_end`

Limites normalizados do período de referência.

### `source_observation_at`

Data/timestamp atribuído pelo próprio conjunto de dados à estatística ou vintage. Em Focus, é a data da estatística. Ela **não implica**, por si só, disponibilidade pública naquela mesma data.

### `published_at`

Instante/data oficial de publicação quando a fonte permite estabelecê-lo.

### `available_at`

Primeiro instante defensável em que a informação pode ser usada pelo monitor em uma reconstrução *as known*. Pode coincidir com `published_at`, mas não deve ser inferido retroativamente sem evidência.

### `retrieved_at` / `first_seen_at` / `last_seen_at`

Tempos operacionais de coleta. Servem para auditoria e detecção de revisões; não substituem data de publicação.

## Revisões imutáveis

`observations` preserva vintages distintos. `vintage_key` identifica o conteúdo de uma revisão para um determinado `series_id + reference_period`.

Há três perguntas diferentes:

```text
Qual é hoje o melhor valor para cada período?
→ observations_latest()

O que podia ser conhecido até o instante t?
→ observations_as_known(..., knowledge_cutoff=t)

Como a estimativa do mesmo período-alvo evoluiu ao longo das datas da fonte?
→ observation_vintages(..., reference_period=...)
```

A terceira consulta é indispensável para Focus. Duas previsões para `2028-Q1`, uma em 11/09 e outra em 18/09, são dois pontos da evolução da expectativa, ainda que compartilhem o mesmo `reference_period`.

## Séries observadas, pesquisas e estimativas

`data_kind` distingue a natureza epistemológica:

- `observed`: medida publicada/observada;
- `survey`: estatística de pesquisa de expectativas;
- `estimated`: variável não observável estimada por fonte/modelo;
- `derived`: cálculo determinístico do monitor;
- `simulated`: cenário local do usuário, não persistido como dado oficial.

## Parâmetros documentais

`parameters` permanece adequado a regimes ou hipóteses documentais pontuais, como uma hipótese de taxa real neutra usada pelo Copom. O Sprint 18 deverá evitar usar esse modelo para uma variável naturalmente temporal e revisável quando `observations` for semanticamente superior — especialmente o hiato do produto.

## Seleção *as known at the time*

Uma derivação histórica nunca pode usar informação com `available_at > t`.

Para unir frequências diferentes, a regra temporal padrão é:

```text
valor em t = última observação disponível em ou antes de t
```

Nunca se escolhe “a data mais próxima”, pois isso pode incorporar informação futura.

## Focus e horizonte de política

O histórico futuro precisa preservar simultaneamente:

```text
horizonte-alvo          reference_period
vintage da estatística  source_observation_at
conhecimento defensável available_at
```

O cadastro `BR_POLICY_HORIZONS` atual cobre apenas os horizontes já documentados no projeto. O Sprint 18 o substituirá/estenderá por um catálogo documental histórico com proveniência, sem inferência por regra genérica de calendário.

## Meta de inflação

Para a Taylor prospectiva histórica, a seleção da meta deve considerar duas condições distintas:

1. a meta já era conhecida na data de avaliação;
2. a meta é aplicável ao período-alvo da expectativa.

Isso é diferente de simplesmente selecionar “a última meta já vigente em t”.
