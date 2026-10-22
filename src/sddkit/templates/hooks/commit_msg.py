#!/usr/bin/env python3
"""Hook commit-msg: bloqueia atribuição de IA na mensagem de commit.

Uso (instalado por `sddkit commitlint`): `commit_msg.py <arquivo-da-mensagem> [--conventional]`.
  - Sempre: recusa trailer `Co-authored-by` de agente de IA, "Generated with Claude Code",
    `Claude-Session:` e afins. O commitlint não checa isso.
  - `--conventional` (projetos sem commitlint): também exige o cabeçalho
    Conventional Commits `tipo(escopo)!: assunto`.
Linhas de comentário (`#`) são ignoradas, como o git faz. Emergência: `git commit --no-verify`.
"""
from __future__ import annotations

import re
import sys

AI = r"claude|anthropic|copilot|openai|chatgpt|\bgpt-|codex|gemini|cursor|devin|aider|windsurf|codeium|tabnine|amazon q"
ATTRIBUTION = [
    re.compile(rf"^co-authored-by:.*({AI})", re.I),
    re.compile(r"generated (with|by) \[?(claude|chatgpt|copilot|cursor|gemini|codex|ai\b)", re.I),
    re.compile(r"^claude-session:", re.I),
]
HEADER = re.compile(r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([\w./, -]+\))?!?: \S")
EXEMPT = re.compile(r"^(Merge |Revert \"|fixup! |squash! |amend! )")


def problems(text: str, conventional: bool = False) -> list[str]:
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    out = [f"atribuição de IA: {ln.strip()}" for ln in lines if any(p.search(ln.strip()) for p in ATTRIBUTION)]
    header = next((ln for ln in lines if ln.strip()), "")
    if conventional and header and not EXEMPT.match(header) and not HEADER.match(header):
        out.append(f"cabeçalho fora do Conventional Commits: {header!r} (ex.: `feat(api): adiciona filtro`)")
    return out


def main(argv: list[str]) -> int:
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print("uso: commit_msg.py <arquivo-da-mensagem> [--conventional]", file=sys.stderr)
        return 2
    with open(paths[0], encoding="utf-8") as fh:
        bad = problems(fh.read(), "--conventional" in argv)
    if bad:
        print("commit-msg: mensagem recusada\n- " + "\n- ".join(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
