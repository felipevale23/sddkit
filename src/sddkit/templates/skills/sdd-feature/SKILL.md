---
name: sdd-feature
description: Pipeline spec-driven de uma feature nova, da ideia até tasks.md revisado — grill (opcional) → speckit-specify → clarify → plan (pesquisa paralela via sdd-researcher) → tasks → análise independente (sdd-analyst) — parando antes de implementar. Use quando o usuário pedir uma feature sem indicar a fase.
argument-hint: "<descrição da feature> [--stack <restrições técnicas>] [--grill | --no-grill] [--auto]"
---

# /sdd-feature

Entrada: `$ARGUMENTS`. Separe a descrição de `--stack ...` e das flags.

Você é o **orquestrador**. Fases interativas (grill, specify, clarify) rodam no seu contexto; pesquisa e revisão rodam em subagents.

## Como delegar (qualquer ferramenta)
Os papéis estão em `.agents/agents/<nome>.md`.
- A ferramenta tem subagents → delegue ao subagent de mesmo nome, passando **caminhos, nunca o conteúdo** dos artefatos. Vários independentes → dispare todos de uma vez, em paralelo.
- Não tem subagents → execute o papel você mesmo, lendo o arquivo do papel, um de cada vez, e mantenha só o resumo no formato de saída dele.

## 0. Pré-condições
- `.specify/memory/constitution.md` ainda tem placeholders (`[PROJECT_NAME]`, `[PRINCIPLE_`)? Pare e peça `/speckit-constitution` primeiro.
- Sem `--stack`: pergunte a stack/restrições agora, numa única rodada junto com outras dúvidas iniciais.

## 1. Grill (afiar a ideia antes da spec)
Rode quando houver `--grill`, ou quando a descrição for vaga (sem usuário-alvo claro, sem resultado observável, ou com mais de uma interpretação plausível). Pule com `--no-grill`.
- Skill `grilling` instalada em `.agents/skills/` → siga-a até a árvore de decisões esvaziar e o usuário confirmar o entendimento comum.
- Não instalada → avise em 1 linha que `sddkit add grill-me` a instala e faça uma rodada curta de perguntas numeradas, cada uma com sua resposta recomendada.
- Saída do passo: um resumo de 5–15 linhas (usuários, problema, escopo dentro/fora, critérios de sucesso, decisões tomadas). Esse resumo é a entrada do passo 2, no lugar da descrição original.

## 2. Specify
1. Escolha o nome curto (2–4 palavras, kebab-case) e o número: `NNN` = maior prefixo em `.agents/specs/features/` + 1 (3 dígitos; `001` se vazio).
2. Invoque `/speckit-specify` com a descrição (ou o resumo do grill), passando `SPECIFY_FEATURE_DIRECTORY=.agents/specs/features/NNN-slug` e `GIT_BRANCH_NAME=NNN-slug`. Sem eles o Spec Kit cria em `specs/`, fora do padrão do projeto.
3. Guarde `FEATURE_DIR` e confira que `.specify/feature.json` aponta para ele.
**Gate humano** (pule com `--auto`): mostre as user stories com prioridades e os critérios de sucesso em ≤ 12 linhas e peça aprovação.

## 3. Clarify
`spec.md` tem `[NEEDS CLARIFICATION`? Invoque `/speckit-clarify` (interativo). Senão, pule.

## 4. Plan — com pesquisa paralela
1. Invoque `/speckit-plan` com a stack.
2. No Phase 0, quando a skill mandar "dispatch research agents": um `sdd-researcher` por incógnita, com `QUESTION`, `FEATURE_DIR` e a stack, todos em paralelo (máx. 6 por vez).
3. Consolide as respostas em `research.md` (Decision / Rationale / Alternatives) e siga para o Phase 1.
4. Confira o "Constitution Check". Violação sem justificativa em "Complexity Tracking" → corrija o plano.

## 5. Tasks
Invoque `/speckit-tasks`. Confira: toda tarefa com ID, caminho de arquivo explícito e `[USn]` nas fases de história; `### Tests` antes de `### Implementation`. Isso é o que permite ao `/sdd-build` paralelizar com segurança.
Rode `python3 .agents/skills/sdd-build/scripts/waves.py <tasks.md>` e confira o campo `agent` de cada tarefa: se o roteamento automático errar, acrescente `[@papel]` na linha (papéis em `.agents/agents/`, ex.: `[@ui]`, `[@api]`, `[@data]`, `[@qa]`).

## 6. Análise independente
Delegue a `sdd-analyst` com `FEATURE_DIR`.
- `PRONTO` → relatório.
- `CORRIGIR ANTES` → corrija os CRITICAL/HIGH nos artefatos (spec → plan → tasks) e rode de novo. Máx. 2 ciclos; persistindo, mostre os itens ao usuário.

## 7. Índice
Rode `sddkit index` (atualiza `.agents/specs/features.md` com a feature nova).

## Relatório final (≤ 10 linhas)
Branch · artefatos · nº de FRs / tarefas / ondas (`python3 .agents/skills/sdd-build/scripts/waves.py <tasks.md> --mvp`) · escopo do MVP · veredito do analyst · próximo passo: `/sdd-build --mvp`.

**Nunca implemente a partir desta skill.**
