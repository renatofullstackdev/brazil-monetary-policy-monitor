# ADR 0026 — Metadados públicos de indicadores exigem rótulos curados

## Contexto

O contrato V3 estruturou `inputs` e `missing_inputs`, mas `frequency` e `transformation` continuaram sendo strings técnicas. O diálogo de metadados acabava exibindo valores como `survey_date` e `compound_12_monthly_focus_medians`, expondo detalhes de implementação e misturando português com identificadores internos.

## Decisão

A partir do contrato V4:

- `inputs` e `missing_inputs` continuam como referências `{key, label}`;
- `frequency` e `transformation` também são publicados como `{key, label}`;
- `key` é estável e voltada a máquina; `label` é texto de apresentação curado em português;
- o publisher rejeita frequência ou transformação sem rótulo público cadastrado;
- o frontend nunca tenta humanizar identificadores substituindo `_` por espaço nem exibe valores técnicos como fallback;
- unidades e naturezas desconhecidas também não usam o identificador interno como fallback visual;
- ressalvas permanecem texto editorial e têm renderização distinta das referências estruturadas de insumos.

## Consequências

Um novo indicador pode ser persistido com identificadores técnicos normalmente, mas não pode ser publicado na interface até que seus metadados de apresentação tenham sido definidos. Isso transforma vazamentos de implementação em falhas detectáveis na publicação/testes, em vez de problemas silenciosos de UX.
