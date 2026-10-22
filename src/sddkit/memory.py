"""Memória manual do projeto em .agents/memory/<tópico>.md.

Formato de cada arquivo:
    ---
    topic: bill-parser
    description: convenções dos parsers de fatura
    paths: ["services/bill-parser/**"]     # opcional — sem paths = vale para o projeto todo
    ---
    - um fato por linha

Tópicos globais entram no AGENTS.md (todas as ferramentas). Tópicos com `paths`
entram como ponteiro no AGENTS.md e, no Claude, viram .claude/rules/ com `paths:`
(carregados só quando o agente mexe nesses arquivos).
"""
from __future__ import annotations

import re
from pathlib import Path

from .frontmatter import dump_yaml, parse

MEM_DIR = Path(".agents") / "memory"


def slug(s: str) -> str:
    s = re.sub(r"[^\w-]+", "-", s.strip().lower(), flags=re.UNICODE).strip("-")
    return s or "geral"


def load(root: Path) -> list[dict]:
    out = []
    for f in sorted((root / MEM_DIR).glob("*.md")):
        meta, body = parse(f.read_text(encoding="utf-8"))
        facts = [ln[2:].strip() for ln in body.splitlines() if ln.startswith("- ")]
        paths = meta.get("paths") or []
        out.append({"topic": meta.get("topic") or f.stem, "description": meta.get("description", ""),
                    "paths": paths if isinstance(paths, list) else [paths], "facts": facts, "file": f})
    return out


def _write(f: Path, topic: str, description: str, paths: list[str], facts: list[str]) -> None:
    meta = {"topic": topic, "description": description or None}
    head = dump_yaml(meta)
    if paths:
        head += "paths: [" + ", ".join(f'"{p}"' for p in paths) + "]\n"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\n" + head + "---\n\n" + "".join(f"- {x}\n" for x in facts), encoding="utf-8")


def add(root: Path, text: str, topic: str, paths: list[str] | None, description: str | None) -> str:
    t = slug(topic)
    f = root / MEM_DIR / f"{t}.md"
    cur = next((m for m in load(root) if m["file"] == f), None)
    facts = cur["facts"] if cur else []
    cur_paths = cur["paths"] if cur else []
    if cur and paths is not None and sorted(paths) != sorted(cur_paths):
        raise SystemExit(f"✗ o tópico '{t}' já vale para {cur_paths or 'o projeto todo'}; "
                         f"use outro --topic ou edite {f.relative_to(root)}")
    text = re.sub(r"\s+", " ", text).strip()
    if text in facts:
        return f"· já existe em {t}"
    facts.append(text)
    _write(f, t, description or (cur["description"] if cur else ""), paths if paths is not None else cur_paths, facts)
    return f"✓ {t}: {text}"


def remove(root: Path, topic: str, index: int | None) -> str:
    t = slug(topic)
    f = root / MEM_DIR / f"{t}.md"
    if not f.exists():
        raise SystemExit(f"✗ tópico '{t}' não existe")
    if index is None:
        f.unlink()
        return f"✓ tópico {t} removido"
    m = next(m for m in load(root) if m["file"] == f)
    if not 1 <= index <= len(m["facts"]):
        raise SystemExit(f"✗ {t} tem {len(m['facts'])} item(ns)")
    gone = m["facts"].pop(index - 1)
    if not m["facts"]:
        f.unlink()
        return f"✓ removido de {t}: {gone} (tópico vazio apagado)"
    _write(f, t, m["description"], m["paths"], m["facts"])
    return f"✓ removido de {t}: {gone}"


def render_agents_block(root: Path) -> str:
    mems = [m for m in load(root) if m["facts"]]
    if not mems:
        return ""
    lines = ["## Memória do projeto", "",
             "Fatos e convenções registrados pela equipe (`sddkit memory`). Valem acima de suposições suas.", ""]
    for m in (m for m in mems if not m["paths"]):
        lines.append(f"### {m['topic']}" + (f" — {m['description']}" if m["description"] else ""))
        lines += [f"- {x}" for x in m["facts"]] + [""]
    scoped = [m for m in mems if m["paths"]]
    if scoped:
        lines += ["### Por área (leia antes de editar esses caminhos)", ""]
        for m in scoped:
            globs = ", ".join(f"`{p}`" for p in m["paths"])
            lines.append(f"- {globs} → `{m['file'].relative_to(root).as_posix()}` ({len(m['facts'])} itens)"
                         + (f" — {m['description']}" if m["description"] else ""))
    return "\n".join(lines).rstrip() + "\n"


def claude_rules(root: Path) -> list[tuple[Path, str]]:
    """Arquivos .claude/rules/ para tópicos com paths (carregamento sob demanda no Claude Code)."""
    out = []
    for m in load(root):
        if not m["paths"] or not m["facts"]:
            continue
        head = "paths:\n" + "".join(f'  - "{p}"\n' for p in m["paths"])
        body = f"# Memória: {m['topic']}\n<!-- Gerado por `sddkit sync` a partir de {m['file'].relative_to(root).as_posix()} — edite lá. -->\n\n"
        body += "".join(f"- {x}\n" for x in m["facts"])
        out.append((root / ".claude" / "rules" / f"sddkit-memory-{m['topic']}.md", "---\n" + head + "---\n" + body))
    return out
