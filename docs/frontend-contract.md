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
