# Contratos do frontend

## Regra geral

O navegador consome somente arquivos JSON publicados pelo backend. Não chama APIs de BCB, Tesouro, B3, ANBIMA ou FRED diretamente.

Como frontend e publicadores são entregues juntos no mesmo repositório, os contratos internos não usam `schema_version` numérico nem rejeição por versão no navegador. Compatibilidade é verificada pela estrutura efetivamente necessária (`view`, coleções e objetos obrigatórios) e por testes produtor → consumidor. Mudanças estruturais incompatíveis devem atualizar publisher, loader e testes na mesma alteração.

Isso evita duas fontes de verdade — uma versão declarada no Python e outra repetida no JavaScript — sem enfraquecer a validação do formato. Versionamento explícito só deve voltar a ser introduzido se os artefatos passarem a ter consumidores independentes ou ciclos de release distintos.

Isso não remove versões de migração do SQLite nem a versão do manifesto de snapshot bruto: esses formatos persistidos têm ciclo de compatibilidade próprio e não são contratos consumidos pelo frontend.

## Indicador

Um indicador exibível segue, quando aplicável:

```json
{
  "key": "...",
  "label": "...",
  "title": "...",
  "definition": "o que mede",
  "interpretation": "como interpretar",
  "methodology": "como é calculado",
  "caveats": [],
  "inputs": [
    {"key": "br.selic.target", "label": "Meta Selic"}
  ],
  "missing_inputs": [],
  "status": "available",
  "data_kind": "observed",
  "unit": "percent",
  "frequency": {"key": "monthly", "label": "mensal"},
  "transformation": {"key": "identity", "label": "sem transformação"},
  "latest": {},
  "observations": [],
  "source": {}
}
```

Os campos não são sinônimos:

- `definition`: definição objetiva;
- `interpretation`: significado econômico de alta/baixa/distância;
- `methodology`: cálculo/metodologia quando relevante;
- `caveats`: limitações reais;
- `inputs`: referências estruturadas `{key, label}` das dependências de um indicador derivado, estejam disponíveis ou não;
- `missing_inputs`: subconjunto estruturado ainda ausente.

`key` é identificador estável de máquina. `label` é o texto de apresentação curado em português. A mesma regra vale para `frequency` e `transformation`: o backend publica `{key, label}` e a UI exibe somente `label`. Entradas não estruturadas ou metadados sem rótulo curado fazem a publicação/teste falhar; nomes de variáveis, enums e chaves internas nunca são usados como fallback de interface.

O diálogo não usa fallback silencioso `interpretation -> definition -> note`. Se um campo não foi publicado, a seção correspondente não aparece.

## Datas no indicador

Para séries simples, `latest.date` e `observations[].date` continuam sendo o eixo de plotagem. Indicadores com mais de uma dimensão temporal podem explicitar:

```json
{
  "reference_period": "2028-Q1",
  "as_of_date": "2026-09-18",
  "available_at": "2026-09-21T...Z"
}
```

No Focus, `reference_period` é o horizonte previsto; `as_of_date` é a data da estatística. `available_at` controla reconstruções históricas.

## Gráficos e tabelas

O gráfico é a exploração primária. A tabela:

- fica recolhida por padrão;
- usa exatamente o mesmo range temporal selecionado no gráfico;
- mostra valores exatos;
- limita a altura visível e usa rolagem vertical com cabeçalho fixo;
- pagina localmente conjuntos longos;
- não mantém janelas independentes como `slice(-12)` ou `slice(-24)`.

Ranges padrão ficam em um único ponto: `web/js/config.js`.

## Séries de frequências diferentes

O frontend pode apresentar séries com timestamps próprios. Quando uma tabela conjunta precisa associar valores, usa alinhamento *as-of* (último ponto em ou antes da data), nunca “mais próximo”. Derivações econômicas como `Selic − Taylor` devem ser produzidas no backend, onde a regra de alinhamento faz parte da metodologia.

## Ausência de histórico

`latest` não implica histórico. Um indicador pode ter valor corrente e `observations: []` quando a reconstrução histórica não é metodologicamente defensável. O frontend informa a indisponibilidade sem fabricar pontos. No bloco de postura monetária do Sprint 19, as derivações históricas são publicadas semanalmente e cada ponto inclui a linhagem dos insumos usados no respectivo corte de conhecimento.

## Simulações

Simulações do usuário permanecem locais ao navegador e não alteram os contratos publicados nem o SQLite. Valores simulados devem continuar claramente separados de dados observados/estimados.
