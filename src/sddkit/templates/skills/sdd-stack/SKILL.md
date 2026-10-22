---
name: sdd-stack
description: Grill focado na stack — entrevista o usuário em rodadas, cada pergunta com resposta recomendada, até fechar linguagem, frameworks, dados, filas, auth, hospedagem, CI e testes; grava .agents/specs/stack.md e a visão geral de architecture.md e manda rodar `sddkit init` de novo para instalar papéis e skills da stack escolhida. Use logo depois do primeiro `sddkit init`, quando a stack ainda não está definida, ou ao trocar uma peça grande da stack.
argument-hint: "[o que o projeto é, em uma frase] [--revisar]"
---

# /sdd-stack

Entrada: `$ARGUMENTS`. Você conduz uma entrevista sobre a **stack** e só escreve arquivos no fim, depois de o usuário confirmar o resumo.

## 0. Antes de perguntar: descubra os fatos
Fato do ambiente é trabalho seu, nunca pergunta ao usuário. Olhe (ou delegue a um subagent):
- manifestos e código existentes (`package.json`, `pyproject.toml`, `go.mod`, `Dockerfile`, `.github/workflows/`, pastas de topo);
- `.agents/specs/stack.md` e `architecture.md` (se já preenchidos e não houver `--revisar`, mostre o resumo e pergunte só o que falta);
- `.specify/memory/constitution.md` (restrições já decididas, ex.: LGPD, banco único);
- `sddkit suggest --json` (stacks detectadas).

O que já está decidido no código entra como decisão tomada, não como pergunta.

## 1. Método
- Skill `grilling` instalada em `.agents/skills/` → siga o método dela (rodadas pela fronteira da árvore de decisões, cada pergunta com resposta recomendada, até a fronteira esvaziar).
- Não instalada → mesmo formato: em cada rodada, todas as perguntas cujas pré-condições já estão respondidas, numeradas, cada uma assim:

```
❓ **Q1 — <título>**: <pergunta, com 2–4 opções e o trade-off de cada em 1 linha>

➡️ <sua recomendação e o porquê, em 1–2 linhas>
```

Escreva cada pergunta de modo que "sim" aceite a recomendação. Prefira tecnologia **chata e madura**, que a equipe já conhece, ao estado da arte; uma linguagem para o projeto todo, salvo motivo forte; o mínimo de peças que atende ao escopo (cada serviço a mais é custo de operação). Se a resposta contradiz uma anterior ou a constituição, aponte e pergunte qual vale.

## 2. Árvore de decisões da stack
Percorra nesta ordem de dependência; pule ramos que não se aplicam (ex.: sem UI → sem perguntas de frontend).

1. **Produto:** o que é (app web, API, app mobile, desktop, CLI, biblioteca, worker), quem usa, escala esperada (usuários, dados, picos), restrições (LGPD, offline, custo, prazo).
2. **Equipe:** linguagens que a equipe domina; quem vai manter.
3. **Forma:** monólito modular, monorepo com pacotes ou serviços separados; o que precisa ser assíncrono.
4. **Linguagem e runtime** (versão maior): ex.: TypeScript/Node 22, Python 3.12.
5. **Frontend** (se houver UI): framework (React/Next, Vue/Nuxt, Svelte, Astro…), renderização (SPA, SSR, estático), biblioteca de componentes e estilo (MUI, shadcn+Tailwind…), estado de servidor (TanStack Query…), i18n, acessibilidade.
6. **Mobile/desktop** (se houver): nativo, React Native/Expo, Flutter, Tauri, Electron.
7. **Backend/API:** framework (Express, Fastify, NestJS, Hono, FastAPI, Django…), estilo (REST, GraphQL, tRPC), contratos e validação (Zod, Pydantic, OpenAPI).
8. **Dados:** banco (PostgreSQL, MySQL, MongoDB, SQLite), ORM/acesso (Prisma, Drizzle, SQLAlchemy…), migrations, cache.
9. **Assíncrono:** fila/jobs (BullMQ, Celery, pg-boss…), eventos, tempo real (WebSocket/SSE).
10. **Autenticação e autorização:** provedor ou próprio, sessões/JWT, papéis/permissões.
11. **Integrações externas:** pagamentos (PIX…), e-mail, IA (SDK da Anthropic…), MCP.
12. **Hospedagem e operação:** onde roda (Vercel, VPS com Docker, cloud gerenciada), ambientes, segredos, observabilidade (logs, erros, métricas).
13. **Qualidade:** testes (unidade, integração, e2e com Playwright), lint/format, typecheck, CI (GitHub Actions), commits (Conventional Commits/commitlint).

## 3. Confirmação
Com a fronteira vazia, mostre o resumo em uma tabela (camada · escolha · versão · por quê · alternativa descartada) e pergunte: "Fechamos assim?". Não escreva nada antes do "sim".

## 4. Gravar
1. **`.agents/specs/stack.md`**: substitua o conteúdo (incluindo o marcador `[PREENCHER`) por:
   - `## Por componente` — cada camada com tecnologia, versão maior e as bibliotecas principais pelo **nome do pacote** (ex.: `react`, `@prisma/client`, `bullmq`, `fastapi`): o `sddkit` usa esses nomes para sugerir papéis e skills;
   - `## Infraestrutura` — banco, fila, cache, hospedagem, CI, observabilidade;
   - `## Decisões` — cada escolha relevante com o porquê e a alternativa descartada (data de hoje).
2. **`.agents/specs/architecture.md`**: preencha a seção `## Visão geral` (componentes e como conversam; um diagrama mermaid se houver mais de 2 peças) e tire o `[PREENCHER`. As demais seções ficam para quando houver código.
3. **Constituição:** se surgiram restrições inegociáveis (ex.: "PostgreSQL é a única fonte de verdade"), proponha o texto e sugira `/speckit-constitution` — não edite a constituição direto.
4. Diga ao usuário para rodar no terminal:
   ```bash
   sddkit init        # lê a stack declarada e oferece papéis e skills dela (nada existente é apagado)
   sddkit doctor
   ```

## Relatório final (≤ 8 linhas)
Stack decidida em 1 linha por camada · arquivos gravados · restrições sugeridas para a constituição · próximo passo (`sddkit init`, depois `/sdd-feature`).
