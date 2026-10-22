#!/usr/bin/env python3
"""Guarda determinística contra segredos e dados pessoais em arquivos escritos por agentes.

Modos:
  - Hook PreToolUse (Claude Code): lê o JSON do evento no stdin; se o conteúdo de
    Write/Edit/MultiEdit tiver segredo ou CPF/CNPJ válido, sai com código 2 (bloqueia)
    e explica no stderr.
  - Pre-commit (qualquer ferramenta/husky): `guard_secrets.py --staged` verifica as
    linhas adicionadas no stage do git.

Exceções:
  - arquivos *.example, *.sample, *.template;
  - linha contendo o marcador `sddkit:allow-secret`.
Convenção LGPD para fixtures: use CPF/CNPJ com dígito verificador INVÁLIDO
(ex.: 123.456.789-00) — este guard só bloqueia documentos com DV válido.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

SECRET_PATTERNS = [
    ("chave privada", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("token GitHub", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("chave Anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("chave OpenAI", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}")),
    ("token Slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("chave Google", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("token Stripe", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{20,}")),
    ("URL com senha", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:(?P<pw>[^\s@/]{6,})@[^\s/]+", re.I)),
]
# senha que é só interpolação (`${PASS}`, `$DB_PASS`, `<senha>`, `{{ pass }}`, `%s`) não é segredo;
# `${PASS:-padrao}` é: o padrão fica escrito no arquivo.
TEMPLATED = re.compile(r"\$\{[^}:]+\}|\$[A-Z_][A-Z0-9_]*|<[^<>]+>|\{\{?\s*[\w.]+\s*\}?\}|%\(\w+\)s|%s|\*+")
# formatado (000.000.000-00 / 00.000.000/0000-00) sempre; só dígitos apenas se a linha cita cpf/cnpj
CPF_FMT = re.compile(r"(?<!\d)(\d{3})\.(\d{3})\.(\d{3})-(\d{2})(?!\d)")
CNPJ_FMT = re.compile(r"(?<!\d)(\d{2})\.(\d{3})\.(\d{3})/(\d{4})-(\d{2})(?!\d)")
CPF_RAW = re.compile(r"(?<!\d)(\d{3})(\d{3})(\d{3})(\d{2})(?!\d)")
CNPJ_RAW = re.compile(r"(?<!\d)(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})(?!\d)")
DOC_WORD = re.compile(r"cpf|cnpj|documento|document", re.I)
ALLOW_MARK = "sddkit:allow-secret"
ALLOW_SUFFIX = (".example", ".sample", ".template")


def _cpf_ok(d: str) -> bool:
    if len(set(d)) == 1:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def _cnpj_ok(d: str) -> bool:
    if len(set(d)) == 1:
        return False
    for n in (12, 13):
        w = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][13 - n:]
        s = sum(int(d[i]) * w[i] for i in range(n))
        r = s % 11
        if (0 if r < 2 else 11 - r) != int(d[n]):
            return False
    return True


def scan(text: str) -> list[str]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARK in line:
            continue
        for name, rx in SECRET_PATTERNS:
            m = rx.search(line)
            if m and not ("pw" in rx.groupindex and TEMPLATED.fullmatch(m.group("pw"))):
                hits.append(f"linha {i}: {name}")
        raw = bool(DOC_WORD.search(line))
        for rx in (CPF_FMT, CPF_RAW) if raw else (CPF_FMT,):
            if any(_cpf_ok("".join(m.groups())) for m in rx.finditer(line)):
                hits.append(f"linha {i}: CPF com dígito verificador válido")
                break
        for rx in (CNPJ_FMT, CNPJ_RAW) if raw else (CNPJ_FMT,):
            if any(_cnpj_ok("".join(m.groups())) for m in rx.finditer(line)):
                hits.append(f"linha {i}: CNPJ com dígito verificador válido")
                break
    return hits


def hook() -> int:
    try:
        ev = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    ti = ev.get("tool_input", {}) or {}
    path = str(ti.get("file_path", ""))
    if path.endswith(ALLOW_SUFFIX):
        return 0
    parts = [ti.get("content"), ti.get("new_string")]
    parts += [e.get("new_string") for e in ti.get("edits", []) or [] if isinstance(e, dict)]
    hits = scan("\n".join(p for p in parts if isinstance(p, str)))
    if not hits:
        return 0
    print(f"Bloqueado por .agents/hooks/guard_secrets.py em {path}:\n- " + "\n- ".join(hits[:10]) +
          "\nUse variáveis de ambiente para segredos e dados fictícios com DV inválido em fixtures "
          f"(LGPD). Falso positivo? Acrescente o comentário `{ALLOW_MARK}` na linha.", file=sys.stderr)
    return 2


def staged() -> int:
    diff = subprocess.run(["git", "diff", "--cached", "-U0", "--no-color"], capture_output=True, text=True).stdout
    bad, current = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++") and not current.endswith(ALLOW_SUFFIX):
            bad += [f"{current}: {h.split(': ', 1)[1]}" for h in scan(line[1:])]
    if bad:
        print("guard_secrets: commit bloqueado\n- " + "\n- ".join(bad[:20]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(staged() if "--staged" in sys.argv else hook())
