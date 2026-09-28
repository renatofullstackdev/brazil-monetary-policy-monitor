# ADR 0022 — Orientar a interface por perguntas analíticas

## Contexto

A construção incremental por sprints produziu módulos tecnicamente consistentes, mas com peso visual semelhante e textos concentrados em inventário de dados e ressalvas metodológicas. Isso fazia a página refletir a ordem de implementação mais do que o processo de raciocínio do usuário.

## Decisão

A interface principal será organizada por perguntas econômicas. Cada seção deve, nessa ordem, explicar por que a pergunta importa, apresentar uma síntese factual quando ela puder ser derivada sem julgamento normativo e oferecer exploração proporcional à pergunta.

Detalhes metodológicos, tabelas completas, parâmetros avançados e cronologias extensas usam divulgação progressiva. Relações entre séries são uma ferramenta separada, com transformações explícitas, alinhamento mensal e defasagem controlada pelo usuário. Unidades distintas usam pequenos múltiplos ou índice 100 comum; eixo Y duplo não é o padrão.

A interface não cria score agregado de pressão monetária, semáforos, regressões automáticas, classificação de comunicação ou recomendações de política. A profundidade analítica deve vir de decomposição, sensibilidade e comparação auditável.

## Consequências

- a página fica menos dependente da ordem histórica das sprints;
- adicionar uma nova série exige justificar qual pergunta ela ajuda a investigar;
- o usuário comum vê menos controles simultâneos, enquanto o analista mantém acesso a parâmetros avançados;
- relações visuais permanecem explicitamente descritivas;
- novos contratos de dados não são necessários para a Sprint 15.
