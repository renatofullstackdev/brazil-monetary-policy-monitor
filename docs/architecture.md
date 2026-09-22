# Arquitetura da V1

## 1. Objetivo arquitetural

Manter o sistema pequeno, reproduzível e auditável. A interface precisa continuar disponível mesmo quando BCB, IBGE, Tesouro ou fontes americanas estiverem temporariamente indisponíveis.

A consequência principal é separar **aquisição e preparação** de **visualização**.

```text
┌─────────────────────────────────────────────────────────────┐
│ Fontes oficiais                                             │
│ BCB | IBGE | Tesouro | Federal Reserve | BEA | BLS         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Coleta Python                                               │
│ HTTP -> validação -> snapshot bruto -> parsing              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Normalização                                                │
│ unidades | frequências | datas | proveniência | vintages   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ SQLite                                                      │
│ séries | observações | parâmetros | eventos | ingestões     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Publicação                                                  │
│ JSON estático validado + substituição atômica               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Frontend estático                                           │
│ HTML | CSS | JavaScript | biblioteca de gráficos a definir │
└─────────────────────────────────────────────────────────────┘
```

## 2. Por que não consultar provedores diretamente no navegador

Consultas diretas fariam a disponibilidade do painel depender de várias APIs externas e espalhariam pelo frontend regras de parsing, revisão histórica e conversão de unidades. Isso também dificulta reproduzir o que estava disponível em determinada data.

O navegador deve consumir poucos contratos JSON controlados pelo projeto.

## 3. Por que SQLite

O workload previsto na V1 é de um único processo de atualização, séries macroeconômicas de baixa frequência e leitura publicada como arquivos estáticos. SQLite oferece:

- transações ACID;
- implantação sem serviço adicional;
- backup simples;
- consultas SQL suficientes para séries temporais e vintages;
- caminho de migração para PostgreSQL se concorrência de escrita ou API pública justificarem.

SQLite não será acessado pelo navegador.

## 4. Snapshots brutos

Quando tecnicamente razoável, cada coleta persistirá a resposta original ou um artefato equivalente, acompanhado por metadados e checksum. O objetivo é permitir auditoria de transformações sem depender de o provedor continuar oferecendo exatamente a mesma resposta.

Snapshots não devem ser versionados indiscriminadamente no Git. A política concreta de retenção será definida quando os primeiros coletores forem implementados.

## 5. Temporalidade e vintages

Uma observação pode possuir pelo menos três tempos semanticamente distintos:

- `reference_date`: período econômico a que o valor se refere;
- `published_at`: quando o provedor o tornou público;
- `retrieved_at`: quando nosso pipeline o coletou.

Quando o provedor expuser revisões ou versões, elas devem ser preservadas de forma suficiente para distinguir:

- **latest_revision**: conhecimento atual sobre o passado;
- **as_known**: informação disponível na data escolhida.

A implementação não deve assumir que todas as fontes possuem a mesma semântica de vintage.

## 6. Proveniência

Cada série e cada derivação devem permitir responder:

- qual é a fonte;
- qual o identificador original;
- qual a unidade original;
- qual a unidade normalizada;
- qual a frequência;
- qual transformação foi aplicada;
- qual a classificação epistemológica;
- qual a documentação metodológica relevante.

Classificações iniciais:

- `observed`;
- `survey`;
- `estimated`;
- `derived`;
- `simulated`.

## 7. Separação entre modelo e contexto

A Taylor não absorverá arbitrariamente câmbio, fiscal, crédito ou diferencial externo.

O núcleo do cálculo permanece explícito. Os demais módulos explicam canais de transmissão, condições financeiras, choques e possíveis razões para divergência entre regra simples e política observada.

Essa separação evita transformar o painel em uma regressão opaca calibrada para reproduzir decisões históricas.

## 8. Frontend

A V1 será uma aplicação estática, sem framework JavaScript. O estado será pequeno e explícito: data, vintage, país, intervalo temporal e parâmetros da simulação.

A biblioteca de gráficos será decidida apenas na sprint de frontend. A preferência é por uma biblioteca consolidada e pequena operacionalmente; a decisão deve considerar versionamento, distribuição local versus CDN, acessibilidade e capacidade de séries temporais/curvas.

## 9. Operação

Quando o pipeline existir:

- atualização via `systemd service` + `systemd timer`;
- logs estruturados;
- registro de cada execução em `ingestion_runs`;
- validação antes da publicação;
- publicação atômica dos JSONs;
- falha de uma fonte não apaga dados válidos anteriores.

## 10. Critérios que justificariam evoluir a arquitetura

PostgreSQL ou uma API de aplicação só devem ser considerados se aparecer pelo menos um problema concreto como:

- múltiplos escritores concorrentes;
- consultas públicas arbitrárias;
- usuários/autenticação;
- volume ou latência incompatíveis com publicação estática;
- necessidade de atualizações transacionais remotas.

Framework frontend só deve ser considerado se a complexidade real de estado/componentização superar o custo adicional.
