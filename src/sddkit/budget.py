"""Orçamento de tokens do projeto: o que entra em toda sessão e o que cada subagent carrega por tarefa.

Estimativa ≈ caracteres / 4 (boa para comparar; o número exato depende do tokenizador do modelo).
"""
from __future__ import annotations

from pathlib import Path

from .frontmatter import parse

SESSION_WARN = 6000   # AGENTS.md + descrições de skills, pago em toda sessão
PRELOAD_WARN = 8000   # prompt do papel + skills pré-carregadas, pago em toda tarefa daquele papel


def tok(text: str) -> int:
    return len(text) // 4


def _skills(root: Path) -> dict[str, dict]:
    out = {}
    for f in sorted((root / ".agents" / "skills").glob("*/SKILL.md")):
        text = f.read_text(encoding="utf-8")
        meta, _ = parse(text)
        name = str(meta.get("name") or f.parent.name)
        desc = " ".join(str(meta.get("description", "")).split())
        out[f.parent.name] = {"name": name, "desc": tok(name + desc) + 4, "body": tok(text)}
    return out


def report(root: Path) -> dict:
    skills = _skills(root)
    agents_md = root / "AGENTS.md"
    agents = tok(agents_md.read_text(encoding="utf-8")) if agents_md.exists() else 0
    desc = sum(s["desc"] for s in skills.values())
    roles = []
    for f in sorted((root / ".agents" / "agents").glob("*.md")):
        meta, body = parse(f.read_text(encoding="utf-8"))
        pre = [s for s in (meta.get("skills") or []) if s in skills]
        lazy = [s for s in (meta.get("skills_ondemand") or []) if s in skills]
        roles.append({"role": meta.get("name", f.stem), "prompt": tok(body),
                      "preload": {s: skills[s]["body"] for s in pre},
                      "total": tok(body) + sum(skills[s]["body"] for s in pre),
                      "ondemand": lazy})
    return {
        "session": {"agents_md": agents, "skill_descriptions": desc, "total": agents + desc, "skills": len(skills)},
        "top_descriptions": sorted(((n, s["desc"]) for n, s in skills.items()), key=lambda x: -x[1])[:5],
        "roles": sorted(roles, key=lambda r: -r["total"]),
        "largest_skills": sorted(((n, s["body"]) for n, s in skills.items()), key=lambda x: -x[1])[:5],
    }


def _n(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def render(r: dict) -> list[str]:
    s = r["session"]
    out = [f"Por sessão (todo agente, toda conversa): ≈ {_n(s['total'])} tokens",
           f"  AGENTS.md ≈ {_n(s['agents_md'])} · descrições de {s['skills']} skills ≈ {_n(s['skill_descriptions'])}",
           "  descrições mais caras: " + ", ".join(f"{n} {_n(t)}" for n, t in r["top_descriptions"]),
           "", "Por tarefa, em cada subagent (prompt + skills pré-carregadas):"]
    for ro in r["roles"]:
        flag = "  ⚠" if ro["total"] > PRELOAD_WARN else ""
        pre = ", ".join(f"{n} {_n(t)}" for n, t in ro["preload"].items()) or "nenhuma"
        lazy = f" · sob demanda: {len(ro['ondemand'])}" if ro["ondemand"] else ""
        out.append(f"  {ro['role']:22} ≈ {_n(ro['total']):>6}  (pré-carga: {pre}{lazy}){flag}")
    out += ["", "Maiores skills (custam só quando usadas): " + ", ".join(f"{n} {_n(t)}" for n, t in r["largest_skills"])]
    return out


def checks(r: dict) -> list[tuple[bool, str, str, list[str]]]:
    s = r["session"]
    heavy = [f"{ro['role']} ≈ {ro['total']}" for ro in r["roles"] if ro["total"] > PRELOAD_WARN]
    return [
        (s["total"] <= SESSION_WARN, f"custo por sessão ≈ {s['total']} tokens (limite {SESSION_WARN})",
         "remova skills que não usa (descrições custam em toda sessão) ou mova fatos para memória com --paths", []),
        (not heavy, f"pré-carga dos subagents ≤ {PRELOAD_WARN} tokens por tarefa",
         "passe skills de `skills:` para `skills_ondemand:` no papel e rode `sddkit sync`", heavy),
    ]


