"""Harness de ponta a ponta: projetos de exemplo → `sddkit` de verdade (subprocesso) → asserções.

Offline por padrão (sem Spec Kit, sem `npx skills`, sem npm). `SDDKIT_E2E=1` liga os cenários de rede.
Cada bug achado à mão vira um caso aqui (comentário `regressão:`).

    python -m pytest tests/          # ou: python tests/test_harness.py
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
E2E = os.environ.get("SDDKIT_E2E") == "1"
ENV = {**os.environ, "PYTHONPATH": str(SRC), "NO_COLOR": "1", "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t"}
OFFLINE_INIT = ["init", "-y", "--no-speckit", "--agents", "claude", "--roles", "none", "--skills", "none"]


# ───────────────────────── utilitários ─────────────────────────
def sdd(root: Path, *args: str, ok: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run([sys.executable, "-m", "sddkit", *args], cwd=root, env=ENV, capture_output=True, text=True)
    if ok and r.returncode != 0:
        raise AssertionError(f"sddkit {' '.join(args)} → {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, env=ENV, capture_output=True, text=True)


def project(files: dict[str, str] | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="sddkit-h-"))
    git(root, "init", "-q")
    for rel, text in (files or {}).items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def snapshot(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if rel.startswith(".git/") or rel == ".git":
            continue
        if p.is_symlink():
            out[rel] = "->" + os.readlink(p)
        elif p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def commit(root: Path, msg: str) -> bool:
    return git(root, "commit", "-q", "--allow-empty", "-m", msg).returncode == 0


def frontmatter_skills(md: str) -> list[str]:
    lines, out, on = md.split("---")[1].splitlines(), [], False
    for ln in lines:
        if ln.startswith("skills:"):
            on = True
            out += [x.strip() for x in ln[7:].strip(" []").split(",") if x.strip()]
        elif on and ln.startswith("  - "):
            out.append(ln[4:].strip())
        elif on:
            on = False
    return out


# ───────────────────────── init / sync ─────────────────────────
def test_init_offline_creates_layout_and_is_idempotent():
    root = project({"AGENTS.md": "# Meu projeto\n\nRegra da casa: nada de any.\n",
                    "CLAUDE.md": "Notas minhas.\n"})
    sdd(root, *OFFLINE_INIT)
    agents = (root / "AGENTS.md").read_text()
    assert "Regra da casa: nada de any." in agents                    # texto do usuário preservado
    assert "<!-- sddkit:begin -->" in agents and "sdd-change" in agents
    claude = (root / "CLAUDE.md").read_text()
    assert "Notas minhas." in claude and "@AGENTS.md" in claude
    for f in ("architecture.md", "stack.md", "coding-standards.md", "design-system.md", "features.md",
              "features/.gitkeep", "changes/.gitkeep", "playbooks/.gitkeep"):
        assert (root / ".agents/specs" / f).exists(), f
    for r in ("sdd-analyst", "sdd-converger", "sdd-implementer", "sdd-researcher"):
        assert (root / ".claude/agents" / f"{r}.md").exists(), r
    assert (root / ".agents/skills/sdd-change/SKILL.md").exists()
    assert not (root / "specs").exists()                              # nada no `specs/` do Spec Kit

    before = snapshot(root)
    sdd(root, "sync")
    assert snapshot(root) == before, "sync logo após init mudou arquivos"
    sdd(root, *OFFLINE_INIT)
    assert snapshot(root) == before, "init repetido mudou arquivos"


def test_init_never_overwrites_specs_docs():
    root = project({".agents/specs/architecture.md": "# Arquitetura real\n"})
    sdd(root, *OFFLINE_INIT)
    assert (root / ".agents/specs/architecture.md").read_text() == "# Arquitetura real\n"
    sdd(root, *OFFLINE_INIT, "--force-templates")
    assert (root / ".agents/specs/architecture.md").read_text() == "# Arquitetura real\n"


# ───────────────────────── fonte única: gerados, blocos, templates ─────────────────────────
def test_generated_file_edited_by_hand_is_protected():
    root = project()
    sdd(root, *OFFLINE_INIT)
    gen = root / ".claude/agents/sdd-analyst.md"
    gen.write_text(gen.read_text() + "\nregra só minha\n")
    r = sdd(root, "sync", ok=False)
    assert r.returncode == 1 and "editado à mão" in r.stdout and "regra só minha" in gen.read_text()
    assert sdd(root, "sync", "--check", ok=False).returncode == 1
    assert "nenhum arquivo/bloco gerado editado à mão" in sdd(root, "doctor", ok=False).stdout
    sdd(root, "sync", "--force")
    assert "regra só minha" not in gen.read_text()
    assert "✓ arquivos gerados em dia" in sdd(root, "sync", "--check").stdout


def test_sync_check_detects_stale_output_and_writes_nothing():
    root = project()
    sdd(root, *OFFLINE_INIT)
    src = root / ".agents/agents/sdd-analyst.md"
    src.write_text(src.read_text().replace("description:", "description: [editado na fonte]", 1))
    before = snapshot(root)
    r = sdd(root, "sync", "--check", ok=False)
    assert r.returncode == 1 and "✗ desatualizado: .claude/agents/sdd-analyst.md" in r.stdout
    assert snapshot(root) == before, "sync --check escreveu"
    sdd(root, "sync")
    assert "[editado na fonte]" in (root / ".claude/agents/sdd-analyst.md").read_text()
    assert sdd(root, "sync", "--check").returncode == 0


def test_agents_md_block_edit_is_kept_but_text_outside_is_free():
    root = project()
    sdd(root, *OFFLINE_INIT)
    p = root / "AGENTS.md"
    p.write_text("Minha introdução.\n\n" + p.read_text().replace("## Fluxo", "## Fluxo (mexido)", 1))
    r = sdd(root, "sync", ok=False)
    assert "AGENTS.md#sddkit: bloco editado à mão" in r.stdout
    assert "## Fluxo (mexido)" in p.read_text() and "Minha introdução." in p.read_text()
    sdd(root, "sync", "--force")
    assert "## Fluxo (mexido)" not in p.read_text() and "Minha introdução." in p.read_text()


def test_preexisting_user_file_is_not_overwritten():
    root = project({".claude/agents/ui.md": "---\nname: ui\n---\nmeu agente de UI\n"})
    sdd(root, *OFFLINE_INIT)
    sdd(root, "role", "add", "ui", "--no-skills", ok=False)
    assert (root / ".claude/agents/ui.md").read_text().endswith("meu agente de UI\n")
    for _ in range(2):                                                # regressão: 2º sync sobrescrevia o arquivo
        assert "já existia e não é do sddkit" in sdd(root, "sync", ok=False).stdout
        assert (root / ".claude/agents/ui.md").read_text().endswith("meu agente de UI\n")


def test_obsolete_generated_file_removed_unless_edited():
    root = project()
    sdd(root, *OFFLINE_INIT)
    sdd(root, "role", "add", "docs", "qa", "--no-skills")
    (root / ".claude/agents/qa.md").write_text("editado\n")
    sdd(root, "role", "remove", "docs", ok=False)
    sdd(root, "role", "remove", "qa", ok=False)
    assert not (root / ".claude/agents/docs.md").exists()
    assert (root / ".claude/agents/qa.md").read_text() == "editado\n"


def test_templates_update_when_untouched_and_keep_local_edits():
    root = project()
    sdd(root, *OFFLINE_INIT)
    cfg_p = root / ".agents/sddkit.json"
    build, change = root / ".agents/skills/sdd-build/SKILL.md", root / ".agents/skills/sdd-change/SKILL.md"
    cfg = json.loads(cfg_p.read_text())
    build.write_text("versão antiga do template\n")                     # simula cópia intocada de uma versão anterior
    cfg["templates"][".agents/skills/sdd-build/SKILL.md"] = hashlib.sha256(build.read_bytes()).hexdigest()[:16]
    cfg_p.write_text(json.dumps(cfg))
    change.write_text(change.read_text() + "\nregra local\n")          # edição do usuário
    out = sdd(root, "doctor", ok=False).stdout
    assert "templates do sddkit atualizados (1 com versão nova)" in out and "sdd-change/SKILL.md" in out
    r = sdd(root, *OFFLINE_INIT).stdout
    assert "1 atualizado" in r and "1 editado(s) por você" in r
    assert build.read_text() == (SRC / "sddkit/templates/skills/sdd-build/SKILL.md").read_text()
    assert change.read_text().endswith("regra local\n")
    sdd(root, *OFFLINE_INIT, "--force-templates")
    assert not change.read_text().endswith("regra local\n")


def test_claude_denies_edits_to_generated_folders():
    root = project()
    sdd(root, *OFFLINE_INIT)
    deny = json.loads((root / ".claude/settings.json").read_text())["permissions"]["deny"]
    assert {"Edit(.claude/agents/**)", "Edit(.claude/rules/sddkit-memory-*)", "Edit(.opencode/agents/**)"} <= set(deny)


def test_project_from_older_sddkit_upgrades_without_conflicts():
    root = project()
    sdd(root, *OFFLINE_INIT)
    cfg_p = root / ".agents/sddkit.json"
    cfg = json.loads(cfg_p.read_text())
    cfg.pop("hashes"), cfg.pop("templates")                            # como era antes desta versão
    cfg_p.write_text(json.dumps(cfg))
    r = sdd(root, "sync")
    assert "⚠" not in r.stdout
    assert sdd(root, "sync", "--check").returncode == 0


# ───────────────────────── detecção / catálogo / papéis ─────────────────────────
NODE_APP = {"package.json": json.dumps({"name": "app", "dependencies": {
    "react": "19", "express": "4", "@prisma/client": "5", "tailwindcss": "4", "@tanstack/react-query": "5"}}),
    "components.json": "{}"}


def test_suggest_groups_tiers_and_stack_filter():
    root = project(NODE_APP)
    data = json.loads(sdd(root, "suggest", "--json").stdout)
    stacks = set(data["project"]["stacks"])
    assert {"react", "express", "prisma", "tailwind", "shadcn", "tanstack-query", "frontend"} <= stacks
    ids = [s["id"] for s in data["skills"]]
    assert "cck-prisma" in ids and "cck-mui" not in ids and "apple-design" not in ids
    groups = json.loads((SRC / "sddkit/catalog.json").read_text())["groups"]
    order = [(groups.index(s["group"]), s["tier"] != "oficial") for s in data["skills"]]
    assert order == sorted(order), "suggest fora da ordem grupo → oficial → comunidade"
    py = project({"requirements.txt": "fastapi\n"})
    py_ids = [s["id"] for s in json.loads(sdd(py, "suggest", "--json").stdout)["skills"]]
    assert not any(i.startswith("cck-") and i != "cck-route-tester" for i in py_ids)


def test_declared_stack_drives_suggestions_before_any_manifest():
    root = project()
    out = sdd(root, *OFFLINE_INIT).stdout
    assert "/sdd-stack" in out and (root / ".agents/skills/sdd-stack/SKILL.md").exists()
    assert json.loads(sdd(root, "suggest", "--json").stdout)["project"]["stacks"] == []   # template [PREENCHER ignorado
    (root / ".agents/specs/stack.md").write_text(
        "# Stack\n\n## Por componente\n- **Web:** TypeScript, Next.js 15, `tailwindcss`, shadcn/ui, `@tanstack/react-query`\n"
        "- **API:** Express com `@prisma/client` e PostgreSQL; jobs com `bullmq`\n\n## Infraestrutura\nDocker, GitHub Actions.\n\n"
        "## Decisões\n- 2026-10-22: Express em vez de Django (equipe é TypeScript).\n")
    data = json.loads(sdd(root, "suggest", "--json").stdout)
    stacks = set(data["project"]["stacks"])
    assert {"next", "react", "frontend", "tailwind", "shadcn", "tanstack-query", "express", "prisma", "db",
            "queue", "docker", "ci", "node"} <= stacks, stacks
    assert "python" not in stacks                                       # Django só aparece como alternativa descartada
    ids = {s["id"] for s in data["skills"]}
    assert {"cck-prisma", "cck-shadcn", "react-best-practices"} <= ids
    assert "/sdd-stack" not in sdd(root, *OFFLINE_INIT).stdout          # stack preenchida: não sugere de novo


def test_paradigm_skills_only_for_backend_code():
    back = project({"package.json": json.dumps({"dependencies": {"express": "4"}})})
    front = project({"package.json": json.dumps({"dependencies": {"react": "19"}})})
    para = {"solid", "clean-architecture", "domain-driven-design"}
    sk = {s["id"]: s for s in json.loads(sdd(back, "suggest", "--json").stdout)["skills"]}
    assert para <= set(sk) and not any(sk[i]["recommended"] for i in para)      # opcionais
    assert not para & {s["id"] for s in json.loads(sdd(front, "suggest", "--json").stdout)["skills"]}
    sdd(back, *OFFLINE_INIT)
    for name in ("solid", "frontend-design"):                                    # finge as skills instaladas
        (back / ".agents/skills" / name).mkdir(parents=True)
        (back / ".agents/skills" / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n")
    sdd(back, "role", "add", "api", "ui", "--no-skills")
    sdd(back, "sync")
    api, ui = (back / ".claude/agents/api.md").read_text(), (back / ".claude/agents/ui.md").read_text()
    assert "- `solid` —" in api and "solid" not in frontmatter_skills(api)   # backend: sob demanda
    assert "solid" not in ui                                                 # frontend: nunca
    assert frontmatter_skills(ui) == ["frontend-design"]
    # o que o /sdd-stack grava: escopo global + regra só nas pastas de backend
    sdd(back, "memory", "add", "Paradigma OOP/SOLID só no backend (server/**)", "-t", "paradigma")
    sdd(back, "memory", "add", "Entidades protegem as próprias invariantes", "-t", "paradigma-backend", "--paths", "server/**")
    agents = (back / "AGENTS.md").read_text()
    assert "Paradigma OOP/SOLID só no backend" in agents
    rule = (back / ".claude/rules/sddkit-memory-paradigma-backend.md").read_text()
    assert '"server/**"' in rule and "Entidades protegem" in rule


def test_role_preloads_only_installed_skills():
    root = project(NODE_APP)
    sdd(root, *OFFLINE_INIT)
    fake = root / ".agents/skills/tailwindcss"                        # finge uma skill instalada
    fake.mkdir(parents=True)
    (fake / "SKILL.md").write_text("---\nname: tailwindcss\ndescription: x\n---\n")
    sdd(root, "role", "add", "ui", "--no-skills")
    sdd(root, "sync")
    ui = (root / ".claude/agents/ui.md").read_text()
    assert frontmatter_skills(ui) == [], frontmatter_skills(ui)         # tailwindcss é sob demanda: não pré-carrega
    assert "## Skills sob demanda" in ui and "- `tailwindcss` — x" in ui
    assert "`shadcn`" not in ui                                          # não instalada: não aparece
    assert "disallowedTools: Agent" in ui                            # papéis não criam subagents


# ───────────────────────── specs: CRs, índice, playbooks ─────────────────────────
def test_change_and_playbook_commands():
    root = project()
    sdd(root, *OFFLINE_INIT)
    feat = root / ".agents/specs/features/001-faturas"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Feature Specification: Faturas\n")
    (feat / "tasks.md").write_text("- [x] T001 a\n- [ ] T002 b\n")
    sdd(root, "change", "new", "Parcelar faturas", "--feature", "001")
    sdd(root, "change", "new", "Ação rápida")
    hand = root / ".agents/specs/changes/2020-01-01-manual.md"          # CR escrito à mão, `feature: 001` sem aspas
    hand.write_text("---\nid: CHANGE-007\ntitle: Manual\nstatus: Implemented\nfeature: 001\n---\n")
    out = sdd(root, "playbook", "new", "Pipeline assíncrono").stdout   # também regenera o índice
    assert "pipeline-assincrono.md" in out                            # regressão: acento virava "ass-ncrono"
    changes = sorted((root / ".agents/specs/changes").glob("*.md"))
    assert [c.name.split("-", 3)[3] for c in changes] == ["manual.md", "acao-rapida.md", "parcelar-faturas.md"]
    idx = (root / ".agents/specs/features.md").read_text()
    assert "| 001 | Faturas | In Progress | 1/2 | CHANGE-001, CHANGE-007 |" in idx  # regressão: `feature: 001` virava int 1
    assert "CHANGE-008" in sdd(root, "change", "new", "Depois do manual").stdout  # próximo id = maior + 1
    assert "CHANGE-002" in idx and "Pipeline assíncrono" in idx
    assert "['" not in idx                                            # regressão: placeholder [..] virava lista


# ───────────────────────── doctor (drift) ─────────────────────────
PHOTON_LIKE = {
    "AGENTS.md": "<!-- SPECKIT START -->\nread the current plan\nat .agents/specs/features/008-gone/plan.md\n<!-- SPECKIT END -->\n"
                 "Leia `architecture.md`, `project-structure.md`, `/specs/changelog.md`, `/contracts/openapi`,\n"
                 "`libs/atRest`, `lib/summary.ts`, `/v1/internal/events`, `/.well-known/jwks.json`,\n"
                 "`checklists/requirements.md`, `spec.md`, `.agents/specs/features/<feature>.md`.\n",
    "libs/atRest.ts": "", "app/src/lib/summary.ts": "", "contracts/index.ts": "",
    ".agents/specs/architecture.md": "# Arquitetura\nExpress, Prisma e React Query.\n",
    ".agents/specs/stack.md": "# Stack\nTailwind CSS v4.\n",
    ".agents/specs/features/001-auth/spec.md": "# Feature Specification: Auth\n",
    ".agents/specs/features/011-tokens/tasks.md": "- [x] W1 a\n",
    ".agents/specs/changes/2026-07-02-a.md": "---\nid: CHANGE-010\ntitle: A\nstatus: Implemented\nfeature: 001\n---\n",
    ".agents/specs/changes/2026-09-07-b.md": "---\nid: CHANGE-010\ntitle: B\nstatus: Implemented (2026-09-30, uncommitted)\n---\n",
    ".specify/specs/features/plan.md": "velho\n",
    "package.json": json.dumps({"dependencies": {"express": "4", "@prisma/client": "5", "@tanstack/react-query": "5",
                                                 "tailwindcss": "4", "bullmq": "5", "zod": "3"}}),
    ".claude/settings.local.json": "{}",
}


def test_doctor_flags_real_drift_without_false_positives():
    root = project(PHOTON_LIKE)
    git(root, "add", "-A")
    before = snapshot(root)
    out = sdd(root, "doctor", ok=False).stdout
    assert snapshot(root) == before, "doctor escreveu arquivos"
    drift = out.split("Specs (drift):")[1]
    refs = next(ln for ln in drift.splitlines() if ln.strip().startswith("· AGENTS.md:"))
    for bad in ("project-structure.md", "/specs/changelog.md", "/contracts/openapi"):
        assert bad in refs, bad
    for fine in ("architecture.md,", "libs/atRest", "lib/summary.ts", "/v1/internal", "jwks.json",
                 "checklists/requirements.md", "spec.md,"):                 # regressão: falsos positivos
        assert fine not in refs, fine
    assert "✗ bloco SPECKIT" in drift and "· .specify/specs" in drift
    assert "· CHANGE-010: 2026-07-02-a.md, 2026-09-07-b.md" in drift
    assert "Implemented (2026-09-30, uncommitted)" in drift
    assert "· 011-tokens" in drift
    assert "· 011-tokens/tasks.md: 1 tarefas — 1 com id fora de T###, 1 sem caminho de arquivo" in drift   # formato do Spec Kit
    deps = drift.split("dependências de arquitetura")[1].split("✗ features")[0]
    assert "bullmq" in deps and "zod" in deps
    for documented in ("express", "react-query", "tailwindcss", "prisma"):    # regressão: "React Query"/"Tailwind CSS"
        assert documented not in deps, documented
    assert "✗ CLAUDE.md importa @AGENTS.md" in drift
    assert "· 2026-09-07-b.md" in drift                               # CR sem `feature:`
    assert "2026-07-02-a.md" not in drift.split("CRs com campo feature")[1]


def test_doctor_fix_applies_only_mechanical_fixes():
    files = dict(PHOTON_LIKE)
    files[".agents/specs/changes/2026-09-07-b.md"] = ("---\nid: CHANGE-011\ntitle: B\nstatus: Implemented (2026-09-30, uncommitted)\n"
                                                    "---\nMexe em `001-auth` e nada mais.\n")
    files["specs/005-legacy/spec.md"] = "# Feature Specification: Legacy\n"
    root = project(files)
    out = sdd(root, "doctor", "--fix", ok=False).stdout
    b = (root / ".agents/specs/changes/2026-09-07-b.md").read_text()
    assert "status: Implemented\n" in b and "Status anterior" in b and 'feature: "001"' in b
    assert (root / ".agents/specs/features/005-legacy/spec.md").exists() and not (root / "specs").exists()
    assert not (root / ".agents/skills").exists() and not (root / ".agents/agents").exists()  # regressão: --fix instalava templates
    assert "status de CR no enum" in out
    again = sdd(root, "doctor", "--fix", ok=False).stdout
    assert "0 correção(ões) aplicada(s)" in again and not (root / ".agents/skills").exists()


def test_doctor_clean_after_index_on_fresh_project():
    root = project()
    sdd(root, *OFFLINE_INIT)
    drift = sdd(root, "doctor", ok=False).stdout.split("Specs (drift):")[1]
    failed = [ln for ln in drift.splitlines() if ln.strip().startswith("✗")]
    assert len(failed) == 1 and "docs centrais preenchidos" in failed[0], failed


# ───────────────────────── tokens ─────────────────────────
def _fake_skill(root: Path, name: str, desc: str, body_chars: int) -> None:
    d = root / ".agents/skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n" + "x" * body_chars + "\n")


def test_budget_lean_preload_and_names_only_agents_md():
    root = project()
    sdd(root, *OFFLINE_INIT)
    _fake_skill(root, "frontend-design", "DESCRICAO-LONGA-DO-FRONTEND", 8000)
    _fake_skill(root, "tailwindcss", "estilo com tailwind", 40000)          # 10k tokens: só sob demanda
    sdd(root, "role", "add", "ui", "--no-skills")
    sdd(root, "sync")
    assert "DESCRICAO-LONGA-DO-FRONTEND" not in (root / "AGENTS.md").read_text()   # só nomes no AGENTS.md
    assert "`frontend-design`" in (root / "AGENTS.md").read_text()
    r = json.loads(sdd(root, "budget", "--json").stdout)
    ui = next(x for x in r["roles"] if x["role"] == "ui")
    assert list(ui["preload"]) == ["frontend-design"] and ui["ondemand"] == ["tailwindcss"]
    assert ui["total"] < 4000                                               # sem os 10k do tailwindcss
    assert r["session"]["skills"] == len(list((root / ".agents/skills").glob("*/SKILL.md")))
    text = sdd(root, "budget").stdout
    assert "Por sessão" in text and "ui" in text
    (root / ".agents/agents/ui.md").write_text((root / ".agents/agents/ui.md").read_text()
                                              .replace("skills: [frontend-design,", "skills: [tailwindcss, frontend-design,"))
    assert "⚠" in sdd(root, "budget", ok=False).stdout                       # passou do limite por tarefa
    assert "pré-carga dos subagents" in sdd(root, "doctor", ok=False).stdout


def test_waves_writes_story_scoped_context():
    root = project()
    sdd(root, *OFFLINE_INIT)
    f = root / ".agents/specs/features/001-x"
    f.mkdir(parents=True)
    (f / "spec.md").write_text("# Feature Specification: X\n\n## User Scenarios\n\n### User Story 1 - Pagar (Priority: P1)\nPAGAR-HISTORIA\n\n"
                               "### User Story 2 - Estornar (Priority: P2)\nESTORNO-HISTORIA\n\n## Requirements\n- **FR-001**: System MUST pagar\n")
    (f / "plan.md").write_text("# Plan\n\n## Summary\nRESUMO-LONGO\n\n## Technical Context\nNode 22\n\n## Project Structure\n```text\n# Option 1\nsrc/\n```\n\n## Complexity Tracking\nNADA\n")
    (f / "tasks.md").write_text("## Phase 3: US1\n- [ ] T010 [US1] Pagar em src/pay.ts\n\n## Phase 4: US2\n- [ ] T020 [US2] Estornar em src/refund.ts\n")
    out = subprocess.run([sys.executable, str(root / ".agents/skills/sdd-build/scripts/waves.py"), str(f / "tasks.md")],
                         cwd=root, capture_output=True, text=True, check=True).stdout
    ctx = {t["id"]: t["context"] for w in json.loads(out)["waves"] for t in w["tasks"]}
    us1 = Path(ctx["T010"]).read_text()
    assert "PAGAR-HISTORIA" in us1 and "ESTORNO-HISTORIA" not in us1 and "FR-001" in us1
    assert "Node 22" in us1 and "src/" in us1 and "RESUMO-LONGO" not in us1 and "NADA" not in us1  # regressão: "# Option 1" no bloco não corta a seção
    assert (f / ".context/.gitignore").read_text() == "*\n"


# ───────────────────────── auditoria / CI ─────────────────────────
def test_audit_skill_and_ci_workflows():
    root = project()
    sdd(root, *OFFLINE_INIT)
    assert (root / ".agents/skills/sdd-audit/SKILL.md").exists() and (root / ".agents/specs/audits/.gitkeep").exists()
    assert "/sdd-audit" in (root / "AGENTS.md").read_text()
    sdd(root, "ci", "--audit")
    check = (root / ".github/workflows/sddkit.yml").read_text()
    audit = (root / ".github/workflows/sddkit-audit.yml").read_text()
    assert "sddkit sync --check" in check and "{source}" not in check
    assert "felipevale23/sddkit@v" in check and "felipevale23/sddkit@v" in audit   # versão fixada
    assert "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in audit and "${{ secrets.ANTHROPIC_API_KEY }}" in audit
    assert "anthropics/claude-code-action@v1" in audit
    assert "contents: read" in audit and "contents: write" not in audit   # auditoria não faz commit
    (root / ".github/workflows/sddkit.yml").write_text("meu ci\n")
    assert "já existe — mantido" in sdd(root, "ci").stdout
    assert (root / ".github/workflows/sddkit.yml").read_text() == "meu ci\n"


# ───────────────────────── commitlint / commit-msg ─────────────────────────
ATTRIBUTION = "fix: a\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


def test_commitlint_python_project_blocks_bad_commits():
    root = project({"requirements.txt": "fastapi\n"})
    sdd(root, "commitlint")
    assert git(root, "config", "core.hooksPath").stdout.strip() == ".githooks"
    assert commit(root, "fix(api): corrige filtro")
    assert not commit(root, "added stuff")
    assert not commit(root, ATTRIBUTION)
    assert not commit(root, "feat: x\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)")
    assert commit(root, "fix: a\n\nCo-authored-by: Maria <maria@x.com>")
    before = snapshot(root)
    assert "já configurado" in sdd(root, "commitlint").stdout
    assert snapshot(root) == before


def test_commitlint_keeps_existing_hooks_and_exit_codes():
    root = project({"requirements.txt": "x\n"})
    pre = root / ".git/hooks/pre-commit"
    pre.write_text("#!/bin/sh\nexit 0\n")
    pre.chmod(0o755)
    sdd(root, "commitlint")
    assert git(root, "config", "core.hooksPath").stdout.strip() == ""  # não desliga .git/hooks
    assert (root / ".git/hooks/commit-msg").exists()

    husky = project({"package.json": json.dumps({"name": "y", "devDependencies": {
        "@commitlint/cli": "x", "@commitlint/config-conventional": "x"}}),
        ".husky/commit-msg": 'npx --no -- commitlint --edit "$1"\n', "commitlint.config.js": "module.exports={}\n"})
    out = sdd(husky, "commitlint", "--no-install").stdout
    assert "config existente mantida" in out
    lines = (husky / ".husky/commit-msg").read_text().splitlines()
    assert lines[-1] == 'npx --no -- commitlint --edit "$1"'           # regressão: última linha decide o status
    assert all(ln.endswith("|| exit 1") for ln in lines if "commit_msg.py" in ln)


def test_commitlint_node_end_to_end():
    if not E2E:
        return
    root = project({"package.json": json.dumps({"name": "z", "version": "1.0.0"})})
    (root / ".husky").mkdir()
    git(root, "config", "core.hooksPath", ".husky")
    sdd(root, "commitlint")
    assert commit(root, "feat: ok")
    assert not commit(root, "Bad Header.")                            # regressão: commitlint falhava e o commit passava
    assert not commit(root, ATTRIBUTION)


# ───────────────────────── rede (SDDKIT_E2E=1) ─────────────────────────
def test_full_init_with_speckit_and_skill_install():
    if not E2E:
        return
    root = project()
    sdd(root, "init", "-y", "--agents", "claude", "--roles", "none", "--skills", "none")
    assert (root / ".specify/memory/constitution.md").exists()
    assert (root / ".agents/skills/speckit-specify/SKILL.md").exists()
    sdd(root, "add", "caveman")
    assert (root / ".agents/skills/caveman/SKILL.md").exists()
    assert "comunidade" in sdd(root, "add", "caveman").stdout
    before = snapshot(root)
    sdd(root, "sync")
    assert snapshot(root) == before


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"✓ {name}")
        except AssertionError as e:
            failed += 1
            print(f"✗ {name}\n  {str(e)[:600]}")
    print(f"\n{len(tests) - failed}/{len(tests)} ok" + ("" if E2E else "  (SDDKIT_E2E=1 liga os cenários de rede)"))
    shutil.rmtree(tempfile.gettempdir() + "/sddkit-h-", ignore_errors=True)
    sys.exit(1 if failed else 0)
