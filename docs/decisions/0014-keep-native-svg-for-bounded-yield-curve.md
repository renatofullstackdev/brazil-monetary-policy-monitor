# ADR 0014 — Manter SVG nativo na Sprint 8 após reavaliar a biblioteca de gráficos

## Contexto

O ADR 0009 adiou a decisão sobre Apache ECharts até a Sprint 8. A curva de juros acrescenta comparação entre datas e três famílias de curva, mas a interação continua delimitada: uma família por vez, no máximo duas datas simultâneas, sem zoom, brush, múltiplos eixos ou sincronização entre vários painéis.

## Decisão

Continuar com um componente SVG específico para a curva de juros e não adicionar ECharts nesta sprint.

O componente não é transformado em framework gráfico genérico. Ele implementa apenas eixos, duas linhas, marcadores e redimensionamento responsivo. A tabela HTML continua sendo alternativa acessível aos pontos interpolados.

## Consequências

A distribuição continua sem dependências JavaScript externas e sem etapa Node/npm. O custo é manter dois componentes SVG específicos. A decisão deve ser revista quando visualizações sincronizadas, múltiplos painéis, zoom ou comparação Brasil–EUA fizerem uma biblioteca consolidada reduzir — em vez de aumentar — a complexidade total.
