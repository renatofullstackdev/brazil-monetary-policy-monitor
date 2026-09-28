# ADR 0025 — Remover o proxy de curva baseado no Tesouro Direto

## Status

Aceito.

## Contexto

A implementação anterior construía vértices constantes a partir das taxas de títulos ofertados no Tesouro Direto. Embora a fonte seja oficial, esses pontos são yields de títulos específicos, com vencimentos discretos e estruturas de cupom distintas. Em anos nos quais o vencimento prefixado mais longo ficava aquém de dez anos, o vértice nominal de 10 anos desaparecia porque a metodologia corretamente proibia extrapolação.

A arquitetura greenfield já adota a ETTJ zero-cupom ANBIMA e prepara a curva PRE da B3 como fonte nominal histórica definitiva. Manter uma terceira metodologia apenas para preencher lacunas aumenta código, persistência e ambiguidade conceitual sem responder melhor à pergunta econômica da seção.

## Decisão

- remover coletor, ingestão, tabela, pipeline, scripts e contratos associados a `tesouro.direto.rates` / `yield_curve_quotes`;
- não usar yields de títulos ofertados como fallback para ETTJ ou PRE;
- manter o RMD e demais fontes fiscais do Tesouro Nacional, que pertencem a outro domínio e não são afetados por esta decisão;
- manter provisoriamente ETTJ pública ANBIMA e DI1/BVBG até o Sprint 20;
- deixar o diferencial nominal Brasil−EUA ≈10a `unavailable` até existir PRE/B3 homologada;
- permitir o diferencial real Brasil−EUA ≈10a apenas quando o vértice real da ETTJ ANBIMA estiver disponível;
- preferir lacuna explícita a extrapolação ou concatenação de metodologias incompatíveis.

## Consequências

O domínio de curvas fica menor e metodologicamente mais claro. Parte do histórico nominal desaparece temporariamente da UI, mas deixa de sugerir continuidade onde a fonte não a oferece. O Sprint 20 passa a ser o único caminho para restaurar o histórico nominal de estrutura a termo por meio da PRE/B3.
