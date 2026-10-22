"""sddkit — scaffolding agnóstico de Spec-Driven Development (GitHub Spec Kit) com skills e subagents em .agents/."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

from . import __version__, adapters, memory, specs
from . import out as outmod
from .out import Out, sha
from .detect import detect, matches
from .frontmatter import parse

CONFIG = Path(".agents") / "sddkit.json"
BEGIN, END = "<!-- sddkit:begin -->", "<!-- sddkit:end -->"
IDX_BEGIN, IDX_END = "<!-- sddkit:skills:begin -->", "<!-- sddkit:skills:end -->"
MEM_BEGIN, MEM_END = "<!-- sddkit:memory:begin -->", "<!-- sddkit:memory:end -->"


# ───────────────────────── util ─────────────────────────
def say(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except BrokenPipeError:  # saída cortada (ex.: | head): segue o trabalho em silêncio
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())


def tpl() -> Path:
    return Path(str(resources.files("sddkit") / "templates"))


def catalog() -> list[dict]:
    return json.loads((resources.files("sddkit") / "catalog.json").read_text(encoding="utf-8"))["entries"]


# Publicadores conhecidos (empresas com processo de segurança próprio); o resto é comunidade.
OFFICIAL_PUBLISHERS = {"anthropics", "vercel-labs", "cloudflare", "trailofbits"}


def tier(source: str) -> str:
    return "oficial" if source.split("/", 1)[0].lower() in OFFICIAL_PUBLISHERS else "comunidade"


def role_catalog() -> list[dict]:
    return json.loads((resources.files("sddkit") / "catalog.json").read_text(encoding="utf-8")).get("roles", [])


def installed_roles(root: Path) -> dict[str, dict]:
    out = {}
    for f in sorted((root / ".agents" / "agents").glob("*.md")):
        meta, _ = parse(f.read_text(encoding="utf-8"))
        out[meta.get("name") or f.stem] = meta
    return out


def role_suggestions(root: Path, info: dict) -> list[dict]:
    have = installed_roles(root)
    return [{**r, "installed": r["id"] in have} for r in role_catalog() if matches(r, info)]


def print_roles(sugs: list[dict]) -> None:
    for i, r in enumerate(sugs, 1):
        mark = "✓" if r["installed"] else ("★" if r["recommended"] else " ")
        say(f"  {i:2}. {mark} {r['id']:20} {r['why']}")
    say("  (✓ instalado · ★ recomendado)")


def install_roles(root: Path, ids: list[str], cfg: dict, force: bool = False, quiet: bool = False) -> list[str]:
    """Copia papéis do catálogo para .agents/agents (editados são mantidos). Retorna ids de skills sugeridas."""
    cat = {r["id"]: r for r in role_catalog()}
    skills: list[str] = []
    msg = {"criado": "✓ papel {i} → .agents/agents/{i}.md", "atualizado": "✓ papel {i} atualizado",
           "igual": "· {i}: em dia", "editado": "· {i}: editado por você, mantido (--force substitui)"}
    for i in ids:
        if i not in cat:
            raise SystemExit(f"✗ papel '{i}' não existe. Veja `sddkit role list` ou crie com `sddkit role new {i}`.")
        r = install_template(tpl() / "roles" / f"{i}.md", root / ".agents" / "agents" / f"{i}.md", root, cfg, force)
        if not quiet or r in ("atualizado", "editado"):
            say("  " + msg[r].format(i=i))
        skills += cat[i].get("skills", [])
    return list(dict.fromkeys(skills))


def load_cfg(root: Path) -> dict:
    p = root / CONFIG
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"version": 1, "adapters": [], "mode": "copy" if os.name == "nt" else "link",
            "installed": [], "generated": []}


def save_cfg(root: Path, cfg: dict) -> None:
    p = root / CONFIG
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def interactive(args) -> bool:
    return sys.stdin.isatty() and not getattr(args, "yes", False)


def ask(prompt: str, default: str = "") -> str:
    try:
        ans = input(f"{prompt} " + (f"[{default}] " if default else ""))
    except EOFError:
        return default
    return ans.strip() or default


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> int:
    say("  $ " + " ".join(cmd))
    return subprocess.call(cmd, cwd=cwd, env={**os.environ, **(env or {})})


def installed_skills(root: Path) -> dict[str, str]:
    out = {}
    for f in sorted((root / ".agents" / "skills").glob("*/SKILL.md")):
        meta, _ = parse(f.read_text(encoding="utf-8"))
        out[meta.get("name") or f.parent.name] = str(meta.get("description", "")).strip()
    return out


def specify_cmd() -> list[str] | None:
    if shutil.which("specify"):
        return ["specify"]
    if shutil.which("uvx"):
        return ["uvx", "--from", "specify-cli", "specify"]
    return None


# ───────────────────────── AGENTS.md ─────────────────────────
def write_agents_md(root: Path, out: Out) -> None:
    p = root / "AGENTS.md"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    note = "<!-- Bloco gerado pelo sddkit: edite .agents/ e rode `sddkit sync`; edições aqui são recusadas. -->\n"
    text = out.block(text, BEGIN, END, note + (tpl() / "AGENTS.block.md").read_text(encoding="utf-8"), "AGENTS.md#sddkit")
    skills = installed_skills(root)
    lines = [note.rstrip(), "## Skills instaladas (`.agents/skills/`)", ""]
    spk = [n for n in skills if n.startswith("speckit-")]
    if spk:
        lines.append("- Spec Kit: " + ", ".join(f"`{n}`" for n in spk))
    for name, desc in skills.items():
        if name.startswith("speckit-"):
            continue
        d = re.sub(r"\s+", " ", desc)
        lines.append(f"- `{name}` — {d[:160] + '…' if len(d) > 160 else d}")
    if not skills:
        lines.append("- (nenhuma)")
    lines += ["", "## Papéis de subagent (`.agents/agents/`)", "",
              "| Papel | Tipo | Quando entra |", "|---|---|---|"]
    for name, m in installed_roles(root).items():
        kind = m.get("kind", "core")
        if kind == "implementer":
            when = "tarefas roteadas por arquivo/palavra-chave ou `[@" + name + "]`"
        elif kind == "reviewer":
            when = "fim de cada história" if m.get("review_at", "story") == "story" else "convergência da feature"
        else:
            when = "fluxo SDD (sdd-feature / sdd-build)"
        lines.append(f"| `{name}` | {kind} | {when} |")
    text = out.block(text, IDX_BEGIN, IDX_END, "\n".join(lines), "AGENTS.md#skills")
    mem = memory.render_agents_block(root)
    has_mem = MEM_BEGIN in text
    if mem and has_mem:
        text = out.block(text, MEM_BEGIN, MEM_END, mem, "AGENTS.md#memory")
    elif mem:
        block = f"{MEM_BEGIN}\n{mem.rstrip()}\n{MEM_END}\n"
        text = text.replace(END + "\n", END + "\n\n" + block, 1) if END + "\n" in text else text + "\n" + block
        out.hashes["AGENTS.md#memory"] = sha(mem.rstrip())
    elif has_mem:
        text = re.sub(re.escape(MEM_BEGIN) + r".*?" + re.escape(MEM_END) + r"\n?", "", text, flags=re.S)
    text = re.sub(r"\n{3,}", "\n\n", text)
    out.text(p, text, managed=False)


# ───────────────────────── comandos ─────────────────────────
def install_template(src: Path, dst: Path, root: Path, cfg: dict, force: bool) -> str:
    """Copia um template do sddkit sem perder edição local.

    O hash do que foi instalado fica em `templates` no sddkit.json. Cópia intocada é atualizada
    quando o template muda; cópia editada (ou de origem desconhecida) é mantida, salvo `force`.
    """
    rel = dst.relative_to(root).as_posix()
    rec = cfg.setdefault("templates", {})
    new = src.read_bytes()
    h = lambda b: hashlib.sha256(b).hexdigest()[:16]  # noqa: E731
    if dst.exists():
        cur = dst.read_bytes()
        if cur == new:
            rec[rel] = h(new)
            return "igual"
        if not force and rec.get(rel) != h(cur):
            return "editado"
    dst.parent.mkdir(parents=True, exist_ok=True)
    existed = dst.exists()
    shutil.copy2(src, dst)
    if dst.suffix == ".py":
        dst.chmod(0o755)
    rec[rel] = h(new)
    return "atualizado" if existed else "criado"


def copy_templates(root: Path, force: bool, cfg: dict) -> dict[str, list[str]]:
    res: dict[str, list[str]] = {}
    src = tpl()
    for sub in ("agents", "skills", "hooks"):
        for f in sorted(p for p in (src / sub).rglob("*") if p.is_file()):
            dst = root / ".agents" / f.relative_to(src)
            res.setdefault(install_template(f, dst, root, cfg, force), []).append(dst.relative_to(root).as_posix())
    return res


def template_summary(res: dict[str, list[str]]) -> str:
    parts = [f"{len(res[k])} {k}" for k in ("criado", "atualizado") if res.get(k)]
    line = ", ".join(parts) or "nada mudou"
    if res.get("editado"):
        line += (f"; {len(res['editado'])} editado(s) por você, mantido(s): " + ", ".join(res["editado"][:5])
                 + (" …" if len(res["editado"]) > 5 else "") + " — `sddkit init --force-templates` substitui")
    return line


def scaffold_specs(root: Path) -> list[str]:
    """Cria .agents/specs/ (docs centrais + features/changes/playbooks). Nunca sobrescreve: os docs são do projeto."""
    done = []
    src = tpl() / "specs"
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        dst = root / specs.SPECS / f.relative_to(src)
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            done.append(str(dst.relative_to(root)))
    return done


def detect_adapters(root: Path) -> list[str]:
    found = []
    if (root / ".claude").exists() or (root / "CLAUDE.md").exists():
        found.append("claude")
    if (root / ".opencode").exists() or (root / "opencode.json").exists():
        found.append("opencode")
    if (root / ".gemini").exists() or (root / "GEMINI.md").exists():
        found.append("gemini")
    return found


def parse_list(v: str | None) -> list[str] | None:
    if v is None:
        return None
    return [x.strip() for x in v.split(",") if x.strip()]


def cmd_init(args) -> int:
    root = Path(args.dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    cfg = load_cfg(root)
    say(f"sddkit {__version__} → {root}\n")

    # 1. Spec Kit (motor) com skills em .agents/skills
    if args.no_speckit:
        say("• Spec Kit: pulado (--no-speckit)")
    elif (root / ".specify").exists():
        say("• Spec Kit: .specify/ já existe — mantido (atualize com `specify integration upgrade`)")
    else:
        sc = specify_cmd()
        if not sc:
            say("✗ Spec Kit não encontrado. Instale: `uv tool install specify-cli` (ou instale o uv) e rode de novo.")
            return 1
        say("• Spec Kit: instalando (integração generic → .agents/skills)")
        cmd = sc + ["init", "--here", "--force", "--non-interactive", "--ignore-agent-tools",
                    "--integration", "generic",
                    "--integration-options=--commands-dir .agents/skills --skills"]
        if not args.no_git:
            cmd += ["--extension", "git"]
        if run(cmd, root, {"NO_COLOR": "1"}) != 0:
            say("✗ specify init falhou.")
            return 1

    # 2. Camada sdd (papéis + skills de orquestração)
    res = copy_templates(root, args.force_templates, cfg)
    say(f"• Camada sdd: {template_summary(res)}")
    cat_ids = {r["id"] for r in role_catalog()}
    stale = [n for n in installed_roles(root) if n in cat_ids]
    if stale:  # papéis do catálogo já instalados: atualiza os intocados
        install_roles(root, stale, cfg, force=args.force_templates, quiet=True)
    created = scaffold_specs(root)
    say(f"• Specs: {specs.SPECS}/ " + (f"criado ({len(created)} arquivo(s)) — preencha architecture.md, stack.md…" if created else "já existe — mantido"))

    # 3. Adaptadores
    chosen = parse_list(args.agents)
    if chosen is None:
        default = cfg["adapters"] or detect_adapters(root) or ["claude"]
        if interactive(args):
            say("\nAdaptadores disponíveis:")
            for k, v in adapters.ADAPTERS.items():
                say(f"  {k:9} {v}")
            say(f"  (nativos, sem adaptador: {adapters.NATIVE})")
            chosen = parse_list(ask("Quais adaptadores? (vírgula, 'none' p/ nenhum)", ",".join(default)))
        else:
            chosen = default
    if chosen == ["all"]:
        chosen = list(adapters.ADAPTERS)
    chosen = [] if chosen == ["none"] else chosen
    bad = [a for a in chosen if a not in adapters.ADAPTERS]
    if bad:
        say(f"✗ adaptador desconhecido: {', '.join(bad)}")
        return 2
    cfg["adapters"] = chosen
    if args.copy:
        cfg["mode"] = "copy"
    save_cfg(root, cfg)

    # 4. Skills sugeridas
    info = detect(root)
    say(f"\n• Projeto: stacks={info['stacks'] or '—'} · código existente={'sim' if info['has_code'] else 'não'}")
    role_ids = select_roles(args, root, info)
    role_skill_ids: list[str] = []
    if role_ids:
        say(f"\n• Papéis: {', '.join(role_ids)}")
        role_skill_ids = install_roles(root, role_ids, cfg)
    ids = select_skills(args, root, info, cfg, extra=role_skill_ids)
    if ids:
        install(root, ids, cfg)

    # 5. Sync (AGENTS.md + adaptadores)
    do_sync(root, cfg)
    say("\n✓ Pronto. Próximos passos no seu agente:")
    say("  /speckit-constitution <princípios do projeto>")
    say("  /sdd-feature <descrição da feature> --stack <...>   (use --grill para afiar a ideia antes)")
    say("  /sdd-build --mvp")
    say("  /sdd-change <o que mudar>   (bug, ajuste ou evolução de algo que já existe)")
    say("  (papéis extras: sddkit role list · sddkit role add <papel> · sddkit role new <nome>)")
    return 0


def suggestions(root: Path, info: dict) -> list[dict]:
    have = set(installed_skills(root))
    out = []
    for e in catalog():
        if matches(e, info):
            out.append({**e, "tier": tier(e["source"]), "installed": all(s in have for s in e["skills"])})
    groups = json.loads((resources.files("sddkit") / "catalog.json").read_text(encoding="utf-8"))["groups"]
    return sorted(out, key=lambda e: (groups.index(e["group"]), e["tier"] != "oficial"))


def print_suggestions(sugs: list[dict]) -> None:
    for i, e in enumerate(sugs, 1):
        if i == 1 or e["group"] != sugs[i - 2]["group"]:
            say(f"  [{e['group']}]")
        mark = "✓" if e["installed"] else ("★" if e["recommended"] else " ")
        say(f"  {i:2}. {mark} {e['id']:30} [{e['phase']}] · {e['tier']} ({e['source']})")
        say(f"        {e['why']}")
    say("  (✓ instalada · ★ recomendada · oficial = publicador conhecido · comunidade = revise antes de usar)")


def select_roles(args, root: Path, info: dict) -> list[str]:
    sugs = role_suggestions(root, info)
    pending = [r for r in sugs if not r["installed"]]
    rec = [r["id"] for r in pending if r["recommended"]]
    mode = args.roles
    if mode is None and interactive(args):
        say("\nSubagents especialistas sugeridos:")
        print_roles(sugs)
        mode = ask("Adicionar quais? (Enter = recomendados, 'all', 'none', ou números/ids)", "recommended")
    mode = mode or "recommended"
    if mode == "none":
        return []
    if mode == "recommended":
        return rec
    if mode == "all":
        return [r["id"] for r in pending]
    out = []
    for tok in parse_list(mode) or []:
        out.append(sugs[int(tok) - 1]["id"] if tok.isdigit() and 1 <= int(tok) <= len(sugs) else tok)
    return out


def select_skills(args, root: Path, info: dict, cfg: dict, extra: list[str] | None = None) -> list[str]:
    sugs = suggestions(root, info)
    # skills sugeridas pelos papéis escolhidos viram recomendadas (se casam com a stack)
    for e in sugs:
        if e["id"] in (extra or []):
            e["recommended"] = True
    pending = [e for e in sugs if not e["installed"]]
    rec = [e["id"] for e in pending if e["recommended"]]
    mode = args.skills
    if mode is None and interactive(args):
        say("\nSkills sugeridas para este projeto:")
        print_suggestions(sugs)
        ans = ask("Instalar quais? (Enter = recomendadas, 'all', 'none', ou números/ids separados por vírgula)", "recommended")
        mode = ans
    mode = mode or "recommended"
    if mode == "none":
        return []
    if mode == "recommended":
        return rec
    if mode == "all":
        return [e["id"] for e in pending]
    ids = []
    for tok in parse_list(mode) or []:
        if tok.isdigit() and 1 <= int(tok) <= len(sugs):
            ids.append(sugs[int(tok) - 1]["id"])
        else:
            ids.append(tok)
    return ids


def resolve(ids: list[str]) -> dict[str, list[str]]:
    """Agrupa skills por fonte. Aceita ids do catálogo ou 'owner/repo@skill'."""
    cat = {e["id"]: e for e in catalog()}
    by_src: dict[str, list[str]] = {}
    for i in ids:
        if i in cat:
            by_src.setdefault(cat[i]["source"], []).extend(cat[i]["skills"])
        elif "@" in i:
            src, sk = i.rsplit("@", 1)
            by_src.setdefault(src, []).append(sk)
        else:
            raise SystemExit(f"✗ '{i}' não está no catálogo. Use um id de `sddkit suggest` ou owner/repo@skill.")
    return {s: list(dict.fromkeys(v)) for s, v in by_src.items()}


def install(root: Path, ids: list[str], cfg: dict) -> bool:
    if not shutil.which("npx"):
        say("✗ npx não encontrado (Node.js ≥ 22.20). Instale as skills depois com `sddkit add ...`.")
        return False
    ok = True
    say(f"\n• Instalando skills: {', '.join(ids)}")
    for src, skills in resolve(ids).items():
        cmd = ["npx", "-y", "skills", "add", src]
        for s in skills:
            cmd += ["--skill", s]
        cmd += ["-a", "universal", "-y"]
        say(f"  $ {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        if r.returncode != 0 or "No matching skills" in r.stdout + r.stderr:
            tail = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout + r.stderr).strip().splitlines()[-15:]
            say(f"  ✗ falhou: {src}\n    " + "\n    ".join(tail))
            ok = False
        else:
            say(f"  ✓ {src}: {', '.join(skills)}" + ("" if tier(src) == "oficial" else "  ⚠ comunidade — revise antes de usar"))
    have = set(installed_skills(root))
    cat = {e["id"]: e for e in catalog()}
    for i in ids:
        if i in cat and all(s in have for s in cat[i]["skills"]) and i not in cfg["installed"]:
            cfg["installed"].append(i)
    save_cfg(root, cfg)
    return ok


def do_sync(root: Path, cfg: dict, check: bool = False, force: bool = False) -> Out:
    """Regenera AGENTS.md, índice e adaptadores a partir de .agents/. `check`: só compara, não escreve."""
    out = outmod.OUT = Out(root, cfg, check=check, force=force)
    write_agents_md(root, out)
    specs.write_index(root, out)
    gen, log = adapters.run(root, cfg["adapters"], cfg["mode"], cfg.get("generated", []), out)
    if not check:
        cfg["generated"], cfg["hashes"] = gen, dict(sorted(out.hashes.items()))
        save_cfg(root, cfg)
        say("\n• AGENTS.md, índice de specs e adaptadores sincronizados" + (f" ({len(out.changes)} arquivo(s) alterado(s))" if out.changes else " (nada mudou)"))
        for line in log:
            say(f"  {line}")
        for line in out.report():
            say(line)
    outmod.OUT = None
    return out


def refresh_index(root: Path) -> None:
    """Atualiza só o features.md (fora do sync), mantendo o hash do bloco no sddkit.json."""
    cfg = load_cfg(root)
    out = Out(root, cfg)
    specs.write_index(root, out)
    cfg.setdefault("hashes", {}).update(out.hashes)
    save_cfg(root, cfg)
    for line in out.report():
        say(line)


def cmd_suggest(args) -> int:
    root = Path(args.dir).resolve()
    info = detect(root)
    sugs = suggestions(root, info)
    roles = role_suggestions(root, info)
    if args.json:
        say(json.dumps({"project": info, "skills": sugs, "roles": roles}, ensure_ascii=False, indent=2))
        return 0
    say(f"Projeto: stacks={info['stacks'] or '—'} · evidências={info['evidence'] or '—'}\n")
    say("Subagents especialistas:")
    print_roles(roles)
    say("\nSkills:")
    print_suggestions(sugs)
    say("\nAdicione com: sddkit role add <papel> …  ·  sddkit add <skill> …  (ou owner/repo@skill)")
    return 0


def cmd_add(args) -> int:
    root = Path(args.dir).resolve()
    cfg = load_cfg(root)
    ok = install(root, args.ids, cfg)
    do_sync(root, cfg)
    return 0 if ok else 1


def cmd_sync(args) -> int:
    root = Path(args.dir).resolve()
    cfg = load_cfg(root)
    if args.agents is not None:
        cfg["adapters"] = [] if args.agents == "none" else parse_list(args.agents)
    if args.copy:
        cfg["mode"] = "copy"
    out = do_sync(root, cfg, check=args.check, force=args.force)
    if args.check:
        for rel in out.changes:
            say(f"✗ desatualizado: {rel}")
        for line in out.report():
            say(line)
        say("✓ arquivos gerados em dia com .agents/" if not (out.changes or out.conflicts)
            else "\n→ rode `sddkit sync` e faça commit do resultado")
        return 1 if out.changes or out.conflicts else 0
    return 1 if out.conflicts else 0


ROLE_SKELETON = """---
name: {name}
description: TODO — o que este especialista faz e quando deve ser usado.
kind: {kind}
{extra}capabilities: [read, edit, write, shell]
tier: fast
skills: []
route_globs: []
route_keywords: []
priority: 20
max_turns: 40
---

{body}
"""


def cmd_role(args) -> int:
    root = Path(args.dir).resolve()
    cfg = load_cfg(root)
    if args.action == "list":
        info = detect(root)
        have = installed_roles(root)
        say("Catálogo (✓ instalado · ★ recomendado para esta stack):")
        stack_ok = {r["id"] for r in role_catalog() if matches(r, info)}
        for r in role_catalog():
            mark = "✓" if r["id"] in have else ("★" if r["recommended"] and r["id"] in stack_ok else " ")
            say(f"  {mark} {r['id']:20} {r['why']}")
        custom = [n for n, m in have.items() if m.get("kind") in ("implementer", "reviewer")
                  and n not in {r["id"] for r in role_catalog()}]
        if custom:
            say("Personalizados: " + ", ".join(custom))
        return 0
    if args.action == "update":
        cat_ids = {r["id"] for r in role_catalog()}
        names = args.names or [n for n in installed_roles(root) if n in cat_ids]
        install_roles(root, names, cfg, force=True)
        do_sync(root, cfg)
        return 0
    if not args.names:
        say("✗ informe ao menos um papel")
        return 2
    if args.action == "add":
        skills = install_roles(root, args.names, cfg, args.force)
        if skills and not args.no_skills:
            info = detect(root)
            have = set(installed_skills(root))
            cat = {e["id"]: e for e in catalog()}
            todo = [i for i in skills if i in cat and matches(cat[i], info)
                    and not all(x in have for x in cat[i]["skills"])]
            if todo:
                install(root, todo, cfg)
    elif args.action == "remove":
        core = {"sdd-researcher", "sdd-implementer", "sdd-analyst", "sdd-converger"}
        for n in args.names:
            f = root / ".agents" / "agents" / f"{n}.md"
            if n in core:
                say(f"  ✗ {n} é papel do núcleo SDD; não removido")
            elif f.exists():
                f.unlink()
                say(f"  ✓ removido {n}")
            else:
                say(f"  · {n} não está instalado")
    elif args.action == "new":
        for n in args.names:
            f = root / ".agents" / "agents" / f"{n}.md"
            if f.exists():
                say(f"  · {n} já existe")
                continue
            if args.kind == "reviewer":
                extra, body = "review_at: story\n", ("Siga o formato dos revisores (veja .agents/agents/ui-reviewer.md se instalado): "
                                                     "leia, não edite código, grave relatório em FEATURE_DIR/reviews/ e devolva verdict + tarefas.")
            else:
                extra, body = "", "Siga o contrato de `.agents/agents/sdd-implementer.md` e, além dele:\n\n- TODO: regras do especialista"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(ROLE_SKELETON.format(name=n, kind=args.kind, extra=extra, body=body), encoding="utf-8")
            say(f"  ✓ criado .agents/agents/{n}.md — preencha description, route_globs e route_keywords")
    do_sync(root, cfg)
    return 0


def cmd_memory(args) -> int:
    root = Path(args.dir).resolve()
    if args.action == "add":
        if not args.text:
            say("✗ informe o texto: sddkit memory add \"<fato>\" [-t tópico] [--paths glob,glob]")
            return 2
        say(memory.add(root, " ".join(args.text), args.topic, parse_list(args.paths), args.description))
    elif args.action in ("rm", "remove"):
        if not args.text:
            say("✗ uso: sddkit memory rm <tópico> [n]")
            return 2
        idx = int(args.text[1]) if len(args.text) > 1 else None
        say(memory.remove(root, args.text[0], idx))
    else:
        mems = memory.load(root)
        if args.topic and args.topic != "geral":
            mems = [m for m in mems if m["topic"] == memory.slug(args.topic)]
        if not mems:
            say("(sem memórias — adicione com: sddkit memory add \"<fato>\" -t <tópico>)")
        for m in mems:
            scope = ", ".join(m["paths"]) if m["paths"] else "projeto todo"
            say(f"■ {m['topic']}  [{scope}]" + (f" — {m['description']}" if m["description"] else ""))
            for i, x in enumerate(m["facts"], 1):
                say(f"  {i:2}. {x}")
        return 0
    do_sync(root, load_cfg(root))
    return 0


def cmd_change(args) -> int:
    root = Path(args.dir).resolve()
    f = specs.new_change(root, " ".join(args.title), args.feature, args.priority)
    meta, _ = parse(f.read_text(encoding="utf-8"))
    say(f"✓ {meta['id']} → {f.relative_to(root)} (status: Proposed)")
    refresh_index(root)
    return 0


def cmd_index(args) -> int:
    root = Path(args.dir).resolve()
    if not (root / specs.SPECS).is_dir():
        say(f"✗ {specs.SPECS}/ não existe — rode `sddkit init`.")
        return 1
    refresh_index(root)
    say(f"✓ {specs.SPECS}/features.md")
    return 0


def cmd_playbook(args) -> int:
    root = Path(args.dir).resolve()
    f = specs.new_playbook(root, " ".join(args.name))
    say(f"✓ {f.relative_to(root)}")
    refresh_index(root)
    return 0


COMMITLINT_CONFIGS = ("commitlint.config.js", "commitlint.config.mjs", "commitlint.config.cjs", "commitlint.config.ts",
                      ".commitlintrc", ".commitlintrc.json", ".commitlintrc.yml", ".commitlintrc.yaml", ".commitlintrc.js")


def _hooks_dir(root: Path) -> tuple[Path, bool]:
    """(pasta do commit-msg, versionada?). Husky > core.hooksPath > .githooks (só se .git/hooks não tiver hooks próprios)."""
    if (root / ".husky").is_dir():
        return root / ".husky", True
    cur = subprocess.run(["git", "config", "core.hooksPath"], cwd=root, capture_output=True, text=True).stdout.strip()
    if cur:
        return root / cur, not cur.startswith(".git/")
    own = [h for h in (root / ".git" / "hooks").glob("*") if h.is_file() and not h.name.endswith(".sample")]
    if own:  # trocar o hooksPath desligaria esses hooks
        return root / ".git" / "hooks", False
    run(["git", "config", "core.hooksPath", ".githooks"], root)
    return root / ".githooks", True


def cmd_commitlint(args) -> int:
    root = Path(args.dir).resolve()
    if not (root / ".git").exists():
        say("✗ não é um repositório git.")
        return 1
    script = root / ".agents" / "hooks" / "commit_msg.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tpl() / "hooks" / "commit_msg.py", script)
    script.chmod(0o755)
    pkg = root / "package.json"
    node = pkg.is_file()
    if node:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        need = [d for d in ("@commitlint/cli", "@commitlint/config-conventional") if d not in deps]
        if need and not args.no_install:
            if (root / "pnpm-lock.yaml").exists():
                cmd = ["pnpm", "add", "-D"] + (["-w"] if (root / "pnpm-workspace.yaml").exists() else [])
            elif (root / "yarn.lock").exists():
                cmd = ["yarn", "add", "-D"]
            elif (root / "bun.lockb").exists() or (root / "bun.lock").exists():
                cmd = ["bun", "add", "-d"]
            else:
                cmd = ["npm", "install", "-D"]
            say(f"• {' '.join(cmd + need)}")
            if run(cmd + need, root) != 0:
                say("✗ falhou ao instalar o commitlint.")
                return 1
        elif need:
            say(f"• pulado (--no-install): instale {' '.join(need)} como devDependencies")
        cfg = next((c for c in COMMITLINT_CONFIGS if (root / c).exists()), None) or ("commitlint" if "commitlint" in data else None)
        if cfg:
            say(f"• commitlint: config existente mantida ({cfg})")
        else:
            (root / "commitlint.config.mjs").write_text("export default { extends: ['@commitlint/config-conventional'] };\n", encoding="utf-8")
            say("• commitlint.config.mjs criado (@commitlint/config-conventional)")

    hdir, versioned = _hooks_dir(root)
    hook = hdir / "commit-msg"
    text = hook.read_text(encoding="utf-8") if hook.exists() else ("" if hdir.name == ".husky" else "#!/bin/sh\n")
    add = []
    if node and "commitlint" not in text:
        add.append('npx --no -- commitlint --edit "$1"')
    if "commit_msg.py" not in text:
        add.append('python3 .agents/hooks/commit_msg.py "$1"' + ("" if node else " --conventional"))
    if add:
        # no topo e com `|| exit 1`: sem `sh -e`, o status do hook é o do último comando — a ordem não pode mascarar falhas
        lines = text.splitlines()
        head = [lines.pop(0)] if lines and lines[0].startswith("#!") else []
        block = ["# sddkit: Conventional Commits + sem atribuição de IA"] + [c + " || exit 1" for c in add]
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("\n".join(head + block + lines) + "\n", encoding="utf-8")
        hook.chmod(0o755)
    say(f"• {hook.relative_to(root)}: " + ("atualizado" if add else "já configurado")
        + ("" if versioned else " (local, não versionado: cada clone roda `sddkit commitlint`)"))
    if hdir.name == ".githooks":
        say("  core.hooksPath=.githooks — em outro clone: `git config core.hooksPath .githooks`")
    say("✓ commits passam por " + ("commitlint + " if node else "Conventional Commits + ") + "bloqueio de atribuição de IA")
    return 0


def cmd_doctor(args) -> int:
    root = Path(args.dir).resolve()
    cfg = load_cfg(root)
    problems = 0

    def check(ok: bool, msg: str, fix: str = "") -> None:
        nonlocal problems
        say(f"  {'✓' if ok else '✗'} {msg}" + ("" if ok or not fix else f"  → {fix}"))
        problems += not ok

    say(f"sddkit doctor — {root}")
    check(specify_cmd() is not None, "Spec Kit CLI (specify ou uvx)", "uv tool install specify-cli")
    node = shutil.which("node")
    ver = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip() if node else ""
    nv = tuple(int(x) for x in re.findall(r"\d+", ver)[:2]) if ver else (0, 0)
    check(nv >= (22, 20), f"Node.js ≥ 22.20 para `npx skills` ({ver or 'ausente'})", "instale Node 22.20+")
    check((root / ".git").exists(), "repositório git", "git init")
    check((root / ".specify").is_dir(), ".specify/ (motor do Spec Kit)", "sddkit init")
    agents_md = (root / "AGENTS.md").read_text(encoding="utf-8") if (root / "AGENTS.md").exists() else ""
    check(BEGIN in agents_md, "AGENTS.md com bloco sddkit", "sddkit sync")
    n_lines = agents_md.count("\n")
    check(n_lines <= 200, f"AGENTS.md com {n_lines} linhas (recomendado ≤ 200 para aderência)",
          "mova memórias para tópicos com --paths ou procedimentos para skills")
    if "claude" in cfg["adapters"]:
        for name in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"):
            f = root / name
            if f.exists() and name != "CLAUDE.local.md":
                check("@AGENTS.md" in f.read_text(encoding="utf-8") or name != "CLAUDE.md",
                      f"{name} importa @AGENTS.md", "sddkit sync")
        local = root / "CLAUDE.local.md"
        if local.exists() and not (root / "CLAUDE.md").exists():
            check("@AGENTS.md" in local.read_text(encoding="utf-8"),
                  "CLAUDE.local.md existe: sem @AGENTS.md o Claude deixa de ler o AGENTS.md", "adicione @AGENTS.md nele")
    skills = installed_skills(root)
    core = {"speckit-specify", "speckit-plan", "speckit-tasks", "sdd-feature", "sdd-build"}
    check(core <= set(skills), f".agents/skills: {len(skills)} skills (núcleo speckit + sdd)", "sddkit init")
    check(len(adapters.load_roles(root)) >= 4, f".agents/agents: {len(adapters.load_roles(root))} papéis", "sddkit init")
    const = root / ".specify" / "memory" / "constitution.md"
    check(const.exists() and "[PROJECT_NAME]" not in const.read_text(encoding="utf-8"),
          "constituição preenchida", "/speckit-constitution no seu agente")
    for a in cfg["adapters"]:
        if a == "claude":
            cs = root / ".claude" / "skills"
            check(cs.exists() and (cs / "sdd-feature" / "SKILL.md").exists(), "claude: .claude/skills resolve para .agents/skills", "sddkit sync")
            check(all((root / ".claude" / "agents" / f"{r['meta']['name']}.md").exists() for r in adapters.load_roles(root)),
                  "claude: subagents gerados", "sddkit sync")
        if a == "opencode":
            check((root / ".opencode" / "agents").is_dir(), "opencode: subagents gerados", "sddkit sync")
        if a == "gemini":
            check((root / ".gemini" / "settings.json").exists(), "gemini: settings.json", "sddkit sync")
    info = detect(root)
    pend = [e["id"] for e in suggestions(root, info) if e["recommended"] and not e["installed"]]
    rpend = [r["id"] for r in role_suggestions(root, info) if r["recommended"] and not r["installed"]]
    check(not rpend, "papéis recomendados instalados" + (f" (faltam: {', '.join(rpend)})" if rpend else ""), "sddkit role add " + " ".join(rpend))
    check(not pend, "skills recomendadas instaladas" + (f" (faltam: {', '.join(pend)})" if pend else ""), "sddkit add " + " ".join(pend))
    say("\nFonte única (.agents/ → arquivos gerados):")
    sync = do_sync(root, cfg, check=True)
    check(not sync.changes, "arquivos gerados em dia com .agents/", "sddkit sync")
    for rel in sync.changes[:8]:
        say(f"      · {rel}")
    check(not sync.conflicts, "nenhum arquivo/bloco gerado editado à mão",
          "leve a edição para .agents/ e rode `sddkit sync` (ou `sddkit sync --force` para descartá-la)")
    for rel, why in sync.conflicts[:8]:
        say(f"      · {rel}: {why}")
    rec, edited, old_tpl = cfg.get("templates", {}), [], []
    srcs = [(f, root / ".agents" / f.relative_to(tpl())) for sub in ("agents", "skills", "hooks")
            for f in (tpl() / sub).rglob("*") if f.is_file()]
    srcs += [(tpl() / "roles" / f"{n}.md", root / ".agents" / "agents" / f"{n}.md") for n in installed_roles(root)
             if (tpl() / "roles" / f"{n}.md").exists()]
    for src, dst in srcs:
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            r = dst.relative_to(root).as_posix()
            (old_tpl if rec.get(r) == hashlib.sha256(dst.read_bytes()).hexdigest()[:16] else edited).append(r)
    check(not old_tpl, "templates do sddkit atualizados" + (f" ({len(old_tpl)} com versão nova)" if old_tpl else ""), "sddkit init")
    if edited:
        say(f"  · {len(edited)} template(s) editado(s) localmente (versão nova não aplicada): {', '.join(edited[:5])}"
            + (" …" if len(edited) > 5 else "") + " — compare e use `sddkit init --force-templates` se quiser a versão nova")

    say("\nSpecs (drift):")
    for ok, msg, fix, details in specs.drift_checks(root, info):
        check(ok, msg, fix)
        for d in details[:8]:
            say(f"      · {d}")
        if len(details) > 8:
            say(f"      · … +{len(details) - 8}")
    say(f"\n{problems} pendência(s).")
    return 0 if problems == 0 else 1


# ───────────────────────── main ─────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sddkit", description=__doc__)
    ap.add_argument("--version", action="version", version=f"sddkit {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="cria/atualiza o scaffolding SDD no projeto")
    p.add_argument("dir", nargs="?", default=".")
    p.add_argument("--agents", help="adaptadores: claude,opencode,gemini | all | none (padrão: detectados ou claude)")
    p.add_argument("--roles", help="subagents especialistas: recommended (padrão) | all | none | ids/números")
    p.add_argument("--skills", help="recommended (padrão) | all | none | ids/números separados por vírgula")
    p.add_argument("--copy", action="store_true", help="copiar em vez de symlink (padrão no Windows)")
    p.add_argument("--no-speckit", action="store_true", help="não rodar specify init")
    p.add_argument("--no-git", action="store_true", help="sem a extensão git do Spec Kit")
    p.add_argument("--force-templates", action="store_true", help="sobrescrever papéis e skills sdd-* existentes")
    p.add_argument("-y", "--yes", action="store_true", help="sem perguntas (usa padrões)")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("suggest", help="sugere skills com base na stack detectada")
    p.add_argument("dir", nargs="?", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_suggest)

    p = sub.add_parser("add", help="instala skills do catálogo (ex.: grill-me) ou owner/repo@skill em .agents/skills")
    p.add_argument("ids", nargs="+")
    p.add_argument("--dir", default=".")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("role", help="subagents especialistas pré-definidos (ui, api, data, qa, ...)")
    p.add_argument("action", choices=["list", "add", "remove", "new", "update"])
    p.add_argument("names", nargs="*")
    p.add_argument("--dir", default=".")
    p.add_argument("--force", action="store_true", help="add: sobrescreve papel existente")
    p.add_argument("--no-skills", action="store_true", help="add: não instala as skills sugeridas pelo papel")
    p.add_argument("--kind", choices=["implementer", "reviewer"], default="implementer", help="new: tipo do papel")
    p.set_defaults(fn=cmd_role)

    p = sub.add_parser("memory", help="memória manual do projeto (.agents/memory) — entra no AGENTS.md e em .claude/rules")
    p.add_argument("action", choices=["add", "list", "ls", "rm", "remove"])
    p.add_argument("text", nargs="*", help="add: o fato · rm: <tópico> [n]")
    p.add_argument("-t", "--topic", default="geral", help="tópico (arquivo) — padrão: geral")
    p.add_argument("--paths", help="globs separados por vírgula: memória só vale nesses caminhos")
    p.add_argument("-d", "--description", help="descrição curta do tópico")
    p.add_argument("--dir", default=".")
    p.set_defaults(fn=cmd_memory)

    p = sub.add_parser("sync", help="regenera AGENTS.md e adaptadores a partir de .agents/")
    p.add_argument("dir", nargs="?", default=".")
    p.add_argument("--agents", help="redefine adaptadores: claude,opencode,gemini | none")
    p.add_argument("--copy", action="store_true")
    p.add_argument("--check", action="store_true", help="não escreve; sai com 1 se algum arquivo gerado estiver desatualizado ou editado à mão (CI)")
    p.add_argument("--force", action="store_true", help="sobrescreve arquivos/blocos gerados que foram editados à mão")
    p.set_defaults(fn=cmd_sync)

    p = sub.add_parser("change", help="change requests em .agents/specs/changes (id CHANGE-NNN sequencial)")
    p.add_argument("action", choices=["new"])
    p.add_argument("title", nargs="+")
    p.add_argument("--feature", default="none", help="NNN ou pasta da feature afetada (padrão: none)")
    p.add_argument("--priority", default="Medium", choices=["Low", "Medium", "High", "Critical"])
    p.add_argument("--dir", default=".")
    p.set_defaults(fn=cmd_change)

    p = sub.add_parser("index", help="regenera .agents/specs/features.md (features, CRs, playbooks)")
    p.add_argument("dir", nargs="?", default=".")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("playbook", help="guias reutilizáveis em .agents/specs/playbooks")
    p.add_argument("action", choices=["new"])
    p.add_argument("name", nargs="+")
    p.add_argument("--dir", default=".")
    p.set_defaults(fn=cmd_playbook)

    p = sub.add_parser("commitlint", help="hook commit-msg: Conventional Commits (commitlint em projetos node) + bloqueio de atribuição de IA")
    p.add_argument("dir", nargs="?", default=".")
    p.add_argument("--no-install", action="store_true", help="não instala @commitlint/* (só cria config e hook)")
    p.set_defaults(fn=cmd_commitlint)

    p = sub.add_parser("doctor", help="verifica a instalação e o drift entre specs e código")
    p.add_argument("dir", nargs="?", default=".")
    p.set_defaults(fn=cmd_doctor)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except BrokenPipeError:
        sys.stderr.close()
        return 0
    except KeyboardInterrupt:
        say("\ninterrompido")
        return 130


if __name__ == "__main__":
    sys.exit(main())
