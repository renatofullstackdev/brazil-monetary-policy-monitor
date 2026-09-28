# ADR 0016 — Preservar indicadores do RMD como snapshots documentais

## Status

Aceita na Sprint 10.

## Contexto

O módulo fiscal precisa mostrar não apenas fluxo e estoque, mas também características da Dívida Pública Federal como composição, vencimentos, prazo médio, custo e liquidez. Parte dessas métricas poderia ser aproximada a partir de tabelas de títulos e vencimentos, mas a metodologia oficial do Tesouro contém definições próprias e nem todas as informações necessárias estão presentes em uma base simplificada.

## Decisão

Os indicadores de perfil da DPF reportados no Relatório Mensal da Dívida serão registrados como parâmetros documentais versionados, preservando período de referência, publicação, referência da tabela/seção, unidade, metodologia e fonte.

O monitor não reconstruirá prazo médio, custo médio, vencimentos em 12 meses ou reserva de liquidez a partir de proxies quando o valor oficial estiver disponível no RMD.

DBGG seguirá separadamente como série observada do BCB. DBGG e DPF não serão tratadas como a mesma cobertura institucional.

## Consequências

- os números exibidos preservam a metodologia oficial em vez de uma aproximação local;
- revisões futuras podem coexistir por versão;
- a atualização do perfil exige curadoria documental enquanto não houver uma fonte estruturada homologada equivalente;
- o painel não cria um histórico artificial anterior aos snapshots efetivamente incorporados;
- comparações entre DBGG e DPF precisam manter os rótulos de cobertura visíveis.
