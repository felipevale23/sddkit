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


def test_role_preloads_only_installed_skills():
    root = project(NODE_APP)
    sdd(root, *OFFLINE_INIT)
    fake = root / ".agents/skills/tailwindcss"                        # finge uma skill instalada
    fake.mkdir(parents=True)
    (fake / "SKILL.md").write_text("---\nname: tailwindcss\ndescription: x\n---\n")
    sdd(root, "role", "add", "ui", "--no-skills")
    sdd(root, "sync")
    ui = (root / ".claude/agents/ui.md").read_text()
    assert frontmatter_skills(ui) == ["tailwindcss"], frontmatter_skills(ui)
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
    deps = drift.split("dependências de arquitetura")[1].split("✗ features")[0]
    assert "bullmq" in deps and "zod" in deps
    for documented in ("express", "react-query", "tailwindcss", "prisma"):    # regressão: "React Query"/"Tailwind CSS"
        assert documented not in deps, documented
    assert "✗ CLAUDE.md importa @AGENTS.md" in drift
    assert "· 2026-09-07-b.md" in drift                               # CR sem `feature:`
    assert "2026-07-02-a.md" not in drift.split("CRs com campo feature")[1]


def test_doctor_clean_after_index_on_fresh_project():
    root = project()
    sdd(root, *OFFLINE_INIT)
    drift = sdd(root, "doctor", ok=False).stdout.split("Specs (drift):")[1]
    failed = [ln for ln in drift.splitlines() if ln.strip().startswith("✗")]
    assert len(failed) == 1 and "docs centrais preenchidos" in failed[0], failed


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
