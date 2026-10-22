#!/usr/bin/env python3
"""Benchmark com agente de IA de verdade: o mesmo pedido com e sem o fluxo do sddkit.

Roda o Claude Code em modo headless (`claude -p`) numa cópia nova do repositório para cada execução.
Funciona com assinatura (login claude.ai) — não precisa de créditos de API —, mas consome o limite
de uso do plano: uma execução com sddkit (`/sdd-feature` + `/sdd-build --mvp`) pode levar dezenas
de minutos.

Isolamento e segurança:
- clone só com arquivos versionados (nada de .env) e **sem remote** (o agente não consegue dar push);
- `--setting-sources project`: não carrega suas configurações, plugins, hooks nem CLAUDE.md pessoais;
- `--permission-mode dontAsk` com lista de permissões: edição de arquivos, git (sem push),
  gerenciador de pacotes/testes e scripts do projeto; sem acesso à web.

    python bench/agent.py <repo> --request pedido.md [--variants sddkit,baseline] [--runs 1]
        [--setup "npm ci"] [--test "npm test"] [--model <modelo>] [--timeout 5400] [--out relatorio.md]
    python bench/agent.py <repo> --smoke     # 1 pergunta curta: confere login, isolamento e medição
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
ALLOWED = ["Read", "Grep", "Glob", "Edit", "Write", "MultiEdit", "TodoWrite", "Task", "Agent", "Skill",
           "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git add:*)", "Bash(git commit:*)",
           "Bash(git show:*)", "Bash(git rev-parse:*)", "Bash(git branch:*)", "Bash(git checkout:*)", "Bash(git switch:*)",
           "Bash(ls:*)", "Bash(cat:*)", "Bash(mkdir:*)", "Bash(npm:*)", "Bash(npx:*)", "Bash(pnpm:*)", "Bash(node:*)",
           "Bash(python3:*)", "Bash(uv:*)", "Bash(uvx:*)", "Bash(pytest:*)", "Bash(sddkit:*)", "Bash(bash .specify/:*)",
           "Bash(.specify/:*)"]
DENIED = ["WebFetch", "WebSearch", "Bash(git push:*)", "Bash(curl:*)", "Bash(wget:*)", "Bash(rm -rf:*)", "Bash(sudo:*)"]
BASELINE_PROMPT = ("Implemente o pedido abaixo neste repositório, com testes, seguindo as convenções existentes. "
                   "Rode os testes no fim e faça commit do resultado.\n\n{request}")


def sh(cwd: Path, cmd: str, timeout: int = 1800, env: dict | None = None) -> tuple[int, str, float]:
    t = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, **(env or {})})
        return r.returncode, r.stdout + r.stderr, time.perf_counter() - t
    except subprocess.TimeoutExpired:
        return 124, "timeout", time.perf_counter() - t


def claude(cwd: Path, prompt: str, model: str | None, timeout: int) -> dict:
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--setting-sources", "project",
           "--permission-mode", "dontAsk", "--allowedTools", *ALLOWED, "--disallowedTools", *DENIED,
           "--no-session-persistence"]
    if model:
        cmd += ["--model", model]
    t = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        out = r.stdout
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    wall = time.perf_counter() - t
    try:
        j = json.loads(out.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"ok": False, "wall_s": wall, "error": out[-500:]}
    u = j.get("usage", {})
    return {"ok": not j.get("is_error"), "wall_s": wall, "turns": j.get("num_turns"),
            "input": u.get("input_tokens", 0), "output": u.get("output_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0),
            "cost_estimate_usd": j.get("total_cost_usd"), "denials": len(j.get("permission_denials", []) or []),
            "result": (j.get("result") or "")[:400]}


def fresh_clone(repo: Path) -> Path:
    d = Path(tempfile.mkdtemp(prefix="sddkit-agent-")) / "repo"
    subprocess.run(["git", "clone", "-q", "--no-local", str(repo), str(d)], check=True)
    subprocess.run(["git", "remote", "remove", "origin"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "bench"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "bench@localhost"], cwd=d, check=True)
    return d


def add(a: dict, b: dict) -> dict:
    keys = ("wall_s", "turns", "input", "output", "cache_read", "cache_write", "cost_estimate_usd", "denials")
    return {k: (a.get(k) or 0) + (b.get(k) or 0) for k in keys} | {"ok": a.get("ok", True) and b.get("ok", True)}


def run_variant(repo: Path, variant: str, request: str, a) -> dict:
    root = fresh_clone(repo)
    rec: dict = {"variant": variant, "dir": str(root)}
    if a.setup:
        rc, _, s = sh(root, a.setup, timeout=3600)
        rec["setup"] = {"exit": rc, "s": round(s)}
    start = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    total: dict = {}
    if variant == "sddkit":
        env = {"PYTHONPATH": str(SRC)}
        rc, out, s = sh(root, f"{shlex.quote(sys.executable)} -m sddkit init -y --agents claude --roles recommended "
                              f"--skills recommended", timeout=1800, env=env)
        rec["init"] = {"exit": rc, "s": round(s)}
        subprocess.run(["git", "add", "-A"], cwd=root)
        subprocess.run(["git", "commit", "-qm", "chore: sddkit init"], cwd=root)
        start = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
        steps = [("sdd-feature", f"/sdd-feature {request} --auto --no-grill"), ("sdd-build", "/sdd-build --mvp")]
    else:
        steps = [("implement", BASELINE_PROMPT.format(request=request))]
    rec["steps"] = {}
    for name, prompt in steps:
        r = claude(root, prompt, a.model, a.timeout)
        rec["steps"][name] = r
        total = add(total, r)
        if not r["ok"]:
            break
    rec["total"] = total
    rec["changed"] = subprocess.run(["git", "diff", "--shortstat", start], cwd=root, capture_output=True, text=True).stdout.strip()
    rec["commits"] = int(subprocess.run(["git", "rev-list", "--count", f"{start}..HEAD"], cwd=root,
                                        capture_output=True, text=True).stdout.strip() or 0)
    if a.test:
        rc, out, s = sh(root, a.test, timeout=3600)
        nums = re.findall(r"(\d+) (passed|failed)", out)
        rec["tests"] = {"exit": rc, "counts": nums[-2:], "s": round(s)}
    if variant == "sddkit":
        feats = sorted((root / ".agents/specs/features").glob("[0-9]*"), key=lambda p: p.stat().st_mtime)
        new = feats[-1] if feats else None
        rec["artifacts"] = sorted(p.name for p in new.iterdir()) if new else []
        rc, out, _ = sh(root, f"{shlex.quote(sys.executable)} -m sddkit doctor", env={"PYTHONPATH": str(SRC)})
        rec["doctor_fails"] = [ln.strip() for ln in out.splitlines() if "✗" in ln]
    return rec


def render(recs: list[dict], request: str) -> str:
    L = ["# Benchmark com agente (Claude Code headless)", "", f"Pedido: {request[:300]}", "",
         "| Variante | ok | Tempo | Turnos | Tokens entrada (+cache lido) | Saída | Custo estimado* | Commits | Mudanças | Testes |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in recs:
        t = r["total"]
        tests = r.get("tests", {})
        L.append(f"| {r['variant']} | {'sim' if t.get('ok') else 'não'} | {t.get('wall_s', 0) / 60:.1f} min | {t.get('turns')} | "
                 f"{t.get('input', 0) + t.get('cache_write', 0):,} (+{t.get('cache_read', 0):,}) | {t.get('output', 0):,} | "
                 f"${t.get('cost_estimate_usd') or 0:.2f} | {r.get('commits')} | {r.get('changed') or '—'} | "
                 f"{'exit ' + str(tests.get('exit')) + ' ' + str(tests.get('counts')) if tests else '—'} |")
    L += ["", "*Na assinatura não há cobrança por token: o custo estimado só indica o peso no limite do plano.", ""]
    for r in recs:
        L.append(f"## {r['variant']}")
        for name, s in r.get("steps", {}).items():
            L.append(f"- `{name}`: {'ok' if s.get('ok') else 'falhou'}, {s.get('wall_s', 0) / 60:.1f} min, {s.get('turns')} turnos, "
                     f"{s.get('denials', 0)} permissões negadas — {(s.get('result') or s.get('error') or '')[:200]!r}")
        if r.get("artifacts") is not None:
            L.append(f"- artefatos da feature: {', '.join(r['artifacts']) or '—'}")
            L.append(f"- doctor: {len(r.get('doctor_fails', []))} pendência(s)")
        L.append(f"- cópia de trabalho: `{r['dir']}`")
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    ap.add_argument("--request", type=Path, help="arquivo com o pedido (ex.: um change request)")
    ap.add_argument("--variants", default="sddkit,baseline")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--setup", help='comando antes do agente (ex.: "npm ci")')
    ap.add_argument("--test", help='comando de testes no fim (ex.: "npm test")')
    ap.add_argument("--model")
    ap.add_argument("--timeout", type=int, default=5400, help="segundos por etapa do agente")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.smoke:
        root = fresh_clone(a.repo.resolve())
        r = claude(root, "Quantas pastas existem em .agents/specs/features? Responda só o número.", a.model, 300)
        remotes = subprocess.run(["git", "remote"], cwd=root, capture_output=True, text=True).stdout.strip()
        print(json.dumps({**r, "remotes": remotes or "(nenhum)"}, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    request = a.request.read_text(encoding="utf-8")
    recs = [run_variant(a.repo.resolve(), v, request, a) for _ in range(a.runs) for v in a.variants.split(",")]
    md = render(recs, request)
    if a.out:
        a.out.write_text(md, encoding="utf-8")
        a.out.with_suffix(".json").write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
