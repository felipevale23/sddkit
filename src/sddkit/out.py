"""Toda escrita de arquivo gerado passa por aqui: fonte única de verdade com proteção contra edição à mão.

- Arquivo gerado (`managed`): o hash do que o sddkit escreveu fica em `.agents/sddkit.json` (`hashes`).
  Se o arquivo no disco não bate mais com esse hash, alguém o editou: o `sync` não sobrescreve
  (conflito) até a edição ir para a fonte em `.agents/` ou até `--force`.
- Bloco gerado dentro de arquivo do usuário (`AGENTS.md`, `features.md`): mesma regra, pelo hash do bloco.
- Arquivo compartilhado (`CLAUDE.md`, `settings.json`): o sddkit só mescla, então não há hash.
- `check=True`: nada é escrito; `changes` lista o que mudaria (é o `sddkit sync --check` do CI).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class Out:
    def __init__(self, root: Path, cfg: dict, check: bool = False, force: bool = False):
        self.root, self.check, self.force = root, check, force
        self.prev: dict[str, str] = dict(cfg.get("hashes", {}))
        self.prev_generated = set(cfg.get("generated", []))
        self.hashes: dict[str, str] = {}
        self.changes: list[str] = []
        self.conflicts: list[tuple[str, str]] = []

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def edited(self, rel: str, current: str) -> str | None:
        """Motivo para não sobrescrever `current`, ou None se é seguro."""
        if self.force:
            return None
        old = self.prev.get(rel)
        if old is not None:
            return "editado à mão" if sha(current) != old else None
        return None if rel in self.prev_generated else "já existia e não é do sddkit"

    def text(self, path: Path, text: str, managed: bool = True) -> bool:
        rel = self.rel(path)
        cur = path.read_text(encoding="utf-8") if path.is_file() else None
        if cur == text:
            if managed:
                self.hashes[rel] = sha(text)
            return False
        if managed and cur is not None and (why := self.edited(rel, cur)):
            self.conflicts.append((rel, why))
            if rel in self.prev:
                self.hashes[rel] = self.prev[rel]  # continua sinalizado até ser resolvido
            return False
        self.changes.append(rel)
        if not self.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        if managed:
            self.hashes[rel] = sha(text)
        return True

    def block(self, text: str, begin: str, end: str, block: str, key: str) -> str:
        """Insere/atualiza o bloco entre marcadores; bloco editado à mão é mantido (conflito)."""
        new = f"{begin}\n{block.rstrip()}\n{end}"
        pat = re.compile(re.escape(begin) + r"\n?(.*?)\n?" + re.escape(end), re.S)
        m = pat.search(text)
        if not m:
            self.hashes[key] = sha(block.rstrip())
            return (text.rstrip() + "\n\n" if text.strip() else "") + new + "\n"
        cur = m.group(1)
        old = self.prev.get(key)
        if cur != block.rstrip() and old is not None and sha(cur) != old and not self.force:
            self.conflicts.append((key, "bloco editado à mão"))
            self.hashes[key] = old
            return text
        self.hashes[key] = sha(block.rstrip())
        return pat.sub(lambda _: new, text, count=1)

    def remove(self, path: Path) -> bool:
        rel = self.rel(path)
        if path.is_file() and not path.is_symlink():
            if why := self.edited(rel, path.read_text(encoding="utf-8")):
                self.conflicts.append((rel, f"obsoleto mas {why}; apague à mão se não precisa mais"))
                return False
        self.changes.append(rel)
        if not self.check:
            import shutil
            path.unlink() if path.is_symlink() or path.is_file() else shutil.rmtree(path)
        return True

    def report(self) -> list[str]:
        lines = [f"⚠ {rel}: {why}" for rel, why in self.conflicts]
        if self.conflicts:
            lines.append("  → leve a edição para a fonte em .agents/ e rode `sddkit sync`, ou `sddkit sync --force` para descartá-la")
        return lines


OUT: Out | None = None  # instância do sync em curso (usada por adapters, cli e specs)
