# Contrato estático da visão geral

## Objetivo

`web/data/overview.json` é o único contrato de dados publicado consumido pela tela inicial nas Sprints 4 e 5. O navegador não consulta BCB, IBGE, Tesouro ou qualquer outro provedor diretamente.

O contrato existe para desacoplar três responsabilidades:

1. coleta e normalização de dados oficiais;
2. decisão de quais valores estão seguros para publicação;
3. apresentação no navegador.

A interface pode evoluir sem aprender schemas de provedores e uma indisponibilidade upstream não torna a página dependente de uma chamada em tempo real.

## Publicação

O arquivo é gerado com:

```bash
./scripts/publish-overview.sh
```

Fonte padrão:

```text
data/database/monitor.sqlite3
```

Destino padrão:

```text
web/data/overview.json
```

A escrita usa arquivo temporário, `fsync` e `os.replace()`. Assim, o navegador observa o documento anterior completo ou o novo documento completo, nunca JSON parcial.

## Estrutura

Exemplo reduzido:

```json
{
  "schema_version": 1,
  "view": "overview",
  "country": "BR",
  "generated_at": "2026-09-22T12:00:00Z",
  "knowledge_mode": "latest_revision",
  "availability": {
    "status": "partial",
    "available_series": 1,
    "total_series": 9
  },
  "series": {
    "selic": {
      "status": "available",
      "data_kind": "observed",
      "latest": {
        "date": "2026-09-22",
        "value": 15.0,
        "available_at": "2026-09-22T12:00:00Z"
      },
      "observations": []
    },
    "taylor_prospective": {
      "status": "unavailable",
      "data_kind": "derived",
      "required_inputs": [
        "expected_inflation",
        "inflation_target",
        "neutral_real_rate",
        "output_gap"
      ],
      "latest": null,
      "observations": []
    }
  }
}
```

O exemplo acima é estrutural, não um fixture de produção.

## Estados de disponibilidade

Uma série possui `status` igual a:

- `available`: há informação validada e publicável;
- `unavailable`: não há informação suficiente para publicar o indicador com a proveniência exigida.

`unavailable` não é convertido em zero, último valor arbitrário, fixture ou aproximação silenciosa. O campo `required_inputs` informa as dependências ainda ausentes e `note` explica a limitação ao usuário.

Essa regra permite entregar a interface antes de todas as fontes sem contaminar o painel com dados artificiais.

## Natureza dos dados

`data_kind` reutiliza as categorias de proveniência do backend:

- `observed`;
- `survey`;
- `estimated`;
- `derived`;
- `simulated`, reservado para resultados calculados localmente a partir de premissas alteradas pelo usuário.

A Sprint 5 não adiciona séries `simulated` ao JSON. O navegador produz esses valores somente em memória. O contrato continua contendo exclusivamente dados publicados e seus estados de disponibilidade.

## Histórico

Cada série disponível pode expor `observations` como pares de data e valor, além de `available_at`. A interface filtra localmente os períodos 1, 3, 5, 10 anos ou toda a série.

O contrato atual usa `knowledge_mode = latest_revision`. O seletor entre `as_known` e `latest_revision` será implementado posteriormente, depois que houver cobertura de vintages suficiente para tornar a comparação historicamente significativa.

## Compatibilidade

Mudança incompatível do formato exige incremento de `schema_version`. O frontend deve recusar silenciosamente versões desconhecidas? Não: deve exibir erro explícito, pois renderizar um contrato que não entende pode produzir interpretação incorreta dos dados.


## Simulador local da Sprint 5

O simulador reutiliza quatro séries já presentes no contrato como baseline quando disponíveis:

- `expected_inflation`;
- `inflation_target`;
- `neutral_real_rate`;
- `output_gap`.

Se alguma estiver `unavailable`, o respectivo campo inicia vazio. A interface não converte ausência em zero e não injeta fixture, exemplo ou default econômico.

O resultado simulado não altera `overview.json` e não é enviado ao backend. `taylor_prospective` continua significando exclusivamente a série publicada pelo pipeline; a Taylor calculada a partir dos controles é apresentada separadamente como simulação.

## Sprint 6 additions

The overview contract now contains a top-level `policy_horizon` object when a source-backed Brazilian horizon is configured. Its fields include `reference`, `effective_from`, `window_start`, `window_end`, source metadata, and the selection method.

`series.expected_inflation` becomes available only when twelve monthly Focus medians can be composed for the configured horizon. It is classified as `derived`. Its `latest.source_observation_at` identifies the Focus statistic date used for the latest calculation.

The Taylor card remains unavailable until the remaining official/estimated inputs are present. A Focus ingestion must not make the interface imply that `r*`, the inflation target, or the output gap have already been loaded.

## Adições da Sprint 7

O objeto `series` passa a expor, além dos indicadores monetários:

- `ipca_12m`;
- `ipca_core_12m`;
- `ipca_services_12m`;
- `ibc_br_mom`;
- `unemployment_rate`;
- `real_earnings`.

A tela agrupa esses indicadores em **Contexto macroeconômico**, separado das premissas da Taylor. Essa separação é semântica: contexto pode ajudar a investigar a decisão, mas não entra implicitamente na fórmula.

`inflation_target`, `neutral_real_rate` e `output_gap` agora podem vir de registros de `parameters`. Seus metadados mantêm fonte e referência documental. `neutral_real_rate` e `output_gap` continuam `estimated`.

Quando os quatro insumos estão disponíveis, `taylor_prospective.latest` contém o benchmark corrente e sua decomposição. A presença de `latest` não implica histórico: na Sprint 7, `taylor_prospective.observations` permanece vazio enquanto não houver vintages historicamente alinhados de taxa neutra e hiato. A interface informa essa limitação no painel histórico em vez de desenhar uma linha retroativa artificial.

As novas unidades `percent`, `index` e `brl_real` têm formatação própria no navegador. Apenas `percent_per_year` recebe o sufixo visual `a.a.`.
