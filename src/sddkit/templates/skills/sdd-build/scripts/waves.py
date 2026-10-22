#!/usr/bin/env python3
"""Converte tasks.md (formato Spec Kit) em ondas de execução para subagents.

Regras:
- Fases (## headings) são barreiras: a fase N só começa quando a N-1 terminou.
- Dentro da fase, tarefas [P] consecutivas formam uma onda paralela.
- Tarefa sem [P] vira onda própria (sequencial).
- Duas tarefas da mesma onda que tocam o mesmo arquivo, ou com
  "depends on Txxx" apontando para a onda corrente, são empurradas para a próxima.
- Subtítulos ### (ex.: "Tests for US1" → "Implementation") também são barreira,
  preservando TDD: testes da história terminam antes do código.
- Tarefas já marcadas [X] são ignoradas.

Roteamento (campo "agent" de cada tarefa):
- Papéis em .agents/agents/*.md com `kind: implementer` declaram `route_globs`,
  `route_keywords` e `priority`. Score = 3×(arquivos que casam um glob) +
  1×(palavras-chave na descrição); empate → maior priority. Em seções de
  testes, `qa` ganha +2 e papéis com `owns_tests: true` cujos globs casam, +5.
- Tag explícita na tarefa, ex.: `[@ui]`, sempre vence.
- Sem match → `sdd-implementer`.
- Papéis com `kind: reviewer` aparecem em "reviews": por história, quais
  revisores devem rodar (algum arquivo casou os globs) — ou `review_at: converge`.

Contexto por tarefa (economia de tokens): grava em FEATURE_DIR/.context/ um arquivo por história
(`US1.md`…) e um `base.md` para tarefas sem história, com só o que o implementador precisa — a seção
da história em spec.md, as linhas FR-xxx e as seções "Technical Context" e "Project Structure" de
plan.md. Cada tarefa sai com `context`: o caminho do arquivo. O subagent lê esse arquivo em vez de
spec.md e plan.md inteiros. `--no-context` desliga.

Uso:
  waves.py <tasks.md> [--mvp] [--phase N] [--max-parallel K] [--agents-dir DIR] [--no-context]
Saída: JSON em stdout.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

TASK_RE = re.compile(r"^\s*-\s*\[(?P<done>[ xX])\]\s*(?P<id>T\d{3,})\b(?P<rest>.*)$")
PHASE_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
PHASE_NUM_RE = re.compile(r"Phase\s+(\d+)", re.I)
STORY_RE = re.compile(r"\[(US\d+)\]")
DEP_RE = re.compile(r"depends on ([T\d,\s and]+)", re.I)
SUB_RE = re.compile(r"^###\s+")
TAG_RE = re.compile(r"\[@([\w-]+)\]")
FALLBACK = "sdd-implementer"


def _fm(text: str) -> dict:
    """Frontmatter mínimo: escalares e listas inline [a, b]."""
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    out: dict = {}
    if not m:
        return out
    for line in m.group(1).splitlines():
        kv = re.match(r"^([\w-]+):\s*(.*)$", line)
        if not kv:
            continue
        k, v = kv.group(1), kv.group(2).strip()
        if v.startswith("[") and v.endswith("]"):
            out[k] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
        else:
            out[k] = v.strip("\"'")
    return out


def load_roles(agents_dir: Path | None) -> list[dict]:
    if not agents_dir or not agents_dir.is_dir():
        return []
    roles = []
    for f in sorted(agents_dir.glob("*.md")):
        fm = _fm(f.read_text(encoding="utf-8"))
        if fm.get("kind") not in ("implementer", "reviewer"):
            continue
        roles.append({"name": fm.get("name", f.stem), "kind": fm["kind"],
                      "globs": fm.get("route_globs", []), "keywords": [k.lower() for k in fm.get("route_keywords", [])],
                      "priority": int(fm.get("priority", 0) or 0), "review_at": fm.get("review_at", "story"),
                      "owns_tests": str(fm.get("owns_tests", "")).lower() == "true"})
    return roles


def _glob_hit(path: str, globs: list[str]) -> bool:
    for g in globs:
        if fnmatch.fnmatch(path, g) or (g.startswith("**/") and fnmatch.fnmatch(path, g[3:])):
            return True
    return False


def route(task: dict, roles: list[dict], in_tests: bool) -> tuple[str, str]:
    tag = TAG_RE.search(task["desc"])
    if tag:
        return tag.group(1), "tag"
    desc = task["desc"].lower()
    best, best_key, why = FALLBACK, (0, 0), "fallback"
    for r in roles:
        if r["kind"] != "implementer":
            continue
        files = sum(_glob_hit(f, r["globs"]) for f in task["files"])
        words = sum(1 for k in r["keywords"] if re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", desc))
        if in_tests and r["name"] == "qa":
            words += 2
        if in_tests and r["owns_tests"] and files:
            words += 5  # especialista de domínio escreve os testes do próprio domínio
        score = 3 * files + words
        if score and (score, r["priority"]) > best_key:
            best, best_key, why = r["name"], (score, r["priority"]), f"score={score}"
    return best, why
EXT = r"(?:py|pyi|ts|tsx|js|jsx|mjs|go|rs|java|kt|rb|php|cs|sql|md|json|ya?ml|toml|sh|css|scss|html|vue|svelte|dart|swift|ex|exs|proto|graphql|prisma|tf)"
PATH_RE = re.compile(r"(?<![\w/])((?:[\w.@\[\]-]+/)*[\w.@\[\]-]+\." + EXT + r")(?![\w])")


def parse(path: Path) -> list[dict]:
    phases: list[dict] = []
    current = {"title": "(sem fase)", "num": None, "tasks": []}
    in_tests = False
    for line in path.read_text(encoding="utf-8").splitlines():
        m = PHASE_RE.match(line)
        if m:
            if current["tasks"] or current["title"] != "(sem fase)":
                phases.append(current)
            title = m.group("title")
            num = PHASE_NUM_RE.search(title)
            current = {"title": title, "num": int(num.group(1)) if num else None, "tasks": []}
            in_tests = bool(re.search(r"\btests?\b|\btestes?\b", title, re.I))
            continue
        if SUB_RE.match(line):
            in_tests = bool(re.search(r"\btests?\b|\btestes?\b", line, re.I))
            current["tasks"].append({"barrier": True})
            continue
        t = TASK_RE.match(line)
        if not t:
            continue
        rest = t.group("rest")
        deps = []
        d = DEP_RE.search(rest)
        if d:
            deps = re.findall(r"T\d{3,}", d.group(1))
        story = STORY_RE.search(rest)
        files = sorted({p.rstrip(".,;:)") for p in PATH_RE.findall(rest)})
        current["tasks"].append({
            "id": t.group("id"),
            "done": t.group("done").lower() == "x",
            "parallel": "[P]" in rest,
            "story": story.group(1) if story else None,
            "files": files,
            "deps": deps,
            "desc": re.sub(r"\s+", " ", rest).strip(),
            "in_tests": in_tests,
        })
    phases.append(current)
    return [p for p in phases if any(not t.get("barrier") for t in p["tasks"])]


def select_phases(phases: list[dict], mvp: bool, phase: int | None) -> list[dict]:
    if phase is not None:
        return [p for p in phases if p["num"] == phase]
    if not mvp:
        return phases
    out = []
    for p in phases:
        out.append(p)
        if "MVP" in p["title"] or re.search(r"User Story 1\b", p["title"]):
            break
    return out


def build_waves(phases: list[dict], max_parallel: int) -> list[dict]:
    waves: list[dict] = []
    for p in phases:
        open_tasks = [t for t in p["tasks"] if t.get("barrier") or not t["done"]]
        group: list[dict] = []

        def flush():
            if group:
                waves.append({"phase": p["title"], "parallel": len(group) > 1, "tasks": list(group)})
                group.clear()

        for t in open_tasks:
            if t.get("barrier"):
                flush()
                continue
            if not t["parallel"]:
                flush()
                waves.append({"phase": p["title"], "parallel": False, "tasks": [t]})
                continue
            ids = {g["id"] for g in group}
            files = {f for g in group for f in g["files"]}
            conflict = bool(set(t["files"]) & files) or bool(set(t["deps"]) & ids)
            if conflict or len(group) >= max_parallel:
                flush()
            group.append(t)
        flush()
    for i, w in enumerate(waves, 1):
        w["wave"] = i
    return waves


def _section(text: str, heading: str) -> str:
    """Do título `heading` (regex) até o próximo título do mesmo nível ou maior, fora de blocos de código."""
    lines, start, level, fence = text.splitlines(), None, 0, False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        m = None if fence else re.match(r"(#+)\s+(.*)$", ln)
        if not m:
            continue
        if start is None:
            if re.match(heading, m.group(2)):
                start, level = i, len(m.group(1))
        elif len(m.group(1)) <= level:
            return "\n".join(lines[start:i]).strip()
    return "\n".join(lines[start:]).strip() if start is not None else ""


def write_context(feature_dir: Path, stories: set[str | None]) -> dict[str | None, str]:
    """Arquivos de contexto por história; devolve {história: caminho}."""
    spec = (feature_dir / "spec.md").read_text(encoding="utf-8") if (feature_dir / "spec.md").exists() else ""
    plan = (feature_dir / "plan.md").read_text(encoding="utf-8") if (feature_dir / "plan.md").exists() else ""
    if not (spec or plan):
        return {}
    frs = "\n".join(ln for ln in spec.splitlines() if re.search(r"\bFR-\d+", ln) and ln.lstrip().startswith(("-", "*")))
    common = [_section(plan, "Technical Context"), _section(plan, "Project Structure")]
    out_dir = feature_dir / ".context"
    out_dir.mkdir(exist_ok=True)
    (out_dir / ".gitignore").write_text("*\n", encoding="utf-8")
    paths: dict[str | None, str] = {}
    for st in stories:
        parts = ["# Contexto da tarefa (gerado por waves.py; leia isto em vez de spec.md/plan.md inteiros)"]
        if st:
            parts.append(_section(spec, rf"User Story {st[2:]}\b") or f"(história {st} não encontrada em spec.md)")
        if frs:
            parts.append("## Requisitos funcionais (spec.md)\n" + frs)
        parts += [c for c in common if c]
        f = out_dir / f"{st or 'base'}.md"
        f.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
        paths[st] = str(f)
    return paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks_md", type=Path)
    ap.add_argument("--mvp", action="store_true", help="até a fase de User Story 1 / MVP")
    ap.add_argument("--phase", type=int, help="somente a fase N")
    ap.add_argument("--max-parallel", type=int, default=4)
    ap.add_argument("--agents-dir", type=Path, help="padrão: .agents/agents do repositório")
    ap.add_argument("--no-context", action="store_true", help="não grava os arquivos de contexto por história")
    a = ap.parse_args()
    if not a.tasks_md.is_file():
        print(json.dumps({"error": f"não encontrado: {a.tasks_md}"}))
        return 1
    phases = parse(a.tasks_md)
    all_tasks = [t for p in phases for t in p["tasks"] if not t.get("barrier")]
    agents_dir = a.agents_dir
    if agents_dir is None:
        for d in [a.tasks_md.resolve().parent, *a.tasks_md.resolve().parents, Path.cwd()]:
            if (d / ".agents" / "agents").is_dir():
                agents_dir = d / ".agents" / "agents"
                break
    roles = load_roles(agents_dir)
    scope = select_phases(phases, a.mvp, a.phase)
    for p in scope:
        for t in p["tasks"]:
            if not t.get("barrier"):
                t["agent"], t["routed_by"] = route(t, roles, t["in_tests"])
    waves = build_waves(scope, a.max_parallel)
    ctx = {} if a.no_context else write_context(a.tasks_md.resolve().parent, {t["story"] for w in waves for t in w["tasks"]})
    for w in waves:
        for t in w["tasks"]:
            t["context"] = ctx.get(t["story"])

    reviews = []
    scoped = [t for p in scope for t in p["tasks"] if not t.get("barrier")]
    for r in (r for r in roles if r["kind"] == "reviewer"):
        hits = [t for t in scoped if any(_glob_hit(f, r["globs"]) for f in t["files"])]
        if r["review_at"] == "converge":
            # sem globs → sempre; com globs → só se a feature tocou esses arquivos
            if not r["globs"] or hits:
                reviews.append({"agent": r["name"], "at": "converge", "stories": [],
                                "files": sorted({f for t in hits for f in t["files"] if _glob_hit(f, r["globs"])})})
            continue
        if hits:
            reviews.append({"agent": r["name"], "at": "story",
                            "stories": sorted({t["story"] or "-" for t in hits}),
                            "files": sorted({f for t in hits for f in t["files"] if _glob_hit(f, r["globs"])})})
    print(json.dumps({
        "tasks_md": str(a.tasks_md.resolve()),
        "total": len(all_tasks),
        "done": sum(t["done"] for t in all_tasks),
        "open_in_scope": sum(len(w["tasks"]) for w in waves),
        "waves": [
            {"wave": w["wave"], "phase": w["phase"], "parallel": w["parallel"],
             "tasks": [{k: t[k] for k in ("id", "agent", "routed_by", "story", "files", "desc", "context")} for t in w["tasks"]]}
            for w in waves
        ],
        "agents_dir": str(agents_dir) if agents_dir else None,
        "reviews": reviews,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
