# Roadmap — Sprints 18 a 22

A base estabelece módulos por domínio, contrato temporal explícito e metadados públicos estruturados. Os próximos incrementos devem preservar essas fronteiras.


## Sprint 17C — limpeza final antes dos backfills

Concluído antes do Sprint 18:

- referências de `inputs`/`missing_inputs`, `frequency` e `transformation` estruturadas como `{key, label}`, sem nomes internos na UI;
- tabelas analíticas com altura máxima, rolagem e cabeçalho fixo, preservando paginação;
- remoção integral do proxy de curva baseado nos títulos ofertados pelo Tesouro Direto, inclusive coletor, persistência, pipeline e contrato web;
- diferencial nominal Brasil−EUA ≈10a explicitamente indisponível até a PRE/B3 do Sprint 20;
- ETTJ pública da ANBIMA e DI1/BVBG mantidos apenas como capacidades provisórias do domínio de curvas.

## Sprint 18 — semântica temporal e insumos monetários históricos

Concluído:

- backfill oficial dos centros das metas anuais desde 1999 e da meta contínua desde 2025;
- catálogo documental de horizontes relevantes, usando a publicação da ata como fronteira de conhecimento;
- reconstrução do Focus por horizonte para cada vintage disponível no banco, sem colapsar datas da pesquisa;
- `available_at` Focus conservador e distinto de `source_observation_at`;
- hipóteses documentais de taxa real neutra preservadas em degraus;
- hiato migrado de snapshot-paramétrico para série revision-aware com vintages RI/RPM;
- consulta `parameter_for_reference_date()` para selecionar a meta conhecida e aplicável ao horizonte;
- comandos idempotentes `sync-policy-history` e `rebuild-focus-history` para reprocessamento local.

Critério preservado: nenhum ponto histórico pode usar informação cuja disponibilidade seja posterior à data de avaliação.

## Sprint 19 — reconstrução histórica da postura monetária

Concluído:

- inflação esperada histórica preservada pelo Sprint 18 e usada como relógio dos vintages prospectivos;
- juro real ex ante histórico;
- gap monetário real histórico;
- Taylor prospectiva histórica;
- Selic − Taylor histórico;
- frequência semanal defensável, mantendo o último vintage Focus disponível em cada semana;
- *as-of joins* no backend para Selic, taxa neutra, meta aplicável ao horizonte e hiato;
- linhagem dos insumos em cada ponto derivado;
- disponibilidade histórica da primeira versão da meta Selic alinhada à data em que a meta estava publicamente em vigor, sem retroagir correções posteriores do provedor;
- contratos JSON internos simplificados: sem `schema_version` duplicado entre Python e JavaScript, com validação estrutural por `view`/campos obrigatórios;
- carregamento independente dos módulos no frontend, para que falha de um contrato não derrube os demais painéis;
- testes de regressão cobrindo reconstrução temporal, ausência de informação futura e consumo estrutural dos contratos;
- seleção de checkpoints `as_known` preservada sem usar a Selic diária como gatilho de novos bundles; a Selic continua disponível dentro de cada corte, mas sua disponibilidade histórica não multiplica artificialmente centenas de checkpoints estáticos.

A Taylor permanece derivada: dados oficiais/vintages são persistidos; a regra é calculada de forma reproduzível no backend.

## Sprint 20 — curvas de mercado definitivas

- substituir o coletor DI1/BVBG provisório por B3 `TaxaSwap` / PRE;
- validar conteúdo e data de referência antes de persistir;
- backfill histórico retomável, inicialmente validado em amostras de anos distintos;
- calcular forwards a partir dos vértices PRE;
- integrar ANBIMA Feed autenticado quando `ANBIMA_CLIENT_ID/SECRET` estiverem configurados;
- manter capacidade pública corrente sem alegar histórico quando credenciais não existirem;
- separar persistência integral das curvas da publicação web compacta;
- classificar erros: ausência inequívoca de arquivo pode ser `skip`; autenticação, throttling, servidor, transporte e parsing devem falhar explicitamente.

## Sprint 21 — histórico fiscal/Tesouro

- substituir snapshots hard-coded do RMD por séries históricas oficiais;
- usar datasets abertos do Tesouro quando existir série canônica;
- ingerir anexos RMD/XLSX para composição, prazo, custo, vencimentos e liquidez;
- modelar indicadores mensais como `observations`, não `parameters`;
- preservar proveniência de tabela/anexo e metodologia;
- introduzir `openpyxl` somente se ele eliminar parsing OOXML artesanal e frágil.

## Sprint 22 — operação e releases

- scheduler conforme frequência de cada fonte;
- locks e prevenção de execuções concorrentes indevidas;
- atualização incremental e backfills retomáveis;
- health/completeness por fonte;
- retenção de snapshots/vintages;
- backup e restore testados;
- release estático transacional:

```text
web/data/releases/<publication_id>/...
web/data/current.json -> publication_id
```

`current.json` só muda depois de todos os artefatos do release serem gerados e validados. Isso elimina combinações de JSONs pertencentes a gerações diferentes.

## Restrições de arquitetura

- não recriar `pipeline.py` ou `ingestion.py` monolíticos;
- não colocar regra econômica no frontend;
- não inferir disponibilidade histórica sem evidência;
- não publicar grandes matrizes de curvas brutas no browser quando uma visão compacta satisfaz a análise;
- não adicionar framework/dependência sem necessidade concreta e teste correspondente.
