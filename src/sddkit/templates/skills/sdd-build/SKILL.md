---
name: sdd-build
description: Implementa o tasks.md da feature atual em ondas de subagents (cada tarefa roteada ao especialista — ui, api, data, qa… — ou ao sdd-implementer), com [P] em paralelo, revisores especialistas por história, commit por onda e verificação independente (sdd-converger) até convergir. Use no lugar de speckit-implement.
argument-hint: "[--mvp | --phase N] [--max-parallel K] [--no-commit]"
---

# /sdd-build

Entrada: `$ARGUMENTS` (padrão: todas as fases, `--max-parallel 4`, com commits).

Você é o **orquestrador**: não escreve código de produção. Coordena, roda testes, marca tarefas, commita e decide.

## Como delegar (qualquer ferramenta)
Papéis em `.agents/agents/<nome>.md`. Com subagents: delegue passando caminhos e dispare a onda inteira em paralelo. Sem subagents: execute cada papel você mesmo, uma tarefa por vez, na ordem da onda.

## Roteamento para especialistas
O `waves.py` devolve, por tarefa, `agent` (papel que executa) e `routed_by` (`tag`, `score=N` ou `fallback`), e em `reviews` os revisores a acionar.
- Tag `[@papel]` na linha da tarefa força o papel.
- Papel inexistente em `.agents/agents/` → use `sdd-implementer` e avise em 1 linha (`sddkit role add <papel>`).
- Roteamento que parece errado (ex.: tarefa de API caiu em `ui`) → adicione a tag `[@papel]` na linha em tasks.md e recalcule; não corrija "de cabeça".

## 1. Preparação
1. `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` → `FEATURE_DIR`.
2. Gate de checklists: siga o passo 2 de `.agents/skills/speckit-implement/SKILL.md` (mostrar a tabela; havendo itens abertos, perguntar antes de seguir).
3. `FEATURE_DIR/analysis.md` ausente ou mais antigo que `tasks.md`? Delegue a `sdd-analyst` antes. `CORRIGIR ANTES` → pare e mostre.
4. Hooks `before_implement` de `.specify/extensions.yml`: siga as regras de "Pre-Execution Checks" da speckit-implement.
5. Passo 4 da speckit-implement (ignore files): faça você mesmo; é setup global.
6. Calcule as ondas:
   `python3 .agents/skills/sdd-build/scripts/waves.py FEATURE_DIR/tasks.md [--mvp|--phase N] --max-parallel K`
7. Mostre o plano em ≤ 8 linhas: nº de ondas, quantas paralelas, distribuição por papel (ex.: `qa×6 ui×4 api×3 sdd-implementer×2`) e revisores previstos. Siga.

## 2. Loop por onda
1. **Despache** cada tarefa ao subagent do seu campo `agent`, com `FEATURE_DIR`, `TASK_ID`, a linha (`desc`), `FILES` e `CONTEXT` (campo `context` do `waves.py`: o subagent lê esse arquivo em vez de `spec.md`/`plan.md` inteiros). Onda paralela → todos ao mesmo tempo (papéis diferentes podem coexistir na mesma onda).
   Tarefa com `files` vazio: deduza os arquivos pela estrutura em `plan.md` e informe-os explicitamente.
2. **Colete** os relatórios (`Txxx OK|FALHOU|BLOQUEADA`). Não releia o código inteiro; verifique por teste.
3. **Verifique** com o comando de testes de `plan.md`, restrito à fase/história quando possível.
   - Onda de **testes** (TDD): os testes novos **devem falhar** pelo motivo esperado. Se passarem, investigue (teste vazio ou funcionalidade já existente).
   - Onda de **implementação**: os testes da história passam e nada que passava antes quebra.
4. **Falhas**:
   - `FALHOU` → relance uma vez com a saída do erro. Falhou de novo → pare a fase e reporte.
   - `BLOQUEADA` por divergência spec/plano → **pare tudo** e leve ao usuário. Nunca resolva contrariando a spec em silêncio.
   - Em onda paralela, tarefas OK ficam; só as falhas são refeitas.
5. **Marque** `- [X]` em tasks.md para cada tarefa OK (só você edita tasks.md).
6. **Commit** (salvo `--no-commit`) em Conventional Commits, para passar no commitlint/`commit-msg`: `git add -A && git commit -m "<tipo>(<NNN>): onda <n> — T0xx, T0yy <resumo>"`, com `tipo` = `test` em onda de testes, `feat` em implementação, `fix` em correções de revisão; cabeçalho em minúsculas, ≤ 100 caracteres, sem ponto final.
7. **Fim de história** (última onda de uma fase `[USn]`): para cada revisor em `reviews` com `at: story` e `USn` em `stories`, dispare-o (em paralelo) com `FEATURE_DIR`, `STORY` e os `files` dele.
   - `APROVADO` → siga.
   - `AJUSTES` → anexe as tarefas CRITICAL/HIGH devolvidas numa fase `## Review fixes (USn)` logo após a fase da história (IDs livres, mantendo `[@papel]`), recalcule as ondas e execute-as antes da próxima história. MEDIUM/LOW ficam no relatório.
   - Máx. 2 ciclos de revisão por história; depois, siga e liste as pendências no relatório final.
8. Checkpoint de fase (`**Checkpoint**` em tasks.md)? Reporte em 1 linha e siga.

## 3. Convergência
1. Em paralelo: `sdd-converger` com `FEATURE_DIR` **e** cada revisor de `reviews` com `at: converge` (ex.: `security-reviewer`) **e**, se `.agents/skills/spec-to-code-compliance/` existir, a checagem de conformidade abaixo (é sua: papéis não criam subagents).
   - **Conformidade spec × código.** Documento: `spec.md` + `contracts/`; código: os arquivos da feature. Se o comando `/spec-to-code-compliance:spec-compliance` existir (plugin instalado), rode-o com esses caminhos. Senão, reproduza o método da skill **em lotes** (economia de tokens): agrupe os FR/SC em lotes de 3–5 que tocam o mesmo código (mesma história, entidade ou endpoint) e mande **um subagent somente leitura por lote** (até `--max-parallel` por vez), seguindo `resources/ANALYSIS_FORMAT.md` e `resources/DIVERGENCE_RUBRIC.md` da skill e devolvendo, **por FR/SC**, veredito (`implemented`, `partial`, `contradicted`, `stronger-than-spec`, `absent`, `undecidable`), linhas lidas e buscas feitas. Contestação só onde importa: veredito `partial`/`contradicted`/`absent` que afeta história P1, segurança, dados pessoais ou dinheiro vai a um segundo subagent, que não o produziu, para tentar refutá-lo (vários desses podem ir no mesmo lote de contestação) — descarte o que cair; os demais entram marcados "não contestado". Grave em `FEATURE_DIR/reviews/spec-compliance.md`. Sem subagents na ferramenta: pule (feita inline, a checagem perde a confiabilidade) e registre no relatório final.
2. Tarefas CRITICAL/HIGH dos revisores e vereditos `partial`/`contradicted`/`absent` da conformidade → anexe ao fim de tasks.md numa fase `## Review fixes (converge)`. `stronger-than-spec`/`undecidable` → liste no relatório como ajustes de spec.
   - `PLANO PENDENTE` (ex.: `sast-scanner`): mostre o plano ao usuário e pergunte. Aprovado → grave-o em `.agents/security/semgrep-plan.json` (linguagens, rulesets, engine, modo, data, quem aprovou) e relance o revisor. Recusado → registre no relatório final.
   - `NÃO EXECUTADO` (ferramenta ausente): não bloqueia; liste no relatório final com o comando de instalação sugerido.
3. `CONVERGED` e revisores `APROVADO` → relatório.
4. Senão → recalcule as ondas (tarefas novas no fim de tasks.md) e repita a seção 2 só para elas. Máx. 3 ciclos; depois, pare e mostre os gaps.
5. A feature criou área nova ou moveu ponto de entrada? Atualize `## Mapa do código` em `.agents/specs/architecture.md` (uma linha por área).
6. Hooks `after_implement`.

## Relatório final (≤ 10 linhas)
Ondas (paralelas/sequenciais) · tarefas por papel · OK / refeitas / bloqueadas · vereditos dos revisores (com caminhos de `FEATURE_DIR/reviews/`) · testes · veredito do converger · conformidade (vereditos por FR/SC ou "não executada") · commits · próximo passo (próxima história, `/speckit-taskstoissues` ou PR).
