---
name: sdd-audit
description: Caça de bugs no repositório inteiro, fora do fluxo de feature — roda as checagens determinísticas (testes, lint, tipos, dependências, Semgrep, sddkit doctor), manda subagents somente leitura caçarem bugs por área e conferirem features implementadas contra a spec, contesta cada achado com um segundo subagent e grava um relatório datado, abrindo CRs propostos para o que for estrutural. Nunca edita código. Use periodicamente, antes de uma release ou quando pedirem auditoria/caça de bugs.
argument-hint: "[--quick] [--scope <caminho>] [--features NNN,NNN] [--issue]"
---

# /sdd-audit

Entrada: `$ARGUMENTS`. Você é o **orquestrador** de uma auditoria: **não edita código nem specs**. Escreve só o relatório, CRs com `status: Proposed` e, com `--issue`, uma issue.

- `--quick`: só a parte 1 (determinística), sem subagents.
- `--scope <caminho>`: limita a caça de bugs a essa pasta.
- `--features 008,010`: limita a conformidade a essas features.
- `--issue`: além do arquivo, abre uma issue com o resumo (`gh issue create`).

## 0. Preparação
1. Leia `.specify/memory/constitution.md`, `.agents/specs/architecture.md`, `stack.md` e o último relatório em `.agents/specs/audits/` (se existir), para saber o que já era conhecido.
2. Descubra os comandos de teste, lint e tipos: `plan.md` das features, `package.json` (scripts), `pyproject.toml`, `Makefile`, CI em `.github/workflows/`.

## 1. Checagens determinísticas (sempre; não dependem do modelo)
Rode e guarde só o resumo (comando → passou/falhou, contagens, primeiras linhas de erro):
- testes, lint e checagem de tipos do projeto;
- `sddkit doctor` (instalação, fonte única e drift entre specs e código);
- dependências: `npm audit --omit=dev --json` / `pip-audit` / `osv-scanner --lockfile=<lock>`, o que existir;
- Semgrep **só** se houver plano aprovado em `.agents/security/semgrep-plan.json`: rode-o no repositório inteiro com os scripts da skill `semgrep`. Sem plano, registre "Semgrep: sem plano aprovado (rode /sdd-build uma vez ou aprove um plano)" e siga.

Ferramenta ausente não é falha: registre "não executado" com o comando de instalação.

## 2. Caça de bugs por área (subagents somente leitura, em paralelo)
1. Divida o código em áreas pela estrutura real (pacotes, serviços, pastas de topo), partindo de `## Mapa do código` em `architecture.md`; área real que falta no mapa vai ao relatório como achado LOW (próximo `/sdd-change`). Máx. 6 áreas por rodada; com `--scope`, só ela.
2. Para cada área, dispare um subagent **somente leitura** (sem editar arquivos) com: a área, o resumo da parte 1 que a toca e esta instrução:
   > Procure defeitos reais, não estilo: entradas não validadas na borda, erros engolidos, condições de corrida, recursos que vazam, falta de timeout/idempotência em efeitos externos, autorização faltando, queries sem limite em coleções que crescem, divergência entre contrato e implementação. Para cada achado devolva: `arquivo:linha`, o defeito em 1 frase, o cenário concreto que o dispara, severidade (CRITICAL/HIGH/MEDIUM/LOW), confiança (alta/média) e o teste que falharia hoje. Nada de achado sem cenário concreto.
3. Skills instaladas que ajudam (o subagent lê se existirem): `diagnosing-bugs`, `security-audit` (auditoria completa de segurança — cara; só se o usuário pedir ou houver suspeita) e as skills de regras do próprio projeto em `.agents/skills/` cuja descrição case com a área.

## 3. Conformidade spec × código (features implementadas)
Para cada feature com status `Implemented` ou `In Progress` em `.agents/specs/features.md` (ou as de `--features`), começando pelas que nunca foram auditadas ou foram há mais tempo (veja o relatório anterior), máx. 3 por rodada:
- Se `.agents/skills/spec-to-code-compliance/` existir, siga o método da seção "Conformidade spec × código" de `.agents/skills/sdd-build/SKILL.md`: lotes de 3–5 FR/SC por subagent somente leitura e contestação só dos vereditos graves.
- Senão, um subagent somente leitura por feature conferindo cada FR/SC no código (caminho:linha).

## 4. Contestação (falso positivo)
Cada achado HIGH/CRITICAL das partes 2 e 3 vai para um **segundo** subagent, que não o produziu, com a instrução de tentar derrubá-lo (o código de fato faz isso? o cenário é alcançável? há guarda em outra camada?). Se `fp-check` estiver instalada, ele a segue. Descarte o que cair e registre o motivo. MEDIUM/LOW entram sem contestação, marcados como "não contestado".

## 5. Relatório
Grave `.agents/specs/audits/AAAA-MM-DD.md` (crie a pasta; se já houver um do dia, sufixo `-2`):

```markdown
# Auditoria AAAA-MM-DD
Escopo · commit (`git rev-parse --short HEAD`) · o que rodou e o que não rodou

## Resumo
CRITICAL n · HIGH n · MEDIUM n · LOW n · novos n · resolvidos desde a última n

## Checagens determinísticas
| Checagem | Resultado |

## Achados
### [HIGH] <título> — novo | já conhecido
`arquivo:linha` · cenário · teste que falharia · confiança · contestação: mantido (motivo)

## Conformidade por feature
| Feature | FR/SC ok | partial | contradicted | absent |

## Descartados na contestação
- <achado> — <por que caiu>
```

## 6. Encaminhamento (sem implementar)
- Achado CRITICAL/HIGH confirmado que exige mudança estrutural (API, contrato, schema, regra) → `sddkit change new "<título>" --feature <NNN|none> --priority <High|Critical>`; preencha contexto e mudança proposta citando o relatório. Fica `Proposed`: o usuário decide.
- Achado local (Tipo A) → liste no relatório como próximo `/sdd-change`.
- `--issue` → `gh issue create --title "Auditoria AAAA-MM-DD: n CRITICAL, n HIGH" --body-file <relatório>` (sem `gh` autenticado: avise e pare aqui).

## Relatório final ao usuário (≤ 10 linhas)
Caminho do relatório · contagens por severidade · top 3 achados · CRs propostos · o que não rodou e por quê · próximo passo.
