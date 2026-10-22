# sddkit

CLI que monta **Spec-Driven Development** (GitHub Spec Kit) num repositório de forma **agnóstica de agente**: tudo vive em `AGENTS.md` + `.agents/`, e adaptadores finos projetam isso para as ferramentas que ainda não leem esse layout.

## Instalação
```bash
uv tool install specify-cli          # motor do Spec Kit
uv tool install ./sddkit             # ou: uvx --from git+https://github.com/<org>/sddkit sddkit init
```
Requer Python ≥ 3.10 (só stdlib) e, para instalar skills, Node.js ≥ 22.20 (`npx skills`).

## Comandos
```bash
sddkit init [dir] [--agents claude,opencode,gemini|all|none] [--roles recommended|all|none|ui,api] [--skills recommended|all|none|1,4,grill-me] [-y] [--copy]
sddkit suggest [--json]                 # detecta a stack e sugere skills
sddkit add grill-me tdd                 # instala do catálogo
sddkit add owner/repo@skill             # qualquer skill do ecossistema skills.sh
sddkit role list                        # subagents especialistas do catálogo
sddkit role add ui ui-reviewer          # instala o papel + skills que ele usa (se casam com a stack)
sddkit role new pix-integrator          # esqueleto de papel próprio
sddkit role remove docs
sddkit role update                      # reaplica os templates do catálogo aos papéis instalados
sddkit memory add "fato" [-t tópico] [--paths "glob,glob"] [-d "descrição"]
sddkit memory list [-t tópico]
sddkit memory rm <tópico> [n]
sddkit sync [--agents ...] [--copy]     # regenera AGENTS.md + adaptadores após editar .agents/
sddkit doctor                           # checa instalação, constituição e skills recomendadas
```

## O que `init` cria
```
AGENTS.md                     ← instruções (blocos <!-- sddkit --> gerenciados; o resto é seu)
.agents/
  skills/                     ← fonte única de skills (padrão Agent Skills)
    speckit-*/                  geradas pelo Spec Kit (integração generic) — não editar
    sdd-feature/                pipeline: grill → specify → clarify → plan → tasks → análise
    sdd-build/                  ondas paralelas de implementação + convergência (scripts/waves.py)
    grill-me/ grilling/ ...     sugeridas e instaladas via `npx skills -a universal`
  agents/                     ← papéis de subagent em formato neutro
    sdd-researcher.md  sdd-implementer.md  sdd-analyst.md  sdd-converger.md   (núcleo)
    ui.md  ui-reviewer.md  api.md  data.md  qa.md  security-reviewer.md ...  (especialistas)
  sddkit.json                 ← adaptadores, modo link/cópia, arquivos gerados
.specify/  specs/             ← motor e artefatos do Spec Kit
skills-lock.json              ← hashes das skills de terceiros (do `npx skills`)
```

### Adaptadores
| Ferramenta | Lê nativamente | O que o adaptador gera |
|---|---|---|
| Codex, Cursor, Copilot, Amp, Zed, Kilo, Antigravity, Droid | AGENTS.md + `.agents/skills` | nada; subagents caem no fallback do AGENTS.md (papel executado inline) |
| Claude Code (`claude`) | — | `.claude/skills` → symlink para `.agents/skills`; `.claude/agents/*.md` traduzidos; `CLAUDE.md` com `@AGENTS.md`; permissões em `.claude/settings.json` |
| OpenCode (`opencode`) | AGENTS.md + `.agents/skills` | `.opencode/agents/*.md` (`mode: subagent`, `permission`) |
| Gemini CLI (`gemini`) | `.agents/skills` | `.gemini/settings.json` com `context.fileName: ["AGENTS.md", ...]` |

Arquivos dos adaptadores são **gerados**: edite `.agents/` e rode `sddkit sync`. O que o usuário já tinha (skills próprias em `.claude/skills/`, conteúdo de `CLAUDE.md`/`AGENTS.md`, chaves de settings) é preservado.

### Formato neutro de papel (`.agents/agents/*.md`)
```yaml
---
name: sdd-analyst
description: ...
capabilities: [read, shell, write]   # read | write | edit | shell | web
tier: strong                         # fast → sonnet / strong → opus (Claude); OpenCode herda o modelo
skills: [speckit-analyze]            # pré-carregadas onde a ferramenta suporta
max_turns: 40
---
<prompt do papel>
```

## Memória do projeto
Fatos e convenções que todo agente deve saber, versionados em `.agents/memory/<tópico>.md` (um fato por linha; editável à mão — depois `sddkit sync`).

| Tipo | Onde aparece | Claude Code | Demais ferramentas |
|---|---|---|---|
| Global (sem `--paths`) | bloco "Memória do projeto" no `AGENTS.md` | via `@AGENTS.md`, toda sessão | toda sessão |
| Por área (`--paths`) | ponteiro no `AGENTS.md` | `.claude/rules/sddkit-memory-<tópico>.md` com `paths:` — carrega só ao tocar esses arquivos | leem o arquivo quando o ponteiro manda |

Constituição ≠ memória: a constituição (`/speckit-constitution`) traz **princípios** que viram gate no plano; a memória traz **fatos e armadilhas** ("a fila se chama `bills`", "Energisa mudou o layout em 2024-03"). Prefira `--paths` para manter o `AGENTS.md` abaixo de 200 linhas (o `doctor` avisa).

## Subagents especialistas pré-definidos
| Papel | Tipo | Modelo | Entra quando | Skills pré-carregadas (se instaladas) |
|---|---|---|---|---|
| `ui` | implementer | strong | `*.tsx/.vue/.svelte/.css`, `components/`, `pages/`, `app/**/page.*`, "tela", "componente"… | frontend-design, vercel-react-best-practices, vercel-composition-patterns, web-design-guidelines, ui-ux-pro-max, apple-design, react, nextjs, tailwindcss, shadcn, mui, tanstack-query, tanstack-router |
| `ui-reviewer` | reviewer (fim da história) | strong | a história tocou arquivos de UI | web-design-guidelines, playwright-skill, webapp-testing, apple-design, ui-ux-pro-max |
| `api` | implementer | fast | `api/`, `routes/`, `services/`, `*.controller.*`, "endpoint", "webhook"… | claude-api, express, nodejs |
| `data` | implementer | fast | `migrations/`, `prisma/`, `*.sql`, `models/`, "migration", "schema"… | domain-modeling, prisma |
| `qa` | implementer | fast | seções `### Tests`, `tests/`, `*.test.*`, `e2e/` | tdd, playwright-skill, webapp-testing, route-tester |
| `security-reviewer` | reviewer (convergência) | strong | sempre, sobre o diff da feature | — |
| `devops` | implementer | fast | `Dockerfile`, `.github/workflows/`, `*.tf`, "deploy"… | setup-pre-commit, deploy-to-vercel |
| `docs` | implementer | fast | `docs/`, `README`, ADR, "quickstart"… | domain-modeling |
| `event-module` | implementer | fast | `modules/`, `domain/`, `events/`, `contracts/`, "módulo", "evento"… — lógica pura, sem banco/IO | — |
| `queue-worker` | implementer | fast | `workers/`, `queues/`, `*.worker.ts`, "bullmq", "fila"… — fila → módulo → POST interno | — |
| `bill-parser` | implementer | strong | `parsers/`, `*parser*.py`, `faturas/`, `layouts/`, "fatura", "distribuidora", "SCEE"… | — |
| `contract-reviewer` | reviewer (convergência, se a feature tocou contratos/fila/parsers) | strong | deriva de contrato TS ↔ Python ao longo da cadeia | — |

**Roteamento** (`waves.py`): score = 3×arquivos que casam `route_globs` + palavras de `route_keywords` na descrição (+2 para `qa` dentro de `### Tests`; +5 para papéis com `owns_tests: true` cujos globs casam — o especialista escreve os testes do próprio domínio); empate → `priority`. `[@papel]` na linha da tarefa força; sem match → `sdd-implementer`.
**Revisores** gravam relatório em `specs/NNN/reviews/` e devolvem tarefas CRITICAL/HIGH com `[@papel]`, que o `/sdd-build` anexa numa fase "Review fixes" e executa antes de seguir.
Para criar um papel: `sddkit role new <nome>` (ou `--kind reviewer`), preencha `description`, `route_globs` e `route_keywords`, e rode `sddkit sync`.

## Segurança
Três camadas — da que depende do modelo à que não depende:

| Camada | O quê | Onde |
|---|---|---|
| **Revisores** (convergência, em paralelo) | `security-reviewer` — revisão diferencial do diff + `fp-check` + `variant-analysis`, LGPD, authz, rotas internas, PIX/webhooks · `sast-scanner` — Semgrep (oficial + Trail of Bits/0xdea/Decurity) nos arquivos alterados, SARIF, triagem · `supply-chain-auditor` — só se a feature mexe em manifestos/lockfiles · `actions-auditor` — só se mexe em `.github/workflows` | `.agents/agents/`, skills de [trailofbits/skills](https://github.com/trailofbits/skills) (CC-BY-SA 4.0) |
| **Convergência** | `sdd-converger` usa `spec-to-code-compliance`: acha também comportamento que nenhuma spec pede | núcleo |
| **Determinística** (não depende do modelo obedecer) | hook `guard_secrets.py` bloqueia escrita de chaves/tokens (AWS, GitHub, Anthropic, OpenAI, Slack, Stripe, Google, chave privada, URL com senha) e CPF/CNPJ com dígito verificador válido · `permissions.deny` de leitura de `.env*`, `*.pem`, `*.key`, chaves SSH | Claude: `PreToolUse` em `.claude/settings.json` · qualquer ferramenta: `python3 .agents/hooks/guard_secrets.py --staged` no pre-commit (husky) |

- Semgrep exige aprovação humana do plano de varredura: na 1ª vez o `sast-scanner` devolve `PLANO PENDENTE`, o `/sdd-build` pergunta e grava em `.agents/security/semgrep-plan.json`; depois roda sem perguntar enquanto linguagens e rulesets forem os mesmos. Sem o CLI: `uv tool install semgrep`.
- Fixtures (LGPD): use CPF/CNPJ com DV **inválido** (ex.: `123.456.789-00`). Falso positivo do guard: comentário `sddkit:allow-secret` na linha; `*.example`/`*.sample` são ignorados.
- Atualizar papéis instalados após upgrade do sddkit: `sddkit role update` (ou `sddkit init --force-templates`).

## Catálogo de sugestões
`src/sddkit/catalog.json`. A detecção varre a raiz e pacotes de monorepo (até 3 níveis: `package.json`, `pyproject.toml`, `requirements*.txt`). Cada entrada traz fonte, skills (com dependências: `grill-me` instala `grilling`), em que fase do SDD ajuda e quando sugerir (`always`, `has_code` ou `stacks` detectadas a partir de package.json, pyproject, go.mod, vercel.json…). Recomendadas (★) são instaladas por padrão.

**Níveis de publicador.** `suggest` agrupa as skills (Starting → Coding → UI → Testing → Review → Security → Workflow) e, em cada grupo, lista primeiro as **oficiais** (publicadores conhecidos: `anthropics`, `vercel-labs`, `cloudflare`, `trailofbits` — `OFFICIAL_PUBLISHERS` em `cli.py`) e depois as de **comunidade** (indivíduos e projetos independentes), que o `add` marca com ⚠ para revisão. Entradas com efeitos fora do projeto (hooks, downloads de binário, upload, instalação global) trazem um aviso ⚠ na descrição.

| Grupo | Skills (quando sugerir) |
|---|---|
| **Starting** | ★ grill-me (sempre) · grill-with-docs (sempre) · domain-modeling (sempre) · ★ improve-codebase-architecture (código existente) · planning-with-files (sempre) |
| **Coding** | ★ ponytail (sempre) · ★ react-best-practices (react, next) · ★ react-native (react-native, expo) · ★ mcp-builder (mcp) · ★ claude-api (anthropic-sdk) · ★ cck-express (express) · ★ cck-nodejs (node) · ★ cck-prisma (prisma) · ★ cck-tailwindcss (tailwind) · ★ cck-shadcn (shadcn) · ★ cck-mui (mui) · ★ cck-tanstack-query (tanstack-query) · ★ cck-tanstack-router (tanstack-router) · cck-react (react) · cck-nextjs (next) |
| **UI** | ★ frontend-design (frontend) · web-design-guidelines (frontend) · impeccable (frontend) · ★ apple-design (apple, react-native, flutter, desktop) · ★ ui-ux-pro-max (frontend, react-native, flutter, apple, desktop) · theme-factory (frontend) |
| **Testing** | ★ tdd (sempre) · ★ diagnosing-bugs (sempre) · webapp-testing (frontend) · ★ playwright (frontend) · property-based-testing (fast-check, queue, pydantic) · cck-route-tester (backend) |
| **Review** | ★ superpowers (sempre) · ★ spec-to-code-compliance (sempre) |
| **Security** | ★ security-review (sempre) · ★ semgrep (sempre) · ★ security-audit (código existente) · ★ supply-chain-risk-auditor (node, python, go, rust) · ★ agentic-actions-auditor (ci) |
| **Workflow** | ★ git-guardrails-claude-code (sempre) · ★ setup-pre-commit (node) · ★ caveman (sempre) · ★ find-skills (sempre) · ★ skill-creator (sempre) · deploy-to-vercel (vercel) |

## Fluxo no agente
```text
/speckit-constitution TDD obrigatório; LGPD by design; ...
/sdd-feature Cooperado baixa a fatura do mês --stack NestJS+Postgres --grill
/sdd-build --mvp
```
