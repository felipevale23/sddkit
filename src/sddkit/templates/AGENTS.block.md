# Spec-Driven Development

Este repositório segue SDD com GitHub Spec Kit. **Nenhum código de produção sem spec, plano e tarefas.** A especificação é a fonte da verdade; o código deriva dela.

**Classifique toda tarefa primeiro:** Tipo A (local: bug, ajuste visual, texto, refatoração local — não muda requisito, API, contrato, evento, schema nem arquitetura) segue direto com teste; Tipo B (estrutural) exige change request aprovado. Na dúvida, Tipo B.

## Fluxo
| Quando | Comando |
|---|---|
| 1× por projeto | `/sdd-stack <o que o projeto é>` (grill da stack → `.agents/specs/stack.md`; depois `sddkit init` de novo) e `/speckit-constitution <princípios>` |
| Ideia ainda vaga | `/grill-me` (se instalada) — ou `/sdd-feature ... --grill` |
| Feature nova | `/sdd-feature <descrição> --stack <...>` → grill? → specify → clarify → plan → tasks → análise |
| Implementar | `/sdd-build --mvp`, depois `/sdd-build` |
| Mudar o que já existe (bug, ajuste, evolução) | `/sdd-change <o que mudar>` → Tipo A direto · Tipo B: CR → aprovação → spec → código → drift report → CHANGELOG |
| Caçar bugs no repositório inteiro (periódico, antes de release) | `/sdd-audit` → checagens determinísticas + subagents por área + conformidade spec × código → relatório em `.agents/specs/audits/` e CRs propostos (não edita código) |

Fases avulsas: `/speckit-specify`, `-clarify`, `-plan`, `-checklist`, `-tasks`, `-analyze`, `-implement`, `-converge`, `-taskstoissues`.
Se a sua ferramenta não aceita `/comando`, leia e siga `.agents/skills/<comando>/SKILL.md`.

## Onde fica cada coisa
- `.agents/skills/` — todas as skills (formato Agent Skills). `speckit-*` são geradas pelo Spec Kit; `sdd-*` são a orquestração; as demais vêm de `sddkit add`.
- `.agents/agents/` — papéis de subagent em formato neutro: núcleo SDD (`sdd-researcher`, `sdd-implementer`, `sdd-analyst`, `sdd-converger`) + especialistas (`ui`, `api`, `data`, `qa`… e revisores `ui-reviewer`, `security-reviewer`). Lista completa no fim deste arquivo.
- `.specify/` — motor do Spec Kit (scripts, templates, `memory/constitution.md`).
- `.agents/specs/` — specs do projeto (índice em `.agents/specs/features.md`, gerado por `sddkit index`):
  - `architecture.md` · `stack.md` · `coding-standards.md` · `design-system.md` — docs centrais; leia antes de planejar e atualize no mesmo commit da mudança.
  - `features/NNN-slug/` ↔ branch `NNN-slug`: `spec.md` · `plan.md` · `research.md` · `data-model.md` · `contracts/` · `tasks.md` · `analysis.md` · `checklists/`.
  - `changes/YYYY-MM-DD-slug.md` — change requests `CHANGE-NNN` (`sddkit change new`); status: Proposed · Approved · Rejected · In Progress · Implemented.
  - `playbooks/` — guias reutilizáveis (`sddkit playbook new`).

## Subagents
- Ferramenta com subagents: delegue ao subagent de mesmo nome do papel, passando **caminhos, não conteúdo**; independentes rodam em paralelo.
- Ferramenta sem subagents: execute o papel você mesmo lendo `.agents/agents/<papel>.md`, em sequência, guardando só o resumo no formato de saída do papel.
- Subagents não criam subagents.
- Roteamento: o `/sdd-build` envia cada tarefa ao especialista cujos `route_globs`/`route_keywords` casam; `[@papel]` na linha da tarefa força. Sem match → `sdd-implementer`.
- Revisores (`kind: reviewer`) não editam código: gravam relatório em `FEATURE_DIR/reviews/` e devolvem tarefas de correção.
- O formato de saída definido no papel vence skills de estilo (ponytail, caveman): o resumo volta ao orquestrador exatamente nesse formato.
- Dentro do `/sdd-build`, revisão vem dos revisores do sddkit e do `sdd-converger`: não dispare `requesting-code-review` por tarefa. `using-git-worktrees` e `finishing-a-development-branch` só depois da convergência, sobre a branch `NNN-slug` da feature.

## Regras
1. **Constituição primeiro** (`.specify/memory/constitution.md`). Violação só com justificativa em "Complexity Tracking" do plan.md.
2. **Divergência código × spec:** pare e atualize spec → plan → tasks; nunca o contrário em silêncio.
3. **TDD:** em cada história, `### Tests` terminam (e falham) antes de `### Implementation`.
4. **tasks.md bem formado:** `- [ ] T012 [P] [US1] Descrição em caminho/arquivo.ext`. `[P]` só sem arquivo compartilhado nem dependência na fase.
5. **Escrita concorrente:** só o orquestrador edita `tasks.md` e faz commit.
6. **Gates humanos:** aprovar a spec antes do plano; aprovar o MVP antes das demais histórias; aprovar o CR ("aprovado"/"approved") antes de código Tipo B.
7. **Não edite** `speckit-*` nem `.specify/scripts|templates` — são regenerados pelo Spec Kit. Papéis e skills `sdd-*` são editáveis; depois rode `sddkit sync`.
