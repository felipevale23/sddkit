"""Parser/serializador mínimo de frontmatter YAML (só stdlib).

Suporta o subconjunto usado em SKILL.md e nos papéis: escalares, strings com aspas,
listas inline [a, b], listas em bloco (- item), blocos > e |, e um nível de mapa aninhado.
"""
from __future__ import annotations

import json
import re


def _scalar(v: str):
    v = v.strip()
    if not v:
        return ""
    if v[0] in "\"'" and v[-1] == v[0] and len(v) >= 2:
        return json.loads(v) if v[0] == '"' else v[1:-1].replace("''", "'")
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in re.split(r",\s*", inner)] if inner else []
    if v in ("true", "false"):
        return v == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def parse(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    head = text[3:end].strip("\n").splitlines()
    body = text[end + 4:].lstrip("\n")
    meta: dict = {}
    i = 0
    while i < len(head):
        line = head[i]
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2)
        if val in (">", "|", ">-", "|-"):
            parts = []
            i += 1
            while i < len(head) and (head[i].startswith(" ") or not head[i].strip()):
                parts.append(head[i].strip())
                i += 1
            meta[key] = (" " if val.startswith(">") else "\n").join(p for p in parts if p)
            continue
        if val == "":
            items, sub = [], {}
            i += 1
            while i < len(head) and (head[i].startswith(" ") or head[i].startswith("-")):
                s = head[i].strip()
                if s.startswith("- "):
                    items.append(_scalar(s[2:]))
                elif ":" in s:
                    k, v = s.split(":", 1)
                    sub[k.strip()] = _scalar(v)
                i += 1
            meta[key] = items if items else sub
            continue
        meta[key] = _scalar(val)
        i += 1
    return meta, body


def dump_yaml(d: dict, indent: int = 0) -> str:
    out = []
    pad = " " * indent
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            out.append(f"{pad}{k}:\n" + dump_yaml(v, indent + 2).rstrip("\n"))
        elif isinstance(v, list):
            out.append(f"{pad}{k}:" + "".join(f"\n{pad}  - {x}" for x in v))
        elif isinstance(v, bool):
            out.append(f"{pad}{k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            out.append(f"{pad}{k}: {v}")
        else:
            s = str(v)
            needs_quote = (not s or re.search(r"[:#\[\]{}&*!|>'\"%@`,]", s) or s != s.strip()
                           or s.lower() in ("true", "false", "null", "yes", "no"))
            out.append(f"{pad}{k}: {json.dumps(s, ensure_ascii=False) if needs_quote else s}")
    return "\n".join(out) + "\n"
