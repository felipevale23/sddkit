"""Adaptadores: projetam .agents/ (fonte única) no formato de cada ferramenta.

Nativos (leem AGENTS.md e .agents/skills sem adaptador): Codex, Cursor, GitHub Copilot,
Amp, Zed, Kilo, Antigravity, Droid... — para eles subagents caem no fallback do AGENTS.md
(executar o papel inline).
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .frontmatter import dump_yaml, parse

GEN_NOTE = "<!-- Gerado por `sddkit sync` a partir de .agents/agents/{name}.md — edite lá, não aqui. -->"

CLAUDE_TOOLS = {
    "read": ["Read", "Grep", "Glob"],
    "write": ["Write"],
    "edit": ["Edit"],
    "shell": ["Bash"],
    "web": ["WebSearch", "WebFetch"],
}
CLAUDE_TIER = {"fast": ("sonnet", "medium"), "strong": ("opus", "high")}

ADAPTERS = {
    "claude": "Claude Code — .claude/skills → .agents/skills, .claude/agents gerados, CLAUDE.md importa AGENTS.md",
    "opencode": "OpenCode — .opencode/agents gerados (AGENTS.md e .agents/skills são nativos)",
    "gemini": "Gemini CLI — .gemini/settings.json passa a ler AGENTS.md (.agents/skills é nativo)",
}
NATIVE = "Codex, Cursor, GitHub Copilot, Amp, Zed, Kilo, Antigravity, Droid (AGENTS.md + .agents/skills nativos)"


def load_roles(root: Path) -> list[dict]:
    roles = []
    for f in sorted((root / ".agents" / "agents").glob("*.md")):
        meta, body = parse(f.read_text(encoding="utf-8"))
        meta.setdefault("name", f.stem)
        roles.append({"meta": meta, "body": body.strip() + "\n", "path": f})
    return roles


def _as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _write(path: Path, text: str, generated: list[str], root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    generated.append(str(path.relative_to(root)))


def _merge_json(path: Path, mutate) -> None:
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            raise SystemExit(f"✗ {path} não é JSON válido; corrija e rode `sddkit sync` de novo.")
    mutate(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _link_or_copy(src: Path, dst: Path, mode: str, root: Path, generated: list[str]) -> str:
    """Retorna descrição da ação. Nunca sobrescreve diretório real do usuário."""
    if dst.is_symlink():
        if dst.resolve() == src.resolve() and mode == "link":
            generated.append(str(dst.relative_to(root)))
            return "ok"
        dst.unlink()
    elif dst.exists():
        rel = str(dst.relative_to(root))
        if rel in generated_prev:
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        else:
            return "mantido (já existe, não gerenciado)"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "link":
        dst.symlink_to(os.path.relpath(src, dst.parent), target_is_directory=src.is_dir())
    else:
        shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
    generated.append(str(dst.relative_to(root)))
    return "criado"


generated_prev: set[str] = set()


def claude(root: Path, mode: str, generated: list[str]) -> list[str]:
    log = []
    skills_src = root / ".agents" / "skills"
    cs = root / ".claude" / "skills"
    if mode == "link" and (not cs.exists() or cs.is_symlink()):
        log.append(f".claude/skills → .agents/skills: {_link_or_copy(skills_src, cs, 'link', root, generated)}")
    else:
        # diretório real (skills próprias do Claude ou modo cópia): uma entrada por skill
        n = 0
        for s in sorted(p for p in skills_src.iterdir() if p.is_dir()):
            r = _link_or_copy(s, cs / s.name, mode, root, generated)
            n += r in ("ok", "criado")
        log.append(f".claude/skills: {n} skills ({mode})")

    have_skills = {p.name for p in skills_src.iterdir() if (p / "SKILL.md").exists()}
    for role in load_roles(root):
        m = role["meta"]
        tools: list[str] = []
        for cap in _as_list(m.get("capabilities")):
            tools += CLAUDE_TOOLS.get(cap, [])
        model, effort = CLAUDE_TIER.get(m.get("tier", "fast"), ("inherit", None))
        fm = {"name": m["name"], "description": m.get("description", ""),
              "tools": ", ".join(dict.fromkeys(tools)) or None,
              "disallowedTools": "Agent", "model": model, "effort": effort,
              "skills": [x for x in _as_list(m.get("skills")) if x in have_skills] or None,
              "maxTurns": m.get("max_turns"), "color": m.get("color")}
        text = "---\n" + dump_yaml(fm) + "---\n" + GEN_NOTE.format(name=m["name"]) + "\n\n" + role["body"]
        _write(root / ".claude" / "agents" / f"{m['name']}.md", text, generated, root)
    log.append(f".claude/agents: {len(load_roles(root))} subagents")

    from .memory import claude_rules
    rules = claude_rules(root)
    for path, text in rules:
        _write(path, text, generated, root)
    if rules:
        log.append(f".claude/rules: {len(rules)} memória(s) por área")

    cm = root / "CLAUDE.md"
    if not cm.exists():
        cm.write_text("@AGENTS.md\n", encoding="utf-8")
        log.append("CLAUDE.md criado (@AGENTS.md)")
    elif "@AGENTS.md" not in cm.read_text(encoding="utf-8"):
        with cm.open("a", encoding="utf-8") as fh:
            fh.write("\n@AGENTS.md\n")
        log.append("CLAUDE.md: import @AGENTS.md adicionado")

    allow = ["Bash(.specify/scripts/bash/:*)", "Bash(bash .specify/scripts/bash/:*)",
             "Bash(.specify/extensions/git/scripts/bash/:*)",
             "Bash(bash .specify/extensions/git/scripts/bash/:*)",
             "Bash(python3 .agents/skills/sdd-build/scripts/waves.py:*)",
             "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git add:*)",
             "Bash(git commit:*)", "Read(specs/**)", "Read(.specify/**)", "Read(.agents/**)"]
    deny = ["Read(**/.env)", "Read(**/.env.local)", "Read(**/.env.*.local)", "Read(**/.env.production)",
            "Read(**/*.pem)", "Read(**/*.key)", "Read(**/id_rsa*)", "Read(**/id_ed25519*)",
            "Edit(.agents/hooks/**)",
            "Edit(.agents/skills/speckit-*/**)", "Edit(.specify/scripts/**)",
            "Edit(.specify/templates/**)", "Bash(git push --force:*)", "Bash(git push -f:*)"]

    def mutate(d):
        p = d.setdefault("permissions", {})
        for key, vals in (("allow", allow), ("deny", deny)):
            cur = p.setdefault(key, [])
            cur += [v for v in vals if v not in cur]
        guard = root / ".agents" / "hooks" / "guard_secrets.py"
        if guard.exists():
            cmd = 'python3 "$CLAUDE_PROJECT_DIR/.agents/hooks/guard_secrets.py"'
            pre = d.setdefault("hooks", {}).setdefault("PreToolUse", [])
            if not any(h.get("command") == cmd for e in pre for h in e.get("hooks", [])):
                pre.append({"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": cmd}]})
    _merge_json(root / ".claude" / "settings.json", mutate)
    log.append(".claude/settings.json: permissões + hook guard_secrets mesclados")
    return log


def opencode(root: Path, mode: str, generated: list[str]) -> list[str]:
    roles = load_roles(root)
    for role in roles:
        m = role["meta"]
        caps = set(_as_list(m.get("capabilities")))
        fm = {"description": m.get("description", ""), "mode": "subagent",
              "permission": {"edit": "allow" if caps & {"edit", "write"} else "deny",
                             "bash": "allow" if "shell" in caps else "deny",
                             "webfetch": "allow" if "web" in caps else "deny"},
              "steps": m.get("max_turns")}
        text = "---\n" + dump_yaml(fm) + "---\n" + GEN_NOTE.format(name=m["name"]) + "\n\n" + role["body"]
        _write(root / ".opencode" / "agents" / f"{m['name']}.md", text, generated, root)
    return [f".opencode/agents: {len(roles)} subagents"]


def gemini(root: Path, mode: str, generated: list[str]) -> list[str]:
    def mutate(d):
        ctx = d.setdefault("context", {})
        names = ctx.get("fileName", [])
        names = [names] if isinstance(names, str) else list(names)
        for n in ("AGENTS.md", "GEMINI.md"):
            if n not in names:
                names.append(n)
        ctx["fileName"] = names
    _merge_json(root / ".gemini" / "settings.json", mutate)
    return [".gemini/settings.json: context.fileName inclui AGENTS.md"]


RUNNERS = {"claude": claude, "opencode": opencode, "gemini": gemini}


def run(root: Path, adapters: list[str], mode: str, previous: list[str]) -> tuple[list[str], list[str]]:
    global generated_prev
    generated_prev = set(previous)
    generated: list[str] = []
    log: list[str] = []
    # limpa arquivos gerados antes que não serão regenerados (ex.: papel removido)
    for a in adapters:
        log += [f"[{a}] {line}" for line in RUNNERS[a](root, mode, generated)]
    for rel in sorted(generated_prev - set(generated)):
        p = root / rel
        if p.is_symlink() or p.is_file():
            p.unlink()
            log.append(f"removido (obsoleto): {rel}")
        elif p.is_dir():
            shutil.rmtree(p)
            log.append(f"removido (obsoleto): {rel}")
    return generated, log
