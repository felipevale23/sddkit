---
name: sdd-fix
description: Corrige bug achado à mão (depois do /sdd-build ou já em uso) — código que não faz o que já está escrito na spec, no coding-standards, no Mapa do código, no DESIGN.md ou no stack.md. Reproduz com uma checagem que falha, corrige no menor ponto, registra no tasks.md da feature e fecha a brecha que deixou o bug passar. Sem CR. Regra errada ou ausente é /sdd-change.
argument-hint: "<o bug (um ou vários)> [--feature NNN]"
---

# /sdd-fix

Entrada: `$ARGUMENTS`. Você é o **orquestrador**. Bug = o código contraria uma regra **já escrita**. Querer outra regra é mudança: `/sdd-change`.

## 1. Qual regra o código quebra?
Para cada bug, ache a regra que ele viola, com caminho:linha:
- FR/SC em `spec.md` ou `contracts/` da feature;
- `.agents/specs/coding-standards.md`, `## Mapa do código` em `architecture.md` (ex.: arquivo criado fora das pastas existentes), `DESIGN.md` (ex.: cor do tema não aplicada), `stack.md`.

Diga em 1 linha por bug: regra violada · arquivos afetados.
- Nenhuma regra cobre o comportamento, ou a regra está errada → não é bug: tire o item daqui e indique `/sdd-change`. `/sdd-fix` nunca edita requisito, contrato nem regra.

## 2. Feature
`--feature NNN` → `.agents/specs/features/NNN-*/`. Senão, a branch `NNN-slug` atual. Senão, a feature cujo `tasks.md` cita os arquivos afetados; nenhuma ou mais de uma → pergunte. Código fora de qualquer feature → sem `tasks.md`; siga com TDD e commit.

## 3. Registre e reproduza
1. Anexe ao fim do `tasks.md` uma fase `## Phase N: Bug fixes — <resumo>` (N = maior fase + 1), com os próximos IDs livres, `[USn]` da história afetada (os revisores da história voltam a rodar) e `[@papel]` quando o papel for óbvio. Por bug, um par: `- [ ] T0xx [USn] Reproduzir <bug> em caminho/do/teste` e `- [ ] T0xy [USn] Corrigir <bug> em caminho/arquivo.ext`.
2. Reproduza **antes** de corrigir: uma checagem que falha pelo motivo certo. Vale teste unitário ou e2e, e também `tsc --noEmit`, lint ou teste de estrutura (ex.: nenhum componente fora das pastas do Mapa do código). Bug só visual, sem checagem automatizável → escreva os passos de reprodução na tarefa e diga isso no relatório.

## 4. Corrija
- 3+ tarefas → `/sdd-build --phase N` (roteamento, ondas, revisores).
- Menos → delegue ao papel que o `waves.py` escolhe (`python3 .agents/skills/sdd-build/scripts/waves.py FEATURE_DIR/tasks.md --phase N`) ou faça você mesmo. Mudança mínima, no menor ponto responsável; nada de refatorar ao redor.
- Verifique: a checagem do passo 3 agora passa; testes, lint e typecheck do projeto passam. Marque `- [X]`.

## 5. Feche a brecha
O bug passou pelo `/sdd-build` e pelos revisores. Diga em 1 linha por quê e acrescente, no mesmo commit, o que o pegaria da próxima vez:
- checagem que existia mas não rodava (ex.: typecheck fora do build do Vite) → inclua no comando de verificação do `plan.md` e nos scripts do projeto (`package.json`, `Makefile`, CI);
- pasta que existe mas não está no `## Mapa do código` → acrescente a linha da área;
- fato que só vale numa pasta → `sddkit memory add "<fato>" --paths "<glob>"`;
- a checagem do passo 3 fica como teste permanente.
Fechar a brecha exige mudar regra ou requisito → proponha `/sdd-change`; não faça aqui.

## 6. Fechamento
1. Commit convencional: `fix(<NNN>): <resumo>` (sem feature: `fix(<área>)`).
2. Feature já na branch principal → um item por efeito visível em `### Fixed`, sob `## [Unreleased]` do `CHANGELOG.md`. Ainda na branch da feature → sem CHANGELOG.

## Relatório final (≤ 6 linhas)
Por bug: regra violada · checagem que reproduziu (falhou antes, passa agora) · arquivos. Brechas fechadas · itens enviados ao `/sdd-change` · commit.
