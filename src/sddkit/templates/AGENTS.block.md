# Spec-Driven Development

Este repositório segue SDD com GitHub Spec Kit. **Nenhum código de produção sem spec, plano e tarefas.** A especificação é a fonte da verdade; o código deriva dela.

## Fluxo
| Quando | Comando |
|---|---|
| 1× por projeto | `/speckit-constitution <princípios>` |
| Ideia ainda vaga | `/grill-me` (se instalada) — ou `/sdd-feature ... --grill` |
| Feature nova | `/sdd-feature <descrição> --stack <...>` → grill? → specify → clarify → plan → tasks → análise |
| Implementar | `/sdd-build --mvp`, depois `/sdd-build` |

Fases avulsas: `/speckit-specify`, `-clarify`, `-plan`, `-checklist`, `-tasks`, `-analyze`, `-implement`, `-converge`, `-taskstoissues`.
Se a sua ferramenta não aceita `/comando`, leia e siga `.agents/skills/<comando>/SKILL.md`.

## Onde fica cada coisa
- `.agents/skills/` — todas as skills (formato Agent Skills). `speckit-*` são geradas pelo Spec Kit; `sdd-*` são a orquestração; as demais vêm de `sddkit add`.
- `.agents/agents/` — papéis de subagent em formato neutro: núcleo SDD (`sdd-researcher`, `sdd-implementer`, `sdd-analyst`, `sdd-converger`) + especialistas (`ui`, `api`, `data`, `qa`… e revisores `ui-reviewer`, `security-reviewer`). Lista completa no fim deste arquivo.
- `.specify/` — motor do Spec Kit (scripts, templates, `memory/constitution.md`).
- `specs/NNN-slug/` ↔ branch `NNN-slug`: `spec.md` · `plan.md` · `research.md` · `data-model.md` · `contracts/` · `tasks.md` · `analysis.md` · `checklists/`.

## Subagents
- Ferramenta com subagents: delegue ao subagent de mesmo nome do papel, passando **caminhos, não conteúdo**; independentes rodam em paralelo.
- Ferramenta sem subagents: execute o papel você mesmo lendo `.agents/agents/<papel>.md`, em sequência, guardando só o resumo no formato de saída do papel.
- Subagents não criam subagents.
- Roteamento: o `/sdd-build` envia cada tarefa ao especialista cujos `route_globs`/`route_keywords` casam; `[@papel]` na linha da tarefa força. Sem match → `sdd-implementer`.
- Revisores (`kind: reviewer`) não editam código: gravam relatório em `FEATURE_DIR/reviews/` e devolvem tarefas de correção.

## Regras
1. **Constituição primeiro** (`.specify/memory/constitution.md`). Violação só com justificativa em "Complexity Tracking" do plan.md.
2. **Divergência código × spec:** pare e atualize spec → plan → tasks; nunca o contrário em silêncio.
3. **TDD:** em cada história, `### Tests` terminam (e falham) antes de `### Implementation`.
4. **tasks.md bem formado:** `- [ ] T012 [P] [US1] Descrição em caminho/arquivo.ext`. `[P]` só sem arquivo compartilhado nem dependência na fase.
5. **Escrita concorrente:** só o orquestrador edita `tasks.md` e faz commit.
6. **Gates humanos:** aprovar a spec antes do plano; aprovar o MVP antes das demais histórias.
7. **Não edite** `speckit-*` nem `.specify/scripts|templates` — são regenerados pelo Spec Kit. Papéis e skills `sdd-*` são editáveis; depois rode `sddkit sync`.
