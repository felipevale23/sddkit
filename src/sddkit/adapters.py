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
from .out import Out

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
    OUT.text(path, text)
    rel = str(path.relative_to(root))
    if all(c[0] != rel for c in OUT.conflicts):  # conflito não vira "gerenciado" (senão o próximo sync sobrescreveria)
        generated.append(rel)


def _merge_json(path: Path, mutate) -> None:
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            raise SystemExit(f"✗ {path} não é JSON válido; corrija e rode `sddkit sync` de novo.")
    mutate(data)
    OUT.text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n", managed=False)  # mescla: chaves do usuário ficam


def _same_tree(a: Path, b: Path) -> bool:
    if a.is_file() or b.is_file():
        return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()
    if not b.is_dir():
        return False
    na, nb = sorted(x.name for x in a.iterdir()), sorted(x.name for x in b.iterdir())
    return na == nb and all(_same_tree(a / n, b / n) for n in na)


def _link_or_copy(src: Path, dst: Path, mode: str, root: Path, generated: list[str]) -> str:
    """Retorna descrição da ação. Nunca sobrescreve diretório real do usuário."""
    rel = str(dst.relative_to(root))
    if dst.is_symlink() and dst.resolve() == src.resolve() and mode == "link":
        generated.append(rel)
        return "ok"
    if OUT.check:  # só compara
        generated.append(rel)
        if mode == "copy" and not dst.is_symlink() and _same_tree(src, dst):
            return "ok"
        OUT.changes.append(rel)
        return "desatualizado"
    if dst.is_symlink():
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
OUT: Out  # definido por run()


def _ondemand(root: Path, meta: dict) -> str:
    """Seção 'skills sob demanda': só as instaladas, com 1 linha cada (o corpo só é lido se a tarefa pedir)."""
    lines = []
    for name in _as_list(meta.get("skills_ondemand")):
        f = root / ".agents" / "skills" / name / "SKILL.md"
        if f.exists():
            desc = " ".join(str(parse(f.read_text(encoding="utf-8"))[0].get("description", "")).split())
            lines.append(f"- `{name}` — {desc[:110] + '…' if len(desc) > 110 else desc}")
    if not lines:
        return ""
    return ("\n## Skills sob demanda\nNão estão pré-carregadas (economia de tokens). Leia `.agents/skills/<nome>/SKILL.md` "
            "**só** se a tarefa tocar o tema:\n" + "\n".join(lines) + "\n")


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
        text = "---\n" + dump_yaml(fm) + "---\n" + GEN_NOTE.format(name=m["name"]) + "\n\n" + role["body"] + _ondemand(root, m)
        _write(root / ".claude" / "agents" / f"{m['name']}.md", text, generated, root)
    log.append(f".claude/agents: {len(load_roles(root))} subagents")

    from .memory import claude_rules
    rules = claude_rules(root)
    for path, text in rules:
        _write(path, text, generated, root)
    if rules:
        log.append(f".claude/rules: {len(rules)} memória(s) por área")

    cm = root / "CLAUDE.md"
    cur = cm.read_text(encoding="utf-8") if cm.exists() else ""
    if "@AGENTS.md" not in cur and OUT.text(cm, (cur.rstrip() + "\n\n" if cur.strip() else "") + "@AGENTS.md\n", managed=False):
        log.append("CLAUDE.md: import @AGENTS.md " + ("adicionado" if cur else "criado"))

    allow = ["Bash(.specify/scripts/bash/:*)", "Bash(bash .specify/scripts/bash/:*)",
             "Bash(.specify/extensions/git/scripts/bash/:*)",
             "Bash(bash .specify/extensions/git/scripts/bash/:*)",
             "Bash(python3 .agents/skills/sdd-build/scripts/waves.py:*)",
             "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git add:*)",
             "Bash(git commit:*)", "Read(specs/**)", "Read(.specify/**)", "Read(.agents/**)"]
    deny = ["Read(**/.env)", "Read(**/.env.local)", "Read(**/.env.*.local)", "Read(**/.env.production)",
            "Read(**/*.pem)", "Read(**/*.key)", "Read(**/id_rsa*)", "Read(**/id_ed25519*)",
            "Edit(.agents/hooks/**)", "Edit(.claude/agents/**)", "Edit(.claude/rules/sddkit-memory-*)",
            "Edit(.opencode/agents/**)",
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
        if (root / ".agents" / "skills" / "impeccable").is_dir():
            # impeccable procura PRODUCT.md/DESIGN.md na raiz; a fonte do kit é .agents/specs/ (valor do usuário vence)
            d.setdefault("env", {}).setdefault("IMPECCABLE_CONTEXT_DIR", SPECS_DIR)
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
        text = "---\n" + dump_yaml(fm) + "---\n" + GEN_NOTE.format(name=m["name"]) + "\n\n" + role["body"] + _ondemand(root, m)
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

SPECS_DIR = ".agents/specs"
DESIGN_SRC = Path(SPECS_DIR) / "DESIGN.md"


def design_md(root: Path, mode: str, generated: list[str]) -> list[str]:
    """Publica .agents/specs/DESIGN.md como DESIGN.md na raiz (formato lido por impeccable, Stitch e afins).
    Só depois de preenchido. `link`: symlink (quem escreve em DESIGN.md escreve na fonte); `copy`: cópia com hash.
    Nunca apaga um DESIGN.md que não é do sddkit nem um que divergiu da fonte."""
    src, dst = root / DESIGN_SRC, root / "DESIGN.md"
    rel = "DESIGN.md"
    adopted = []
    if (src.is_file() and "[PREENCHER" in src.read_text(encoding="utf-8") and dst.is_file()
            and not dst.is_symlink() and rel not in generated_prev and "[PREENCHER" not in dst.read_text(encoding="utf-8")):
        # ex.: `/impeccable document` escreveu DESIGN.md na raiz antes do .agents/specs/DESIGN.md ser preenchido: adota como fonte
        if OUT.check:
            OUT.changes.append(DESIGN_SRC.as_posix())
            return []
        OUT.text(src, dst.read_text(encoding="utf-8"), managed=False)
        dst.unlink()
        adopted = [f"DESIGN.md adotado como {DESIGN_SRC.as_posix()} (o template estava vazio)"]
    if not src.is_file() or "[PREENCHER" in (text := src.read_text(encoding="utf-8")):
        return []
    if mode == "copy":
        _write(dst, text, generated, root)
        if rel not in generated and rel in OUT.prev:
            generated.append(rel)  # editado à mão: o hash antigo segue protegendo; não é "obsoleto"
        return adopted + [f"DESIGN.md ← {DESIGN_SRC.as_posix()} (cópia)"]
    if dst.is_file() and not dst.is_symlink():
        ours = rel in generated_prev
        if not ours or (dst.read_text(encoding="utf-8") != text and not OUT.force):
            why = ("já existe e não é do sddkit; leve o conteúdo para " if not ours
                   else "virou arquivo e divergiu da fonte (uma ferramenta o reescreveu?); leve o que vale para ")
            OUT.conflicts.append((rel, why + DESIGN_SRC.as_posix() + " e apague o DESIGN.md da raiz"))
            if ours:
                generated.append(rel)  # senão a limpeza de obsoletos apagaria a versão divergente
            return []
    return adopted + [f"DESIGN.md → {DESIGN_SRC.as_posix()}: {_link_or_copy(src, dst, 'link', root, generated)}"]


def run(root: Path, adapters: list[str], mode: str, previous: list[str], out: Out,
        publish_design: bool = True) -> tuple[list[str], list[str]]:
    global generated_prev, OUT
    generated_prev, OUT = set(previous), out
    generated: list[str] = []
    log: list[str] = []
    # limpa arquivos gerados antes que não serão regenerados (ex.: papel removido)
    for a in adapters:
        log += [f"[{a}] {line}" for line in RUNNERS[a](root, mode, generated)]
    if publish_design:  # `"design_md": false` no sddkit.json: o DESIGN.md fica só em .agents/specs/ (a limpeza abaixo tira o da raiz)
        log += design_md(root, mode, generated)
    for rel in sorted(generated_prev - set(generated)):
        p = root / rel
        if (p.is_symlink() or p.exists()) and out.remove(p):
            log.append(f"removido (obsoleto): {rel}")
    return generated, log
