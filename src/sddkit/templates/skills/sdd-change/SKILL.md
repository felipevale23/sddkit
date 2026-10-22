---
name: sdd-change
description: Mudança em sistema que já existe, do pedido ao CHANGELOG — classifica (Tipo A local × Tipo B estrutural), cria o change request com id sequencial, espera aprovação, atualiza a spec da feature antes do código, implementa (direto ou via /sdd-build), faz o drift report e registra no CHANGELOG. Use para bug, ajuste ou evolução de feature existente; feature nova é /sdd-feature.
argument-hint: "<o que mudar> [--feature NNN] [--auto]"
---

# /sdd-change

Entrada: `$ARGUMENTS`. Você é o **orquestrador**.

## 1. Classifique antes de qualquer coisa
- **Tipo A — local:** bug, ajuste visual, texto, refatoração local, tipagem, filtro/estado, edição de componente. Não altera requisito, API, contrato, evento, schema nem arquitetura.
- **Tipo B — estrutural:** endpoint/integração nova, mudança de contrato, evento, schema, arquitetura ou regra de negócio.
- **Capacidade nova inteira** (novas user stories, nova área do produto) → pare e use `/sdd-feature`.
- Na dúvida, **Tipo B**: revisar à toa custa pouco; pular a revisão de uma mudança estrutural custa caro.

Diga a classificação em 1 linha, com o motivo.

## 2. Tipo A — caminho curto
1. Leia só os arquivos afetados e suas dependências diretas (sem specs amplas, contratos ou CRs).
2. Teste que falha pelo motivo certo → mudança mínima → testes, lint e typecheck do projeto passando.
3. Fim. Sem CR e sem CHANGELOG (o commit convencional basta).

## 3. Tipo B — change request
1. **Contexto:** leia `.specify/memory/constitution.md`, `.agents/specs/architecture.md`, `stack.md`, e da feature afetada (`.agents/specs/features/<NNN-slug>/`) `spec.md` e `tasks.md`. `coding-standards.md` e `design-system.md` só se a mudança tocar código/UI desses temas.
2. **Crie o CR:** `sddkit change new "<título>" --feature <NNN|none>` (gera `.agents/specs/changes/YYYY-MM-DD-slug.md` com o próximo `CHANGE-NNN` livre). Sem o `sddkit` no PATH: copie o frontmatter de um CR existente e use o maior id + 1 — **nunca** reutilize um id.
3. **Preencha** contexto, mudança proposta (citando os FR/SC que mudam), impacto, decisões e critérios de aceite. Mudança que viola a constituição → diga qual princípio e proponha a emenda junto.
4. **Gate humano:** mostre o CR em ≤ 15 linhas e pare. Só siga com "aprovado"/"approved" explícito (`--auto` não pula este gate). Ajustes pedidos → edite e mostre de novo. Recusado → `status: Rejected` e fim.
5. Aprovado → `status: Approved`; registre no CR, em "Decisões", a data e quem aprovou.

## 4. Spec antes do código
1. Atualize `spec.md` da feature: FR/SC alterados ou novos, e uma linha na tabela `## Change History` (crie a seção no fim se não existir): `| CHANGE-NNN | AAAA-MM-DD | resumo |`.
2. Atualize contratos (`contracts/`, schemas, OpenAPI) e, se a arquitetura mudou, `.agents/specs/architecture.md`/`stack.md` — no mesmo commit da mudança.
3. `status: In Progress`.

## 5. Implementação
- **Feature com `tasks.md`:** acrescente ao fim uma fase `## Phase N: CHANGE-NNN — <título>` com tarefas no formato do Spec Kit (`- [ ] T0xx [P] [USn] Descrição em caminho/arquivo.ext`, testes antes da implementação). 3+ tarefas → `/sdd-build --phase N` (roteamento, ondas, revisores e convergência). Menos → implemente você mesmo com TDD.
- **Sem feature (`feature: none`):** tarefas na seção "Tarefas" do CR; implemente com TDD.
- Nunca crie arquivos `tasks-change-*.md` soltos: o histórico de tarefas vive no `tasks.md` da feature.

## 6. Drift report e fechamento
1. Confira cada critério de aceite e cada FR/SC alterado contra o código (caminho:linha), rode testes/lint/typecheck e `sddkit doctor` (seção de specs limpa).
2. Escreva o resultado na seção "Drift report" do CR. Divergência → corrija o código ou volte ao passo 4; nunca ajuste a spec em silêncio para caber no código.
3. `status: Implemented` (data no corpo, não no campo).
4. **CHANGELOG.md** na raiz (crie no formato Keep a Changelog se faltar): sob `## [Unreleased]`, em Added/Changed/Fixed/Removed/Security, um item por efeito visível terminando em `[CHANGE-NNN]`. Nunca reescreva entradas antigas.
5. `sddkit index` (atualiza `.agents/specs/features.md`).
6. Commit convencional citando o CR, ex.: `feat(billing): parcelamento de faturas (CHANGE-043)`.

## Relatório final (≤ 8 linhas)
Tipo · CR (id, caminho, status) · spec/contratos atualizados · tarefas e como rodaram · testes · drift report · CHANGELOG · próximo passo.
