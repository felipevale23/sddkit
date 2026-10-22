# sddkit

**sddkit prepara um repositório para você construir software com agentes de IA (Claude Code, Codex, Cursor, Copilot, OpenCode, Gemini…) seguindo _Spec-Driven Development_**: primeiro se escreve o que o sistema deve fazer, o agente planeja e quebra em tarefas, e só então o código é escrito — por subagents especialistas, com testes antes, revisores no fim e tudo registrado em arquivos versionados.

Ele não substitui o seu agente: ele **arruma a casa** para que qualquer agente trabalhe do mesmo jeito, com as mesmas regras, no mesmo lugar.

> **Em uma frase:** `sddkit init` uma vez; depois, no agente, `/sdd-feature` para criar, `/sdd-build` para implementar, `/sdd-change` para mudar e `/sdd-audit` para caçar bugs.

---

## Sumário
1. [Os conceitos em 5 minutos](#1-os-conceitos-em-5-minutos)
2. [Instalação](#2-instalação)
3. [Tutorial: seu primeiro projeto, passo a passo](#3-tutorial-seu-primeiro-projeto-passo-a-passo)
4. [Usando num projeto que já existe](#4-usando-num-projeto-que-já-existe)
5. [Receitas do dia a dia](#5-receitas-do-dia-a-dia)
6. [Onde fica cada coisa](#6-onde-fica-cada-coisa)
7. [Subagents especialistas](#7-subagents-especialistas)
8. [Skills: o catálogo](#8-skills-o-catálogo)
9. [Memória, skills de projeto e playbooks](#9-memória-skills-de-projeto-e-playbooks)
10. [Segurança e commits](#10-segurança-e-commits)
11. [O `doctor`: saúde e drift](#11-o-doctor-saúde-e-drift)
12. [Referência de comandos](#12-referência-de-comandos)
13. [Perguntas frequentes](#13-perguntas-frequentes)
14. [Desenvolvendo o sddkit](#14-desenvolvendo-o-sddkit)

---

## 1. Os conceitos em 5 minutos

### Spec-Driven Development (SDD)
Em vez de pedir "faz uma tela de login" e torcer, você segue uma linha de montagem:

```
ideia → spec (o quê e por quê) → plano (como) → tarefas → código (com testes antes) → verificação
```

Cada etapa gera um arquivo. O código **deriva** da spec: se o código e a spec divergem, corrige-se a spec primeiro, nunca o contrário em silêncio. Quem implementa essa linha de montagem é o **[GitHub Spec Kit](https://github.com/github/spec-kit)**; o sddkit instala o Spec Kit e acrescenta o que falta para o dia a dia.

### As peças

| Peça | O que é | Analogia |
|---|---|---|
| **Constituição** | Princípios inegociáveis do projeto ("TDD obrigatório", "LGPD by design"). Todo plano é conferido contra ela. | As regras da casa |
| **Spec** | O que uma feature faz: histórias de usuário, requisitos (FR-001…), critérios de sucesso. Sem tecnologia. | O pedido do cliente |
| **Plano** | Como construir: stack, arquitetura, modelo de dados, contratos de API. | A planta da obra |
| **Tarefas** (`tasks.md`) | Lista ordenada de passos pequenos, cada um com arquivo e teste. | O cronograma |
| **Skill** | Um manual que o agente lê quando a tarefa pede (ex.: "como escrever testes", "padrões de React"). Pasta com `SKILL.md`. | Um livro de receitas |
| **Subagent (papel)** | Um agente especializado com contexto próprio (`ui`, `api`, `qa`, `security-reviewer`…). O agente principal delega a ele. | Um especialista da equipe |
| **Orquestrador** | O agente com quem você conversa. Coordena, não escreve código de produção no `/sdd-build`. | O mestre de obras |
| **Change request (CR)** | Pedido formal para mudar algo que já existe, com aprovação antes do código. | Um aditivo de contrato |
| **`AGENTS.md`** | O arquivo de instruções que todo agente lê ao abrir o projeto. | O manual de boas-vindas |

### Agnóstico de agente
Tudo fica em `AGENTS.md` e na pasta `.agents/`, que Codex, Cursor, Copilot, Amp, Zed e outros já leem sozinhos. Para quem não lê esse formato (Claude Code, OpenCode, Gemini CLI), o sddkit gera **adaptadores**: arquivos derivados, nunca editados à mão. Você troca de ferramenta sem refazer nada.

---

## 2. Instalação

### Pré-requisitos

| Ferramenta | Para quê | Como conferir |
|---|---|---|
| **git** | o projeto precisa ser um repositório | `git --version` |
| **Python ≥ 3.10** | roda o sddkit (só biblioteca padrão) | `python3 --version` |
| **uv** | instala o sddkit e o Spec Kit | `uv --version` · [instalar](https://docs.astral.sh/uv/) |
| **Node.js ≥ 22.20** | instala skills (`npx skills`) | `node --version` |

### Instalar

```bash
uv tool install specify-cli                                      # o Spec Kit
uv tool install git+https://github.com/felipevale23/sddkit       # o sddkit
```

Trabalhando no código do sddkit? `uv tool install --editable ./sddkit`.

Confira: `sddkit --version`.

---

## 3. Tutorial: seu primeiro projeto, passo a passo

Vamos montar um projeto do zero e entregar uma feature. Exemplo: uma API de faturas para uma cooperativa.

### Passo 1 — Preparar o repositório

```bash
mkdir faturas && cd faturas
git init
sddkit init
```

O `init` faz quatro perguntas (Enter aceita o padrão; `-y` pula todas):

1. **Adaptadores** — para quais ferramentas gerar arquivos. Usa Claude Code? Responda `claude`. Só Codex/Cursor/Copilot? `none` basta, eles leem `.agents/` sozinhos.
2. **Stack detectada** — ele olha `package.json`, `pyproject.toml` etc. e mostra o que achou. Projeto vazio = nada detectado, tudo bem.
3. **Subagents especialistas** — os ★ são recomendados para a sua stack. Enter instala os recomendados.
4. **Skills** — idem. As skills vêm de repositórios públicos; as **oficiais** (Anthropic, Vercel, Cloudflare, Trail of Bits) aparecem primeiro, as de **comunidade** com ⚠ para você revisar.

> 💡 Projeto vazio? Escreva o `package.json`/`pyproject.toml` antes do `init`, ou rode `sddkit init` de novo depois: ele detecta a stack e sugere o que faltar, sem apagar nada.

### Passo 2 — Ver o que apareceu

```
faturas/
├── AGENTS.md                 ← instruções que todo agente lê (o sddkit cuida dos blocos dele; o resto é seu)
├── CLAUDE.md                 ← só se escolheu claude: uma linha "@AGENTS.md"
├── .agents/
│   ├── skills/               ← skills: speckit-* (Spec Kit), sdd-* (sddkit), e as que você escolheu
│   ├── agents/               ← os subagents (papéis)
│   ├── specs/                ← TUDO que descreve o sistema (vamos usar muito)
│   │   ├── architecture.md  stack.md  coding-standards.md  design-system.md
│   │   ├── features.md       ← índice gerado automaticamente
│   │   ├── features/         ← uma pasta por feature
│   │   ├── changes/          ← change requests
│   │   ├── playbooks/        ← guias reutilizáveis
│   │   └── audits/           ← relatórios do /sdd-audit
│   └── sddkit.json           ← configuração do sddkit
├── .specify/                 ← o motor do Spec Kit (não mexa; só a constituição é sua)
└── .claude/                  ← gerado para o Claude Code (não edite à mão)
```

Faça o primeiro commit: `git add -A && git commit -m "chore: sddkit init"`.

### Passo 3 — Escrever as regras da casa

Abra o seu agente na pasta do projeto e rode:

```text
/speckit-constitution TDD obrigatório; LGPD by design: CPF nunca em log; APIs REST versionadas em /v1; PostgreSQL como única fonte de verdade
```

Ele escreve `.specify/memory/constitution.md`. Depois, preencha (você ou o agente) `.agents/specs/architecture.md` e `stack.md`: eles vêm com `[PREENCHER` e o `sddkit doctor` avisa enquanto estiverem assim.

> 🧭 Se o agente não aceitar `/comando`, diga: "leia e siga `.agents/skills/speckit-constitution/SKILL.md`". Vale para todos os comandos deste guia.

### Passo 4 — Especificar a primeira feature

```text
/sdd-feature Cooperado baixa a fatura do mês em PDF --stack "Node 22, Express, Prisma, PostgreSQL" --grill
```

O que acontece, na ordem:

| Fase | O que o agente faz | O que você faz |
|---|---|---|
| **Grill** (`--grill`) | Faz perguntas até a ideia ficar clara: quem usa, o que entra e o que fica de fora. | Responde. |
| **Specify** | Cria `.agents/specs/features/001-baixar-fatura/spec.md` e a branch `001-baixar-fatura`. | **Aprova** as histórias e critérios mostrados (1º gate). |
| **Clarify** | Se sobrou ambiguidade (`[NEEDS CLARIFICATION]`), pergunta. | Responde. |
| **Plan** | Escreve `plan.md`, `research.md`, `data-model.md`, `contracts/`. Dúvidas técnicas vão para subagents `sdd-researcher` em paralelo. | — |
| **Tasks** | Gera `tasks.md`: testes antes da implementação, um arquivo por tarefa. | — |
| **Análise** | O subagent `sdd-analyst` confere spec ↔ plano ↔ tarefas ↔ constituição. | Lê o resumo. |

**Nada de código foi escrito ainda.** Revise os arquivos em `.agents/specs/features/001-baixar-fatura/`: esse é o momento barato de mudar de ideia.

> 💡 Sem `--grill`, ele pergunta só se a ideia estiver vaga. `--auto` pula o gate de aprovação da spec (use com cuidado).

### Passo 5 — Implementar

```text
/sdd-build --mvp
```

O `--mvp` constrói só a história mais importante (P1). O orquestrador:

1. Divide as tarefas em **ondas**: tarefas marcadas `[P]` e sem arquivo em comum rodam **em paralelo**.
2. Manda cada tarefa ao **especialista** certo: arquivo `*.test.ts` vai para `qa`, `routes/` vai para `api`, `prisma/` vai para `data`… (detalhes na [seção 7](#7-subagents-especialistas)).
3. Na onda de testes, confere que os testes **falham** pelo motivo certo; na de implementação, que **passam**.
4. Faz um commit por onda (`test(001): onda 1 — T004, T005 …`).
5. No fim da história, chama os **revisores** (ex.: `ui-reviewer` com screenshots). Problemas viram tarefas e são corrigidos antes de seguir.
6. Na **convergência**, o `sdd-converger` confere cada requisito contra o código real, os revisores de segurança olham o diff e a checagem de conformidade spec × código roda requisito por requisito.

Teste o MVP. Gostou? **Aprove** (2º gate) e rode o resto:

```text
/sdd-build
```

> 💡 `--phase 3` roda só uma fase; `--max-parallel 2` limita o paralelismo; `--no-commit` deixa os commits com você.

### Passo 6 — Mudar o que já existe

Dias depois, chegam pedidos. Para **qualquer mudança** em algo que existe:

```text
/sdd-change O PDF da fatura está saindo sem o logo
/sdd-change Fatura passa a aceitar parcelamento em até 3x --feature 001
```

O agente **classifica** antes de agir:

- **Tipo A — local** (o logo): bug, ajuste visual, texto, refatoração local. Não muda requisito, API, contrato, schema nem arquitetura. Ele escreve um teste que falha, corrige e pronto. Sem burocracia.
- **Tipo B — estrutural** (parcelamento): muda regra de negócio, API, schema… Aí o fluxo é:

```
CR criado (CHANGE-001)  →  você aprova ("aprovado")  →  spec da feature atualizada
   →  tarefas numa fase nova do tasks.md  →  /sdd-build daquela fase
   →  drift report no CR  →  CHANGELOG.md  →  índice atualizado
```

O CR fica em `.agents/specs/changes/2026-10-22-parcelamento-de-faturas.md`. A spec ganha uma linha em `## Change History` apontando para ele: daqui a um ano, qualquer um (gente ou agente) entende por que a regra mudou.

> Na dúvida entre A e B, ele escolhe **B**: revisar à toa custa pouco; pular a revisão de uma mudança estrutural custa caro.
> Capacidade **nova** inteira (novas histórias) não é change: é `/sdd-feature`.

### Passo 7 — Conferir a saúde do projeto

```bash
sddkit doctor
```

Mostra ✓/✗ para instalação, constituição, skills recomendadas e **drift**: specs que mentem sobre o código, links quebrados, CRs com id repetido, dependências que a arquitetura não menciona… Cada ✗ vem com a correção sugerida. Detalhes na [seção 11](#11-o-doctor-saúde-e-drift).

### Passo 8 — Caçar bugs de tempos em tempos

```text
/sdd-audit
```

Diferente do `/sdd-build`, que olha só a feature em curso, a auditoria olha **o repositório inteiro** e **não edita nada**:

1. **Checagens determinísticas:** testes, lint, tipos, `sddkit doctor`, vulnerabilidades de dependências e Semgrep (se já houver plano aprovado).
2. **Caça por área:** um subagent somente leitura por pasta/serviço procura defeitos reais (entrada sem validação, erro engolido, corrida, falta de timeout, autorização faltando…). Cada achado traz `arquivo:linha`, o cenário que o dispara e o teste que falharia.
3. **Conformidade:** features já implementadas são conferidas requisito a requisito contra o código.
4. **Contestação:** cada achado grave vai a um segundo subagent que tenta derrubá-lo. Só fica o que resiste.
5. **Relatório** em `.agents/specs/audits/AAAA-MM-DD.md`, comparado com o anterior (novos × resolvidos). O que for estrutural vira CR `Proposed` para você decidir.

`--quick` roda só a parte 1, rápido e sem subagents. Para rodar sozinho toda semana, veja `sddkit ci --audit` na [seção 11](#11-o-doctor-saúde-e-drift).

🎉 Pronto: esse é o ciclo inteiro. Daqui em diante é repetir os passos 4–8.

---

## 4. Usando num projeto que já existe

### Projeto sem SDD
```bash
git checkout -b chore/sddkit
sddkit init                    # detecta a stack pelo código e sugere papéis/skills
```
- O texto que você já tinha no `AGENTS.md` e no `CLAUDE.md` é **preservado**; o sddkit só acrescenta os blocos dele, entre marcadores `<!-- sddkit:… -->`.
- Preencha `architecture.md` e `stack.md` descrevendo o que **já existe**. Com código existente, a skill `improve-codebase-architecture` (sugerida) ajuda a mapear.
- A partir daí: features novas com `/sdd-feature`, mudanças com `/sdd-change`.

### Projeto que já usa Spec Kit
- O `init` **não reinstala** o Spec Kit se `.specify/` existe: mantém sua constituição e templates.
- Specs em `specs/NNN-…` (o padrão do Spec Kit)? Mova as pastas para `.agents/specs/features/` (mantendo os nomes `NNN-slug`); o `doctor` aponta as que ficaram para trás.
- Rode `sddkit doctor --fix`: ele aplica sozinho as correções mecânicas (veja a [seção 11](#11-o-doctor-saúde-e-drift)) e lista o que sobrou. Os itens que sobram pedem julgamento seu: ids de CR duplicados, o que a arquitetura deveria dizer, features sem spec.
- `sddkit index` gera o `features.md`. Se você tinha uma tabela escrita à mão, apague-a: o índice gerado fica entre marcadores e se mantém sozinho.

---

## 5. Receitas do dia a dia

| Eu quero… | Faça |
|---|---|
| afiar uma ideia ainda vaga | `/grill-me` ou `/sdd-feature … --grill` |
| criar uma feature | `/sdd-feature <descrição> --stack <…>` |
| implementar a feature atual | `/sdd-build --mvp`, depois `/sdd-build` |
| corrigir um bug ou ajustar algo | `/sdd-change <o que mudar>` |
| mudar uma regra de negócio ou API | `/sdd-change <…> --feature NNN` (vira CR com aprovação) |
| criar um CR à mão | `sddkit change new "título" --feature 001` |
| ver o estado de features e CRs | abrir `.agents/specs/features.md` (ou `sddkit index` para atualizar) |
| ensinar um fato ao agente | `sddkit memory add "a fila se chama bills"` |
| um fato que só vale numa pasta | `sddkit memory add "use Decimal" --paths "services/billing/**"` |
| registrar um guia para outro projeto | `sddkit playbook new "pipeline assíncrono de arquivos"` |
| ver skills sugeridas para minha stack | `sddkit suggest` |
| instalar uma skill | `sddkit add grill-me` ou `sddkit add owner/repo@skill` |
| adicionar um especialista | `sddkit role list` → `sddkit role add ui` |
| criar um especialista meu | `sddkit role new pix-integrator`, editar, `sddkit sync` |
| forçar um especialista numa tarefa | escrever `[@api]` na linha da tarefa em `tasks.md` |
| commits padronizados e sem atribuição de IA | `sddkit commitlint` |
| passar a usar outra ferramenta | `sddkit sync --agents claude,opencode` |
| atualizar após upgrade do sddkit | `sddkit init` (atualiza o que você não editou; o que editou é mantido e listado) |
| conferir no CI que nada gerado está desatualizado | `sddkit sync --check` |
| saber o que está errado | `sddkit doctor` (`--fix` corrige o mecânico) |
| caçar bugs no repositório inteiro | `/sdd-audit` (`--quick` só o determinístico) |
| checagem a cada PR e auditoria semanal no GitHub | `sddkit ci --audit` |

**Regra de ouro:** você edita arquivos em `.agents/` (e o texto fora dos marcadores no `AGENTS.md`); depois roda `sddkit sync`. Arquivos em `.claude/`, `.opencode/`, `.gemini/` são **gerados** a partir deles. Se alguém editar um gerado, o `sync` **recusa sobrescrever** e avisa, para a edição ir para a fonte (veja a [seção 6](#6-onde-fica-cada-coisa)).

---

## 6. Onde fica cada coisa

| Caminho | Dono | Pode editar? |
|---|---|---|
| `AGENTS.md` fora dos marcadores | você | ✅ |
| `AGENTS.md` entre `<!-- sddkit:… -->` | sddkit (`sync`) | ❌ regenerado |
| `.agents/specs/**` | você | ✅ (o `init` nunca sobrescreve) |
| `.agents/specs/features.md` entre marcadores | sddkit (`index`) | ❌ regenerado |
| `.agents/memory/*.md` | você | ✅ depois `sddkit sync` |
| `.agents/agents/*.md` (papéis) | você (vieram de templates) | ✅ depois `sddkit sync`; o `init` só atualiza papéis que você não editou |
| `.agents/skills/sdd-*` | sddkit (templates) | ✅ o `init` mantém sua edição; `--force-templates` sobrescreve |
| `.agents/skills/speckit-*` | Spec Kit | ❌ |
| `.agents/skills/<outras>` | o autor da skill (`npx skills`) | ❌ atualize com `npx skills update` |
| `.agents/skills/<sua-skill>` | você | ✅ |
| `.agents/hooks/*` | sddkit (templates) | ❌ |
| `.specify/memory/constitution.md` | você (via `/speckit-constitution`) | ✅ |
| `.specify/` (resto) | Spec Kit | ❌ |
| `.claude/`, `.opencode/`, `.gemini/`, `CLAUDE.md` | sddkit (adaptadores) | ❌ exceto conteúdo seu já existente, que é preservado |

### Como a fonte única é garantida
O sddkit guarda em `.agents/sddkit.json` o hash de tudo que gera e de tudo que instala:

- **Gerado editado à mão** (arquivo em `.claude/agents/`, bloco do `AGENTS.md`, índice do `features.md`): o `sync` não sobrescreve. Ele avisa (`⚠ … editado à mão`) e sai com código 1. Leve a edição para a fonte em `.agents/` e rode `sddkit sync`, ou descarte-a com `sddkit sync --force`.
- **Arquivo que já existia** com o mesmo nome de um gerado (ex.: um `.claude/agents/ui.md` seu, de antes do sddkit): nunca é sobrescrito sem `--force`.
- **Gerado que ficou obsoleto** (ex.: papel removido): é apagado, a menos que tenha sido editado.
- **Templates do sddkit** (skills `sdd-*`, hooks, papéis do catálogo): o `sddkit init` atualiza os que você não editou e mantém os editados, listando-os. `--force-templates` substitui todos.
- **Agentes**: no Claude Code, editar `.claude/agents/**`, `.claude/rules/sddkit-memory-*` e `.opencode/agents/**` é negado por permissão. O agente é levado a editar a fonte.
- **CI**: `sddkit sync --check` não escreve nada e falha se algum gerado estiver desatualizado ou editado. Coloque no pipeline:

```yaml
# .github/workflows/sddkit.yml
name: sddkit
on: [pull_request]
jobs:
  sync-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uvx --from git+https://github.com/felipevale23/sddkit sddkit sync --check
```

> Arquivos não são marcados como somente leitura de propósito: o git não guarda essa permissão (um clone volta a ter tudo gravável) e agentes e editores costumam falhar de jeito confuso. O hash + `--check` dá a mesma garantia sem esses efeitos.

### Uma feature por dentro
```
.agents/specs/features/001-baixar-fatura/     ↔ branch 001-baixar-fatura
├── spec.md          o quê e por quê (histórias, FR-xxx, SC-xxx, ## Change History)
├── plan.md          como (stack, estrutura, comandos de teste)
├── research.md      decisões técnicas e alternativas
├── data-model.md    entidades e relações
├── contracts/       API/eventos
├── tasks.md         - [ ] T001 [P] [US1] Descrição em caminho/arquivo.ext
├── analysis.md      relatório do sdd-analyst
├── checklists/      checklists de requisitos
└── reviews/         relatórios dos revisores e da conformidade spec × código
```

### Um change request por dentro
```yaml
---
id: CHANGE-001                 # sequencial, gerado pelo `sddkit change new` (nunca à mão)
title: "Parcelamento de faturas"
status: Proposed               # Proposed | Approved | Rejected | In Progress | Implemented
feature: "001"                 # NNN da feature, ou none
author: Maria
createdAt: 2026-10-22
targetVersion: Unreleased
priority: High
---
```
Corpo: Contexto · Mudança proposta · Impacto (spec, contratos, dados, código, operação) · Decisões · Critérios de aceite · Tarefas · Drift report. Datas e observações vão no corpo, **nunca** no campo `status`.

### Adaptadores
| Ferramenta | Lê sozinha | O que o sddkit gera |
|---|---|---|
| Codex, Cursor, Copilot, Amp, Zed, Kilo, Antigravity, Droid | `AGENTS.md` + `.agents/skills` | nada; sem subagents, o agente executa o papel ele mesmo |
| Claude Code (`claude`) | — | `.claude/skills` → link para `.agents/skills`; `.claude/agents/*.md`; `CLAUDE.md` com `@AGENTS.md`; permissões e hook em `.claude/settings.json` |
| OpenCode (`opencode`) | `AGENTS.md` + `.agents/skills` | `.opencode/agents/*.md` |
| Gemini CLI (`gemini`) | `.agents/skills` | `.gemini/settings.json` lendo `AGENTS.md` |

No Windows, links viram cópias (`--copy`).

---

## 7. Subagents especialistas

Um **subagent** é um agente com contexto limpo e um único trabalho. O orquestrador manda **caminhos** (nunca o conteúdo) e recebe um resumo curto. Vantagens: contexto do principal não incha, tarefas independentes rodam em paralelo e cada especialista já vem com as skills do seu domínio carregadas.

### Núcleo (sempre instalado)
| Papel | Faz |
|---|---|
| `sdd-researcher` | responde uma dúvida técnica do plano (rodam em paralelo) |
| `sdd-implementer` | executa uma tarefa quando nenhum especialista se aplica |
| `sdd-analyst` | confere spec ↔ plano ↔ tarefas ↔ constituição antes de implementar |
| `sdd-converger` | depois de implementar: roda os testes e confere cada requisito no código real |

### Especialistas (`sddkit role add …`)
| Papel | Tipo | Entra quando a tarefa toca… | Skills que carrega (se instaladas) |
|---|---|---|---|
| `ui` | implementa | `*.tsx/.vue/.svelte/.css`, `components/`, `pages/` | frontend-design, vercel-react-best-practices, vercel-composition-patterns, web-design-guidelines, ui-ux-pro-max, apple-design, react, nextjs, tailwindcss, shadcn, mui, tanstack-query, tanstack-router |
| `api` | implementa | `api/`, `routes/`, `services/`, `*.controller.*` | claude-api, express, nodejs |
| `data` | implementa | `migrations/`, `prisma/`, `*.sql`, `models/` | domain-modeling, prisma |
| `qa` | implementa | `### Tests`, `tests/`, `*.test.*`, `e2e/` | tdd, playwright-skill, webapp-testing, route-tester |
| `devops` | implementa | `Dockerfile`, `.github/workflows/`, `*.tf` | setup-pre-commit, deploy-to-vercel |
| `docs` | implementa | `docs/`, `README`, ADRs | domain-modeling |
| `event-module` | implementa | `modules/`, `domain/`, `events/` (lógica pura, sem IO) | property-based-testing |
| `queue-worker` | implementa | `workers/`, `queues/`, `*.worker.ts` | — |
| `bill-parser` | implementa | `parsers/`, `faturas/`, `layouts/` | — |
| `ui-reviewer` | revisa (fim da história) | a história tocou UI | web-design-guidelines, playwright-skill, webapp-testing, apple-design, ui-ux-pro-max |
| `security-reviewer` | revisa (convergência) | sempre, o diff da feature | differential-review, fp-check, variant-analysis |
| `sast-scanner` | revisa (convergência) | sempre (Semgrep) | semgrep, sarif-parsing, fp-check |
| `supply-chain-auditor` | revisa (convergência) | a feature mexeu em dependências | supply-chain-risk-auditor |
| `actions-auditor` | revisa (convergência) | a feature mexeu em `.github/workflows` | agentic-actions-auditor |
| `contract-reviewer` | revisa (convergência) | contratos, filas ou parsers | — |

**Como o especialista é escolhido** (`waves.py`): cada papel tem `route_globs` (arquivos) e `route_keywords` (palavras). A tarefa vai para quem pontuar mais (3× por arquivo que casa + palavras da descrição). Errou? Escreva `[@papel]` na linha da tarefa. Ninguém casou? `sdd-implementer`.

**Revisores** não editam código: gravam relatório em `FEATURE_DIR/reviews/` e devolvem tarefas de correção, que o `/sdd-build` executa antes de seguir.

**Regras que valem para todos:** subagents não criam subagents; o formato de relatório do papel vence skills de estilo (como caveman e ponytail); só o orquestrador edita `tasks.md` e faz commit.

### Criar o seu
```bash
sddkit role new pix-integrator            # ou --kind reviewer
# edite .agents/agents/pix-integrator.md: description, route_globs, route_keywords, skills e o prompt
sddkit sync
```
Formato:
```yaml
---
name: pix-integrator
description: Integra cobranças PIX com idempotência e verificação de webhook.
kind: implementer                      # implementer | reviewer
capabilities: [read, edit, write, shell]
tier: strong                           # fast → modelo rápido · strong → modelo forte
skills: [tdd]                          # pré-carregadas (só as instaladas)
route_globs: ["**/pix/**"]
route_keywords: [pix, cobrança, webhook]
max_turns: 40
---
<instruções do papel>
```

---

## 8. Skills: o catálogo

`sddkit suggest` mostra as skills que combinam com a sua stack, agrupadas pela fase em que ajudam:

| Grupo | Para quê | Skills (★ = instalada por padrão) |
|---|---|---|
| **Starting** | afiar ideias e entender código existente | ★ grill-me · grill-with-docs · domain-modeling · ★ improve-codebase-architecture · planning-with-files |
| **Coding** | padrões de código e frameworks | ★ ponytail · ★ react-best-practices · ★ react-native · ★ mcp-builder · ★ claude-api · Claude Code Kit (`cck-*`): ★ express, ★ nodejs, ★ prisma, ★ tailwindcss, ★ shadcn, ★ mui, ★ tanstack-query, ★ tanstack-router, react, nextjs |
| **UI** | design e interface | ★ frontend-design · web-design-guidelines · impeccable · ★ apple-design · ★ ui-ux-pro-max · theme-factory |
| **Testing** | testes e depuração | ★ tdd · ★ diagnosing-bugs · webapp-testing · ★ playwright · property-based-testing · cck-route-tester |
| **Review** | revisão e verificação | ★ superpowers · ★ spec-to-code-compliance |
| **Security** | segurança | ★ security-review · ★ semgrep · ★ security-audit · ★ supply-chain-risk-auditor · ★ agentic-actions-auditor |
| **Workflow** | git, commits e manutenção | ★ git-guardrails-claude-code · ★ setup-pre-commit · conventional-git · ★ caveman · ★ find-skills · ★ skill-creator · deploy-to-vercel |

Só aparecem as que casam com o projeto: `cck-prisma` só se houver Prisma, `apple-design` só em app mobile/desktop, `security-audit` só com código existente (5+ arquivos).

**Oficial × comunidade.** Skills de publicadores conhecidos (`anthropics`, `vercel-labs`, `cloudflare`, `trailofbits`) aparecem primeiro. As de **comunidade** saem com "⚠ revise antes de usar": uma skill é um texto que o agente obedece, então leia antes de confiar. Skills com efeitos fora do projeto (hooks, download de binário, upload, instalação global) trazem um aviso ⚠ na descrição.

Qualquer skill do ecossistema [skills.sh](https://skills.sh) também funciona: `sddkit add owner/repo@skill`.

---

## 9. Memória, skills de projeto e playbooks

Há quatro jeitos de ensinar algo ao agente. Escolha pelo tamanho e pelo alcance:

| Tenho… | Use | Exemplo |
|---|---|---|
| um fato curto, válido no projeto todo | `sddkit memory add "…"` | "a fila se chama `bills`" |
| um fato curto, válido numa pasta | `sddkit memory add "…" --paths "glob"` | "em `services/billing/**` valores são `Decimal`" |
| um procedimento ou regra com exemplos | uma **skill do projeto** em `.agents/skills/<nome>/SKILL.md` (crie com `/skill-creator`) | "toda query em coleção que cresce sem limite usa cursor e projeção" |
| um guia para reaproveitar em **outro** projeto | `sddkit playbook new "…"` | "pipeline assíncrono de upload → fila → worker → progresso" |
| um princípio inegociável | a **constituição** | "TDD obrigatório" |

- **Memória** vira um bloco no `AGENTS.md`. Com `--paths`, no Claude Code ela só é carregada quando o agente mexe naqueles arquivos, o que mantém o `AGENTS.md` enxuto (o `doctor` avisa acima de 200 linhas).
- **Skill do projeto**: a `description` diz *quando* ela vale ("use ao editar `server/src/repositories/**`"); o agente a carrega sozinho quando a tarefa casa.
- **Playbook**: escrito para ser entregue a um agente num código-base diferente: arquitetura, passo a passo, armadilhas reais e como verificar.

---

## 10. Segurança e commits

| Camada | O que faz | Depende do modelo obedecer? |
|---|---|---|
| **Revisores** | `security-reviewer` (diff, falso positivo, variantes, LGPD, authz), `sast-scanner` (Semgrep), `supply-chain-auditor`, `actions-auditor` na convergência de cada feature | sim |
| **Conformidade** | na convergência, cada requisito da spec é checado no código por um subagent e contestado por outro | sim |
| **Guarda de segredos** | `.agents/hooks/guard_secrets.py` bloqueia escrita de chaves/tokens (AWS, GitHub, Anthropic, OpenAI, Slack, Stripe, Google, chave privada, URL com senha) e CPF/CNPJ válidos; no Claude Code também nega leitura de `.env*`, `*.pem`, `*.key` e chaves SSH | **não** |
| **Commits** | `sddkit commitlint`: hook `commit-msg` com Conventional Commits e bloqueio de atribuição de IA | **não** |

**Guarda de segredos em qualquer ferramenta:** coloque `python3 .agents/hooks/guard_secrets.py --staged` no pre-commit. Falso positivo? Comentário `sddkit:allow-secret` na linha. Fixtures com CPF/CNPJ devem usar dígito verificador **inválido** (ex.: `123.456.789-00`).

**Semgrep:** na primeira vez o `sast-scanner` devolve o plano de varredura para você aprovar; o `/sdd-build` grava a aprovação em `.agents/security/semgrep-plan.json` e não pergunta de novo. Sem o CLI: `uv tool install semgrep`.

### Commits padronizados (`sddkit commitlint`)
```bash
sddkit commitlint            # --no-install para não instalar pacotes npm
```
- **Projeto Node:** instala `@commitlint/cli` + `@commitlint/config-conventional` com o seu gerenciador (npm/pnpm/yarn/bun) e cria `commitlint.config.mjs`, **só se** não houver config. A sua é mantida.
- **Sem Node:** o próprio script exige o formato `tipo(escopo): assunto`.
- **Sempre:** recusa `Co-authored-by` de agentes de IA (Claude, Copilot, Cursor, Codex, Gemini…), "Generated with Claude Code" e `Claude-Session:`. Coautores humanos passam.
- O hook vai para o `.husky/` se existir; senão, para `.githooks/` (cada clone roda `git config core.hooksPath .githooks` uma vez). Hooks existentes são preservados.
- Os commits automáticos do `/sdd-build` já saem nesse formato.
- Complemento natural: a skill `conventional-git` (`sddkit add conventional-git`) ensina o agente a escrever as mensagens certas antes de o hook precisar barrar.

---

## 11. O `doctor`: saúde e drift

```bash
sddkit doctor
```

**Instalação:** Spec Kit, Node, git, `.specify/`, blocos no `AGENTS.md`, tamanho do `AGENTS.md`, `CLAUDE.md` importando `@AGENTS.md`, skills núcleo, papéis, constituição preenchida, adaptadores gerados, papéis e skills recomendados.

**Fonte única:** gerados em dia com `.agents/` (o mesmo que `sync --check`), nenhum gerado editado à mão, templates do sddkit atualizados (e quais você editou).

**Drift** (specs que deixaram de dizer a verdade):

| Checagem | Pega |
|---|---|
| specs só em `.agents/specs/` | pastas esquecidas em `specs/` ou `.specify/specs/` |
| ponteiros do Spec Kit | `.specify/feature.json` ou bloco SPECKIT do `AGENTS.md` apontando para o que não existe |
| referências a arquivos | caminhos citados no `AGENTS.md`, na constituição e nos docs centrais que não existem |
| docs centrais preenchidos | `architecture.md`/`stack.md`/… ainda com `[PREENCHER` |
| dependências de arquitetura | framework, ORM, fila ou SDK no manifesto que não aparece em `architecture.md`/`stack.md` |
| features | pasta sem `spec.md`; `features.md` desatualizado |
| change requests | id duplicado, status fora do padrão, sem `feature:` |

O `doctor` **só lê**: pode rodar à vontade, inclusive no CI. Sai com código 1 se houver pendência.

### `sddkit doctor --fix`
Antes de checar, aplica as correções que não pedem julgamento, e só elas:

| Corrige | Como |
|---|---|
| status de CR com texto extra (`Implemented (2026-09-30, uncommitted)`) | vira `Implemented`; o texto original vai para o corpo do CR |
| CR sem `feature:` | preenche **só** quando o corpo cita exatamente uma pasta de feature existente |
| features em `specs/NNN-…` | move para `.agents/specs/features/` (se o nome não estiver ocupado) |
| `.specify/feature.json` apontando para o nada | corrige se a pasta foi movida; senão apaga (o próximo `/speckit-specify` recria) |
| `CLAUDE.md` sem `@AGENTS.md` (com `.claude/` no projeto) | acrescenta o import |
| índice, arquivos gerados e templates intocados | regenera e atualiza (nunca sobrescreve edição à mão; nunca instala nada novo) |

Fica com você: ids de CR duplicados (commits já citam o id), o que os docs devem dizer, features sem spec. Rodar de novo não muda nada. Faça commit antes e revise com `git diff`.

### No CI: `sddkit ci`
```bash
sddkit ci            # .github/workflows/sddkit.yml
sddkit ci --audit    # + .github/workflows/sddkit-audit.yml
```
- **`sddkit.yml`** (cada push/PR): `sddkit sync --check` **falha** o PR se algum arquivo gerado estiver desatualizado ou editado à mão; `sddkit doctor` roda como relatório (não falha até o projeto zerar as pendências; tire o `continue-on-error` quando quiser que falhe).
- **`sddkit-audit.yml`** (segunda-feira 06:00 UTC, ou à mão em *Actions → sddkit-audit → Run workflow*): o Claude Code ([claude-code-action](https://github.com/anthropics/claude-code-action)) roda o `/sdd-audit --issue` e abre uma **issue** com o relatório. Tem permissão só de leitura no código e de escrita em issues: não faz commit nem push. Requer o secret `ANTHROPIC_API_KEY` no repositório.
- Os arquivos são criados uma vez e são seus: edite à vontade (horário, comandos); `--force` recria.

---

## 12. Referência de comandos

### No terminal
```bash
sddkit init [dir] [--agents claude,opencode,gemini|all|none] [--roles recommended|all|none|ui,api]
                  [--skills recommended|all|none|1,4,grill-me] [-y] [--copy] [--no-speckit] [--no-git] [--force-templates]
sddkit suggest [--json]                       # stack detectada + skills e papéis sugeridos
sddkit add <id…> | owner/repo@skill           # instala skills
sddkit role list | add <papel…> [--no-skills] | remove <papel> | new <nome> [--kind reviewer] | update
sddkit memory add "fato" [-t tópico] [--paths "glob,glob"] [-d "descrição"] | list | rm <tópico> [n]
sddkit change new "título" [--feature NNN|none] [--priority Low|Medium|High|Critical]
sddkit playbook new "nome"
sddkit index                                  # regenera .agents/specs/features.md
sddkit commitlint [--no-install]
sddkit sync [--agents …] [--copy] [--check] [--force]   # regenera AGENTS.md, índice e adaptadores a partir de .agents/
sddkit doctor [--fix]
sddkit ci [--audit] [--force]                  # workflows do GitHub: checagem a cada PR e auditoria semanal
```

### No agente
| Comando | Para | Opções |
|---|---|---|
| `/speckit-constitution <princípios>` | criar/atualizar a constituição | — |
| `/sdd-feature <descrição>` | da ideia ao `tasks.md` revisado | `--stack "…"` · `--grill` / `--no-grill` · `--auto` |
| `/sdd-build` | implementar em ondas com especialistas e revisores | `--mvp` · `--phase N` · `--max-parallel K` · `--no-commit` |
| `/sdd-change <o que mudar>` | mudar algo existente (Tipo A ou CR Tipo B) | `--feature NNN` |
| `/sdd-audit` | caçar bugs no repositório inteiro, sem editar | `--quick` · `--scope <caminho>` · `--features NNN,NNN` · `--issue` |
| `/grill-me` | interrogatório para afiar uma ideia | — |
| `/speckit-specify`, `-clarify`, `-plan`, `-checklist`, `-tasks`, `-analyze`, `-implement`, `-converge`, `-taskstoissues` | fases avulsas do Spec Kit | — |

---

## 13. Perguntas frequentes

**Preciso usar Claude Code?** Não. Qualquer agente que leia `AGENTS.md` funciona. Sem suporte a subagents, o agente executa cada papel ele mesmo, em sequência.

**O agente não reconhece `/sdd-feature`.** Peça: "leia e siga `.agents/skills/sdd-feature/SKILL.md` com: <descrição>".

**O `sync` diz "editado à mão" e não atualizou um arquivo.** Alguém editou um arquivo gerado. Leve a edição para a fonte em `.agents/` e rode `sddkit sync`; se a edição não importa, `sddkit sync --force`.

**Onde o Spec Kit guarda as coisas?** O motor fica em `.specify/` na raiz (é do Spec Kit; não mexa). As features ficam em `.agents/specs/features/`, porque o `/sdd-feature` informa esse caminho ao Spec Kit. Se você rodar `/speckit-specify` direto, passe `SPECIFY_FEATURE_DIRECTORY=.agents/specs/features/NNN-slug`, ou ele cria em `specs/`.

**Posso pular a aprovação de um CR?** Não: o gate do Tipo B existe justamente para mudanças estruturais. Se a mudança é pequena de verdade, ela é Tipo A e não tem CR.

**Uma skill de comunidade é segura?** Ela é um texto que o agente segue, às vezes com scripts. Leia o `SKILL.md` antes. O sddkit marca as de comunidade e avisa quando uma skill instala hooks, baixa binários ou envia dados.

**Como atualizo o sddkit num projeto?** `uv tool upgrade sddkit` e depois `sddkit init`: atualiza skills `sdd-*`, hooks e papéis do catálogo que você **não** editou; os editados são mantidos e listados (o `doctor` também mostra). Para forçar a versão nova neles: `sddkit init --force-templates` (faça commit antes e compare com `git diff`). Specs, memória, constituição e papéis criados com `role new` nunca são tocados.

**O `AGENTS.md` está enorme.** Mova fatos para tópicos com `--paths` (`sddkit memory add … --paths`) e procedimentos para skills do projeto.

---

## 14. Desenvolvendo o sddkit

`tests/test_harness.py` monta projetos de exemplo em pastas temporárias (vazio; Node com React, Express, Prisma, Tailwind e shadcn; Python; Husky com commitlint; specs com drift no estilo de um projeto real) e roda o `sddkit` de verdade contra eles. Confere o resultado de cada comando, que rodar de novo não muda nada (`init` e `sync` são idempotentes, `doctor` não escreve) e commits reais aceitos ou recusados pelo hook.

```bash
python -m pytest tests -q                 # offline, ~3 s; roda no CI a cada push
SDDKIT_E2E=1 python -m pytest tests -q    # + Spec Kit, npx skills e npm commitlint de verdade
```

Todo bug achado vira um caso marcado com `regressão:` no teste. Para conferir que um teste pega o bug, reintroduza o defeito e veja-o falhar.

O catálogo de skills fica em `src/sddkit/catalog.json` (fonte, skills, grupo, quando sugerir, recomendada ou não); os templates de skills, papéis e specs em `src/sddkit/templates/`.
