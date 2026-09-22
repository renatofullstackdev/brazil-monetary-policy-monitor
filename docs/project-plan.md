# Plano incremental de implementação

## Revisão crítica da especificação

A especificação original é consistente, mas a implementação deve observar cinco refinamentos:

1. **Vintage é requisito estrutural, não um detalhe posterior.** O schema da Sprint 1 deve permitir revisões desde o início; a Sprint 13 será de consolidação da experiência histórica, não de retrofit do banco.
2. **FRED/ALFRED requer configuração de chave em parte de suas APIs.** A escolha da fonte americana deve considerar custo operacional e não pode depender de segredo versionado.
3. **Taxas do Tesouro Direto não equivalem automaticamente a uma curva soberana contínua.** A Sprint de curva deve explicitar cobertura, interpolação e limitações antes de criar 2a/10a sintéticos.
4. **Biblioteca de gráficos não precisa ser decidida na Sprint 0.** A arquitetura fixa o frontend estático; a dependência visual só será escolhida quando houver requisitos concretos de interação e distribuição.
5. **Dados brutos e banco não devem ser versionados indiscriminadamente.** Reprodutibilidade virá de código, metadados, checksums e política de retenção; Git continuará focado em código e documentação.

## Sequência de sprints

### Sprint 0 — Fundação

Escopo:

- repositório;
- documentação-base;
- ADRs;
- pacote Python mínimo;
- testes de sanidade;
- política de Git.

### Sprint 1 — Persistência e proveniência

- SQLite;
- schema versionado;
- `sources`, `series`, `observations`, `parameters`, `events`, `ingestion_runs`;
- semântica inicial de vintage;
- testes de constraints e revisões.

### Sprint 2 — Primeiro pipeline ponta a ponta

- uma ou poucas séries simples do BCB;
- snapshot;
- validação;
- persistência;
- JSON publicado;
- teste de falha sem perda de dados anteriores.

### Sprint 3 — Núcleo monetário

- Taylor clássica;
- Taylor prospectiva com fixture antes do Focus real;
- Taylor inercial;
- juro real;
- gap real;
- decomposição;
- testes numéricos.

### Sprint 4 — Visão geral

- HTML/CSS/JS;
- contrato JSON;
- cards centrais;
- primeiro gráfico histórico;
- metadados e acessibilidade.

### Sprint 5 — Simulador

- quatro controles principais;
- cenário oficial versus simulado;
- restauração;
- decomposição;
- sem persistir simulação.

### Sprint 6 — Focus e horizonte relevante

- coletor OData homologado;
- múltiplos horizontes;
- regras históricas de horizonte relevante;
- Taylor prospectiva real.

### Sprint 7 — Inflação, atividade e trabalho

- IPCA cheio/subjacente/serviços;
- IBC-Br;
- hiato oficial/estimado;
- desemprego/rendimento;
- consumo/FBCF se contratos estiverem estáveis.

### Sprint 8 — Curva

- dados oficiais do Tesouro;
- cobertura de maturidades;
- nominal/real;
- inflação implícita;
- interpolação apenas após validação;
- comparação temporal.

### Sprint 9 — Crédito e condições financeiras

- livre/direcionado;
- taxas;
- indicador composto somente se fonte e metodologia justificarem.

### Sprint 10 — Fiscal

- primário;
- juros nominais;
- nominal;
- DBGG;
- perfil da DPF;
- vencimentos;
- prazo médio;
- liquidez.

### Sprint 11 — Externo e câmbio

- USD/BRL;
- diferenciais;
- transações correntes;
- IDP;
- carteira;
- reservas.

### Sprint 12 — Benchmark EUA

- fontes americanas homologadas;
- taxa básica;
- inflação;
- Taylor;
- juro real;
- Treasury;
- comparação harmonizada.

### Sprint 13 — Experiência de vintages

- `as_known` versus `latest_revision` ponta a ponta;
- validação de ausência de look-ahead;
- comportamento quando uma fonte não possui vintage completo.

### Sprint 14 — Eventos

- Copom/comunicado/ata/RPM;
- anotações nos gráficos;
- equivalentes americanos se úteis.

### Sprint 15 — Navegação por debates

- perguntas orientadoras;
- seleção automática de indicadores;
- sem conclusões normativas automáticas.

### Sprint 16 — Operação

- systemd;
- publicação atômica;
- logs;
- backup;
- recuperação de falhas.

### Sprint 17 — Auditoria metodológica

- revisão de fontes, unidades, fórmulas, labels e comparabilidade.

### Sprint 18 — UX e performance

- redução de ruído;
- mobile;
- acessibilidade;
- payload;
- tempos de carregamento.

## Definition of Done por sprint

- objetivo cumprido;
- testes passam;
- comportamento validado;
- decisões documentadas;
- erros não ocultados;
- mocks não apresentados como reais;
- commits pequenos e explicativos;
- documentação atualizada.
