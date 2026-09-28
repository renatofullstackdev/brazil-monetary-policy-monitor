# ADR 0029 — Validar contratos estáticos internos pela estrutura, não por versão duplicada

## Status

Aceito no Sprint 19.

## Contexto

O Sprint 18 elevou o `overview` para `schema_version: 5`, mas o loader JavaScript continuou aceitando somente a versão 4. Publisher e frontend estavam no mesmo repositório e eram entregues juntos, porém mantinham números de versão independentes. Os testes validavam cada lado isoladamente e não detectaram a incompatibilidade; o erro no `overview` abortava o bootstrap e fazia módulos independentes parecerem sem dados.

## Decisão

- Contratos JSON consumidos apenas pelo frontend deste repositório deixam de publicar e validar `schema_version` numérico.
- Cada loader valida `view` e os campos estruturais mínimos que realmente consome.
- Publisher, loader e testes de uma mudança estrutural devem ser alterados atomicamente.
- A suíte inclui teste produtor → consumidor que carrega os JSONs publicados atuais com os loaders JavaScript reais.
- Os módulos do frontend são carregados com isolamento de falhas; um contrato inválido degrada o painel correspondente sem impedir os demais.
- Versões de migração do SQLite e do manifesto bruto de snapshots permanecem, pois são formatos persistidos/auditáveis com ciclo de compatibilidade próprio e não contratos internos do navegador.

## Consequências

- Elimina-se a dupla fonte de verdade que causou a regressão 4/5.
- Uma mudança incompatível passa a falhar por estrutura efetivamente usada, não por constante esquecida.
- O frontend continua rejeitando contratos malformados.
- Versionamento explícito pode ser reintroduzido se surgirem consumidores externos ou ciclos de release independentes.
