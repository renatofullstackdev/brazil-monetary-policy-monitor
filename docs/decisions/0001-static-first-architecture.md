# ADR 0001 — Arquitetura static-first

## Status

Aceito.

## Contexto

O painel agrega fontes oficiais heterogêneas e precisa continuar navegável durante falhas temporárias de provedores. O frontend não precisa executar consultas arbitrárias nem autenticar usuários na V1.

## Decisão

Separar coleta/preparação do consumo. Python coleta e normaliza; SQLite mantém o estado normalizado; um publicador gera JSON estático; HTML/CSS/JavaScript consome apenas esses contratos locais.

## Consequências

Positivas:

- frontend não depende de CORS ou disponibilidade das fontes;
- transformações ficam centralizadas e testáveis;
- dados exibidos podem ser auditados/reproduzidos;
- implantação HTTP é simples.

Negativas:

- atualização não é instantânea;
- é necessário processo de publicação;
- consultas não previstas exigem novo artefato ou evolução arquitetural.

## Alternativas consideradas

### Browser consultando APIs diretamente

Rejeitada porque espalha regras de parsing/revisão no frontend e acopla disponibilidade do painel a terceiros.

### Backend HTTP próprio desde a V1

Rejeitado porque adiciona serviço, implantação e superfície de falha sem requisito atual de consulta dinâmica.
