# ADR 0009 — Usar SVG nativo no primeiro gráfico histórico

## Contexto

A Sprint 4 precisa de apenas um gráfico temporal simples: histórico da Selic e, futuramente, uma segunda linha para a Taylor prospectiva. A arquitetura previa avaliar uma biblioteca de gráficos quando o frontend fosse implementado, com Apache ECharts como candidato.

Adicionar agora uma biblioteca completa criaria uma dependência de runtime e de distribuição antes de existir uma necessidade concreta de curvas múltiplas, zoom avançado, eixos combinados ou visualizações sincronizadas.

## Decisão

Implementar o primeiro histórico em SVG com JavaScript nativo.

O componente fará somente o necessário para a visão inicial:

- escala temporal;
- escala percentual;
- linha em degraus para a meta Selic;
- tooltip por ponteiro;
- filtro de intervalo;
- descrição textual e tabela acessível como alternativas ao gráfico.

Não será criado um framework gráfico genérico interno.

## Consequências

Vantagens:

- nenhuma dependência JavaScript de runtime na Sprint 4;
- frontend pode ser servido integralmente pelo próprio host;
- carregamento e atualização permanecem simples;
- o escopo do código gráfico fica limitado a uma única visualização.

Custos:

- recursos avançados de visualização não são implementados agora;
- o componente poderá ser substituído quando curvas de juros, comparação Brasil–EUA ou gráficos sincronizados justificarem uma biblioteca consolidada.

## Alternativas consideradas

### Apache ECharts desde a Sprint 4

É uma opção adequada para as visualizações mais complexas previstas. Foi adiada porque a primeira tela não precisa ainda da maior parte de sua capacidade. A decisão deve ser reavaliada na Sprint 8, antes de implementar curvas de juros.

### CDN externo

Rejeitado para a V1 inicial porque faria uma página alimentada por JSON local depender de um terceiro para renderizar seu gráfico, contrariando a preferência por disponibilidade estática autônoma.
