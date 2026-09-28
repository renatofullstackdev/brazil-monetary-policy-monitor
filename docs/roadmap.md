## Sprint 17C — limpeza final antes dos backfills

## Sprint 18 — semântica temporal e insumos monetários históricos

- backfill oficial da meta de inflação;
- histórico Focus no horizonte relevante;
- catálogo documental histórico dos horizontes de política;
- vintages documentais da hipótese de taxa real neutra;
- vintages de hiato de RI/RPM, sem aplicar revisões futuras retroativamente;
- distinguir `reference_period`, `source_observation_at`, `published_at` e `available_at`;
- definir explicitamente a meta aplicável a cada horizonte histórico;
- backfills idempotentes, retomáveis e com relatório de completude desde este sprint.

Critério: nenhum ponto histórico pode usar informação cuja disponibilidade seja posterior à data de avaliação.

## Sprint 19 — reconstrução histórica da postura monetária

- inflação esperada histórica;
- juro real ex ante;
- gap monetário real;
- Taylor prospectiva;
- Selic − Taylor;
- frequência semanal defensável para as derivações prospectivas;
- *as-of joins* no backend;
- linhagem dos insumos usada em cada ponto.

A Taylor permanece derivada: dados oficiais/vintages são persistidos; a regra é calculada de forma reproduzível.

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
