# ADR 0023 — Usar ETTJ ANBIMA e DI1 B3 como estruturas de mercado separadas

## Status

Superado em parte pelos ADRs 0025 e pelo plano do Sprint 20; mantido como registro da implementação provisória.

## Contexto

A Sprint 8 usa yields dos títulos ofertados pelo Tesouro Direto. Esse conjunto é útil historicamente, mas não constitui uma curva zero-cupom e não deve ser reinterpretado como trajetória esperada da Selic.

A seção de expectativas precisa responder duas perguntas diferentes: qual é a estrutura a termo zero-cupom nominal/real/implícita e o que os preços de contratos de juros de curto prazo embutem para horizontes futuros.

## Decisão

- ingerir diretamente a ETTJ zero-cupom publicada pela ANBIMA;
- ingerir DI1 do relatório público BVBG.187.01 da B3;
- derivar fatores/forwards em módulo de domínio independente dos provedores;
- persistir ambos em `market_curve_points`;
- nunca rotular DI/forwards como expectativa pura da Selic;
- nunca concatenar o proxy legado e a ETTJ como uma única série histórica;
- manter o frontend estático e sem chamadas diretas aos provedores.

## Consequências

O painel ganha uma referência zero-cupom consolidada sem implementar bootstrap/Svensson próprio. A ingestão B3 fica sujeita a mudanças no transporte público, mas essa fragilidade fica isolada no coletor. O histórico ANBIMA começa curto quando usado pela superfície legada de download e deve crescer localmente até que uma fonte histórica explicitamente homologada seja incorporada.


## Superação

A arquitetura greenfield mantém a ETTJ pública da ANBIMA apenas como capacidade corrente sem histórico autenticado e programa a substituição da curva B3 DI1/BVBG por **TaxaSwap/PRE** no próximo incremento de curvas. O ADR 0025 remove também o proxy do Tesouro Direto, em vez de preservá-lo como fallback.
