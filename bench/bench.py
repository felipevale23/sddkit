#!/usr/bin/env python3
"""Benchmark do sddkit num repositório real (determinístico; não roda agente de IA).

Clona o repositório numa pasta temporária (só arquivos versionados: nada de .env) e mede:
adoção (init/sync/doctor/--fix), idempotência, detecção de stack, ondas e roteamento do
/sdd-build em todas as features, economia dos arquivos de contexto, orçamento de tokens,
o hook de commit contra o histórico real e a guarda de segredos contra os arquivos versionados.

    python bench/bench.py <caminho-do-repo> [--with-skills] [--commits 300] [--out relatorio.md]

`--with-skills` instala as skills recomendadas (rede, `npx skills`) para medir o orçamento real.
Nenhum valor de segredo é impresso: a guarda reporta só tipo e linha.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
HOOKS = SRC / "sddkit" / "templates" / "hooks"
ENV = {**os.environ, "PYTHONPATH": str(SRC), "NO_COLOR": "1"}


def run(cwd: Path, *args: str) -> tuple[subprocess.CompletedProcess, float]:
    t = time.perf_counter()
    r = subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, text=True)
    return r, time.perf_counter() - t


def sdd(cwd: Path, *args: str) -> tuple[subprocess.CompletedProcess, float]:
    return run(cwd, sys.executable, "-m", "sddkit", *args)


def snapshot(root: Path) -> dict[str, str]:
    import hashlib
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts}


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def marks(out: str, section: str) -> tuple[int, int]:
    part = out.split(section, 1)[1] if section in out else ""
    part = re.split(r"\n\n[A-ZÁÉÍ][^\n]*:\n", part, maxsplit=1)[0]
    return part.count("✓"), part.count("✗")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    ap.add_argument("--with-skills", action="store_true")
    ap.add_argument("--commits", type=int, default=300)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="sddkit-bench-"))
    root = tmp / "repo"
    subprocess.run(["git", "clone", "-q", "--no-local", str(a.repo.resolve()), str(root)], check=True)
    rep: dict = {"repo": a.repo.name, "tracked_files": len(subprocess.run(["git", "ls-files"], cwd=root,
                                                                          capture_output=True, text=True).stdout.split())}

    # 1. detecção
    r, t = sdd(root, "suggest", "--json")
    d = json.loads(r.stdout)
    rep["detect"] = {"s": t, "stacks": d["project"]["stacks"], "evidence": len(d["project"]["evidence"]),
                     "skills_suggested": len(d["skills"]), "skills_recommended": sum(s["recommended"] for s in d["skills"]),
                     "roles_suggested": [x["id"] for x in d["roles"]]}

    # 2. doctor antes, --fix, adoção (init) e idempotência
    r, t = sdd(root, "doctor")
    rep["doctor_before"] = {"s": t, "drift": marks(r.stdout, "Specs (drift):")}
    r, t = sdd(root, "doctor", "--fix")
    rep["fix"] = {"s": t, "applied": int(re.search(r"(\d+) correção", r.stdout).group(1))}
    roles = ",".join(rep["detect"]["roles_suggested"]) or "none"
    init = ["init", "-y", "--no-speckit", "--agents", "claude", "--roles", roles,
            "--skills", "recommended" if a.with_skills else "none"]
    r, t = sdd(root, *init)
    rep["init"] = {"s": t, "ok": r.returncode == 0, "roles": roles.split(",")}
    before = snapshot(root)
    r1, t1 = sdd(root, "sync")
    r2, t2 = sdd(root, "sync", "--check")
    r3, t3 = sdd(root, *init)
    rep["idempotence"] = {"sync_s": t1, "check_s": t2, "check_exit": r2.returncode,
                          "changed_after_sync_and_reinit": sorted(set(snapshot(root).items()) ^ set(before.items()))[:5]}
    r, t = sdd(root, "doctor")
    rep["doctor_after"] = {"s": t, "drift": marks(r.stdout, "Specs (drift):"),
                           "source_of_truth": marks(r.stdout, "Fonte única"), "fails": [ln.strip() for ln in r.stdout.splitlines() if "✗" in ln]}
    r, t = sdd(root, "doctor", "--fix")
    rep["fix_again"] = int(re.search(r"(\d+) correção", r.stdout).group(1))

    # 3. ondas, roteamento e contexto em todas as features (tarefas reabertas na cópia)
    feats = []
    route = collections.Counter()
    for f in sorted((root / ".agents/specs/features").glob("[0-9]*")):
        tasks = [p for p in f.glob("tasks*.md")]
        if not tasks:
            continue
        tm = tasks[0]
        tm.write_text(re.sub(r"- \[[xX]\]", "- [ ]", tm.read_text(encoding="utf-8")), encoding="utf-8")
        r, t = run(root, sys.executable, str(root / ".agents/skills/sdd-build/scripts/waves.py"), str(tm))
        if r.returncode != 0:
            feats.append({"feature": f.name, "error": r.stdout[:200]})
            continue
        w = json.loads(r.stdout)
        ts = [x for wave in w["waves"] for x in wave["tasks"]]
        for x in ts:
            route[(x["agent"], x["routed_by"].split("=")[0])] += 1
        full = sum(len(p.read_text(encoding="utf-8")) for p in (f / "spec.md", f / "plan.md") if p.exists()) // 4
        ctx = [len(Path(x["context"]).read_text(encoding="utf-8")) // 4 for x in ts if x.get("context")]
        feats.append({"feature": f.name, "s": t, "tasks": len(ts), "waves": len(w["waves"]),
                      "parallel_waves": sum(wv["parallel"] for wv in w["waves"]), "reviews": [x["agent"] for x in w["reviews"]],
                      "with_story": sum(1 for x in ts if x["story"]), "doc_tokens": full,
                      "ctx_avg": sum(ctx) // len(ctx) if ctx else None})
    rep["waves"] = feats
    rep["routing"] = sorted(([f"{k[0]} ({k[1]})", v] for k, v in route.items()), key=lambda x: -x[1])

    # 4. orçamento de tokens
    r, t = sdd(root, "budget", "--json")
    b = json.loads(r.stdout)
    rep["budget"] = {"session": b["session"], "roles": [(x["role"], x["total"], list(x["preload"])) for x in b["roles"]]}

    # 5. hook de commit contra o histórico real
    cm = load("commit_msg")
    msgs = subprocess.run(["git", "log", f"-{a.commits}", "--format=%B%x00"], cwd=root, capture_output=True, text=True).stdout.split("\x00")
    msgs = [m.strip() for m in msgs if m.strip()]
    rep["commits"] = {"checked": len(msgs), "conventional_ok": sum(not [p for p in cm.problems(m, True) if "cabeçalho" in p] for m in msgs),
                      "ai_attribution": sum(bool(cm.problems(m)) for m in msgs),
                      "examples_bad_header": [m.splitlines()[0][:70] for m in msgs if [p for p in cm.problems(m, True) if "cabeçalho" in p]][:5]}

    # 6. guarda de segredos contra os arquivos versionados (só tipo e linha, nunca o valor)
    gs = load("guard_secrets")
    hits = collections.Counter()
    files_hit = []
    for rel in subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True).stdout.split():
        p = root / rel
        if rel.endswith(gs.ALLOW_SUFFIX) or not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found = gs.scan(text)
        for h in found:
            hits[h.split(": ", 1)[1]] += 1
        if found:
            files_hit.append(f"{rel} ({len(found)})")
    rep["guard"] = {"hits_by_type": dict(hits), "files": files_hit[:15], "files_total": len(files_hit)}

    md = render(rep)
    if a.out:
        a.out.write_text(md, encoding="utf-8")
    print(md)
    return 0


def render(r: dict) -> str:
    L = [f"# Benchmark do sddkit — {r['repo']} ({r['tracked_files']} arquivos versionados)", ""]
    d = r["detect"]
    L += ["## Detecção", f"- stacks: {', '.join(d['stacks'])} ({d['evidence']} evidências, {d['s']:.2f}s)",
          f"- skills sugeridas: {d['skills_suggested']} ({d['skills_recommended']} recomendadas) · papéis sugeridos: {', '.join(d['roles_suggested'])}", ""]
    L += ["## Adoção e fonte única", "| Etapa | Resultado | Tempo |", "|---|---|---|",
          f"| doctor antes | drift ✓{r['doctor_before']['drift'][0]} ✗{r['doctor_before']['drift'][1]} | {r['doctor_before']['s']:.2f}s |",
          f"| doctor --fix | {r['fix']['applied']} correções | {r['fix']['s']:.2f}s |",
          f"| init (papéis: {', '.join(r['init']['roles'])}) | {'ok' if r['init']['ok'] else 'FALHOU'} | {r['init']['s']:.2f}s |",
          f"| sync / sync --check | exit {r['idempotence']['check_exit']} | {r['idempotence']['sync_s']:.2f}s / {r['idempotence']['check_s']:.2f}s |",
          f"| sync + init de novo mudam arquivos? | {'não' if not r['idempotence']['changed_after_sync_and_reinit'] else r['idempotence']['changed_after_sync_and_reinit']} | |",
          f"| doctor depois | drift ✓{r['doctor_after']['drift'][0]} ✗{r['doctor_after']['drift'][1]} · fonte única ✓{r['doctor_after']['source_of_truth'][0]} ✗{r['doctor_after']['source_of_truth'][1]} | {r['doctor_after']['s']:.2f}s |",
          f"| doctor --fix de novo | {r['fix_again']} correções | |", "",
          "Pendências restantes: " + ("; ".join(r["doctor_after"]["fails"]) or "nenhuma"), ""]
    L += ["## /sdd-build: ondas, paralelismo e contexto", "| Feature | Tarefas | Ondas | Paralelas | Com história | spec+plan | contexto médio | Revisores |", "|---|---|---|---|---|---|---|---|"]
    for f in r["waves"]:
        if "error" in f:
            L.append(f"| {f['feature']} | erro: {f['error']} |"); continue
        L.append(f"| {f['feature']} | {f['tasks']} | {f['waves']} | {f['parallel_waves']} | {f['with_story']} | {f['doc_tokens']} | {f['ctx_avg'] or '—'} | {', '.join(f['reviews']) or '—'} |")
    L += ["", "Roteamento (papel, critério): " + ", ".join(f"{k} {v}" for k, v in r["routing"]), ""]
    s = r["budget"]["session"]
    L += ["## Tokens", f"- por sessão ≈ {s['total']} (AGENTS.md {s['agents_md']} + descrições de {s['skills']} skills {s['skill_descriptions']})",
          "- por tarefa: " + ", ".join(f"{n} ≈{t}" for n, t, _ in r["budget"]["roles"]), ""]
    c = r["commits"]
    L += ["## Hook de commit no histórico real", f"- {c['checked']} commits: {c['conventional_ok']} em Conventional Commits, {c['ai_attribution']} com atribuição de IA",
          "- exemplos fora do padrão: " + ("; ".join(f"`{x}`" for x in c["examples_bad_header"]) or "—"), ""]
    g = r["guard"]
    L += ["## Guarda de segredos nos arquivos versionados", f"- achados por tipo: {g['hits_by_type'] or 'nenhum'} em {g['files_total']} arquivo(s)",
          "- arquivos: " + (", ".join(g["files"]) or "—")]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
