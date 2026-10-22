---
id: {id}
title: "{title}"
status: Proposed
feature: "{feature}"
author: {author}
createdAt: {date}
targetVersion: Unreleased
priority: {priority}
---

# Change Request: {title}

<!-- status: Proposed → Approved (só com "aprovado"/"approved" do usuário) → In Progress → Implemented | Rejected.
     Datas e notas vão no corpo, nunca no campo status. -->

## Contexto
O que existe hoje, o que motivou a mudança e quem pediu (com data).

## Mudança proposta
O comportamento novo, em itens verificáveis. Cite FR/SC da feature que mudam (ex.: FR-004 passa a …).

## Impacto
- **Spec:** seções de `features/<feature>/spec.md` alteradas (ou "nenhuma").
- **Contratos / API:** schemas, endpoints, eventos.
- **Dados:** migrations, índices, backfill.
- **Código:** áreas e arquivos principais.
- **Operação:** env, deploy, CI, custos.

## Decisões
- (data, quem) decisão tomada e alternativa descartada.

## Critérios de aceite
- Observáveis e testáveis.

## Tarefas
Feature com `tasks.md`: as tarefas vão numa fase `## Phase N: {id} — …` do `tasks.md` da feature. Sem feature: liste aqui no formato `- [ ] T001 Descrição em caminho/arquivo.ext`.

## Drift report
Preenchido ao concluir: spec ↔ contratos ↔ código conferidos (caminho:linha), testes rodados, `sddkit doctor` limpo.
