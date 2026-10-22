"""Specs do projeto em .agents/specs/: features (Spec Kit), change requests, playbooks e docs centrais.

    .agents/specs/
      architecture.md stack.md coding-standards.md design-system.md   ← docs centrais (preenchidos pela equipe)
      features.md                                                     ← índice gerado (`sddkit index`)
      features/NNN-slug/   spec.md plan.md tasks.md …                 ← uma pasta por feature (Spec Kit)
      changes/YYYY-MM-DD-slug.md                                      ← change requests (CHANGE-NNN)
      playbooks/<slug>.md                                             ← guias reutilizáveis, portáveis
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from .frontmatter import parse

SPECS = Path(".agents") / "specs"
CR_STATUS = ("Proposed", "Approved", "Rejected", "In Progress", "Implemented")
IDX_BEGIN, IDX_END = "<!-- sddkit:index:begin -->", "<!-- sddkit:index:end -->"
CORE_DOCS = ("architecture.md", "stack.md", "coding-standards.md", "design-system.md")
PLACEHOLDER = "[PREENCHER"


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")
    return s[:60].rstrip("-") or "sem-titulo"


def _author(root: Path) -> str:
    r = subprocess.run(["git", "config", "user.name"], cwd=root, capture_output=True, text=True)
    return r.stdout.strip() or "—"


# ───────────────────────── change requests ─────────────────────────
def load_changes(root: Path) -> list[dict]:
    out = []
    for f in sorted((root / SPECS / "changes").glob("*.md")):
        meta, _ = parse(f.read_text(encoding="utf-8"))
        m = re.fullmatch(r"CHANGE-(\d+)", str(meta.get("id", "")).strip())
        out.append({**meta, "num": int(m.group(1)) if m else None, "file": f})
    return out


def next_change_id(changes: list[dict]) -> str:
    return f"CHANGE-{max([c['num'] for c in changes if c['num'] is not None], default=0) + 1:03d}"


def new_change(root: Path, title: str, feature: str = "none", priority: str = "Medium") -> Path:
    changes = load_changes(root)
    cid = next_change_id(changes)
    today = dt.date.today().isoformat()
    d = root / SPECS / "changes"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{today}-{slug(title)}.md"
    n = 2
    while f.exists():
        f = d / f"{today}-{slug(title)}-{n}.md"
        n += 1
    tpl = (Path(__file__).parent / "templates" / "specs-new" / "change.md").read_text(encoding="utf-8")
    f.write_text(tpl.format(id=cid, title=title.replace('"', "'"), feature=feature, author=_author(root),
                            date=today, priority=priority), encoding="utf-8")
    return f


# ───────────────────────── features ─────────────────────────
def load_features(root: Path) -> list[dict]:
    out = []
    for d in sorted(p for p in (root / SPECS / "features").glob("[0-9]*") if p.is_dir()):
        spec, tasks = d / "spec.md", d / "tasks.md"
        name = d.name.split("-", 1)[-1].replace("-", " ").capitalize()
        if spec.exists():
            h1 = re.search(r"^# (.+)$", spec.read_text(encoding="utf-8"), re.M)
            if h1:
                name = re.sub(r"^Feature Specification:\s*", "", h1.group(1)).strip()
        done = total = 0
        for t in sorted(d.glob("tasks*.md")):
            txt = t.read_text(encoding="utf-8")
            done += len(re.findall(r"^\s*- \[[xX]\]", txt, re.M))
            total += len(re.findall(r"^\s*- \[[ xX]\]", txt, re.M))
        if not spec.exists():
            status = "No spec"
        elif total:
            status = "Implemented" if done == total else "In Progress" if done else "Planned"
        else:
            status = "Planned" if (d / "plan.md").exists() else "Specified"
        out.append({"id": d.name.split("-", 1)[0], "dir": d, "name": name, "status": status,
                    "done": done, "total": total, "has_spec": spec.exists()})
    return out


def _feature_of(change: dict, features: list[dict]) -> str:
    v = change.get("feature", "")
    v = f"{v:03d}" if isinstance(v, int) else str(v).strip()  # `feature: 001` vira int no YAML
    for f in features:
        if v and (v == f["id"] or v == f["dir"].name):
            return f["id"]
    return v or "—"


def render_index(root: Path) -> str:
    feats, changes = load_features(root), load_changes(root)
    by_feat: dict[str, list[str]] = {}
    for c in changes:
        by_feat.setdefault(_feature_of(c, feats), []).append(str(c.get("id", "?")))
    lines = ["## Features", "", "| ID | Feature | Status | Tasks | Changes | Spec |", "|---|---|---|---|---|---|"]
    for f in feats:
        tasks = f"{f['done']}/{f['total']}" if f["total"] else "—"
        link = f"[spec.md](features/{f['dir'].name}/spec.md)" if f["has_spec"] else "—"
        lines.append(f"| {f['id']} | {f['name']} | {f['status']} | {tasks} | {', '.join(by_feat.get(f['id'], [])) or '—'} | {link} |")
    if not feats:
        lines.append("| — | (nenhuma feature ainda: `/sdd-feature`) | | | | |")
    lines += ["", "## Change requests", "", "| ID | Título | Status | Feature | Data |", "|---|---|---|---|---|"]
    for c in sorted(changes, key=lambda c: (c["num"] is None, c["num"] or 0)):
        lines.append(f"| [{c.get('id', '?')}](changes/{c['file'].name}) | {c.get('title', c['file'].stem)} | "
                     f"{c.get('status', '?')} | {_feature_of(c, feats)} | {c.get('createdAt', '')} |")
    if not changes:
        lines.append("| — | (nenhuma ainda: `/sdd-change`) | | | |")
    pbs = sorted((root / SPECS / "playbooks").glob("*.md"))
    lines += ["", "## Playbooks", ""]
    for p in pbs:
        meta, body = parse(p.read_text(encoding="utf-8"))
        h1 = re.search(r"^# (.+)$", body, re.M)
        lines.append(f"- [{h1.group(1) if h1 else p.stem}](playbooks/{p.name})" + (f" — {meta['description']}" if meta.get("description") else ""))
    if not pbs:
        lines.append("- (nenhum ainda: `sddkit playbook new <nome>`)")
    return "\n".join(lines)


def index_text(root: Path) -> str:
    """Conteúdo esperado de features.md (o texto fora dos marcadores é preservado)."""
    p = root / SPECS / "features.md"
    text = p.read_text(encoding="utf-8") if p.exists() else (
        "# Índice de specs\n\nGerado por `sddkit index` entre os marcadores; o texto fora deles é seu.\n")
    block = f"{IDX_BEGIN}\n{render_index(root)}\n{IDX_END}"
    pat = re.compile(re.escape(IDX_BEGIN) + r".*?" + re.escape(IDX_END), re.S)
    return pat.sub(lambda _: block, text) if pat.search(text) else text.rstrip() + "\n\n" + block + "\n"


def write_index(root: Path) -> Path | None:
    if not (root / SPECS).is_dir():
        return None
    p = root / SPECS / "features.md"
    p.write_text(index_text(root), encoding="utf-8")
    return p


# ───────────────────────── playbooks ─────────────────────────
def new_playbook(root: Path, name: str) -> Path:
    d = root / SPECS / "playbooks"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{slug(name)}.md"
    if f.exists():
        raise SystemExit(f"✗ {f.relative_to(root)} já existe.")
    tpl = (Path(__file__).parent / "templates" / "specs-new" / "playbook.md").read_text(encoding="utf-8")
    f.write_text(tpl.format(title=name, date=dt.date.today().isoformat()), encoding="utf-8")
    return f


# ───────────────────────── drift (doctor) ─────────────────────────
FILE_EXT = r"\.(md|json|ya?ml|toml|ts|tsx|js|mjs|cjs|py|sh|sql|css|html)$"
# artefatos que existem por feature/skill, citados genericamente — não são referências a um arquivo do projeto
GENERIC = {"spec.md", "plan.md", "research.md", "data-model.md", "tasks.md", "analysis.md", "quickstart.md",
           "requirements.md", "SKILL.md", "README.md"}


def _refs(text: str) -> list[str]:
    """Caminhos citados num markdown (links e `código`), fora de blocos ``` e sem placeholders."""
    body = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
    toks = re.findall(r"\]\(([^)\s]+)\)", body) + re.findall(r"`([^`\s]+)`", body)
    out = []
    for t in toks:
        t = t.split("#")[0].rstrip(".,;:")
        if not t or re.match(r"^[a-z]+:", t) or re.search(r"[<>{}*$|?]|NNN|YYYY|XXX|\.\.\.", t):
            continue
        out.append(t)
    return out


def _tracked(root: Path) -> list[str]:
    r = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True)
    return r.stdout.splitlines() if r.returncode == 0 else []


def broken_refs(root: Path, doc: Path, tracked: list[str] | None = None) -> list[str]:
    """Caminhos citados que não existem. `/x` é ancorado na raiz (estrito); `x/y` vale se algum arquivo
    versionado terminar nele (ex.: `lib/summary.ts` dentro de um app) ou, sem extensão, for um módulo (`libs/atRest`)."""
    tracked = _tracked(root) if tracked is None else tracked
    bad = []
    for t in dict.fromkeys(_refs(doc.read_text(encoding="utf-8"))):
        anchored, rel = t.startswith("/"), t.lstrip("/").removeprefix("./")
        has_ext = re.search(FILE_EXT, rel) is not None
        first_is_dir = (root / rel.split("/")[0]).is_dir()
        if "/" not in rel:
            if not rel.endswith(".md") or rel in GENERIC:  # nome solto: só docs .md do projeto (ex.: `architecture.md`)
                continue
            places = (root, doc.parent, root / SPECS, root / ".specify" / "memory")
        elif anchored and not first_is_dir and not rel.endswith(".md"):  # rota/URL (`/v1/...`, `/.well-known/...`)
            continue
        elif not (has_ext or first_is_dir) or (rel.rsplit("/", 1)[-1] in GENERIC and not first_is_dir):
            continue
        else:
            places = (root, doc.parent, root / ".specify", root / SPECS)
        if any((p / rel).exists() for p in places):
            continue
        if not anchored and any(f == rel or f.endswith("/" + rel) or (not has_ext and (f.startswith(rel + ".")
                                or f.startswith(rel + "/"))) for f in tracked):
            continue
        bad.append(t)
    return bad


def drift_checks(root: Path, info: dict) -> list[tuple[bool, str, str, list[str]]]:
    """(ok, mensagem, correção, detalhes) — consumido pelo `sddkit doctor`."""
    sdir = root / SPECS
    out: list[tuple[bool, str, str, list[str]]] = []
    if not sdir.is_dir():
        return [(False, f"{SPECS}/ (features, changes, playbooks)", "sddkit init", [])]

    stray = [p for p in (root / "specs", root / ".specify" / "specs") if p.is_dir()]
    out.append((not stray, "specs só em .agents/specs/", "mova as pastas para .agents/specs/features/ e apague as antigas",
                [str(p.relative_to(root)) for p in stray]))

    fj = root / ".specify" / "feature.json"
    if fj.exists():
        try:
            cur = json.loads(fj.read_text(encoding="utf-8")).get("feature_directory", "")
        except json.JSONDecodeError:
            cur = "?"
        out.append((bool(cur) and (root / cur).is_dir(), f".specify/feature.json → {cur or '—'}",
                    "aponte para uma pasta existente em .agents/specs/features/ ou apague o arquivo", []))
    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        m = re.search(r"<!-- SPECKIT START -->(.*?)<!-- SPECKIT END -->", agents_md.read_text(encoding="utf-8"), re.S)
        plan = re.search(r"(\S+/plan\.md)", m.group(1)) if m else None
        if plan:
            out.append(((root / plan.group(1)).exists(), f"bloco SPECKIT do AGENTS.md → {plan.group(1)}",
                        "/speckit-agent-context-update na feature atual (ou remova o bloco)", []))

    docs = [d for d in (agents_md, root / ".specify" / "memory" / "constitution.md", *sorted(sdir.glob("*.md")))
            if d.exists() and d.name != "features.md"]
    tracked = _tracked(root)
    bad = [f"{d.relative_to(root)}: {', '.join(b)}" for d in docs if (b := broken_refs(root, d, tracked))]
    out.append((not bad, "referências a arquivos existem (AGENTS.md, constituição, docs de .agents/specs)",
                "corrija ou remova os caminhos", bad))

    todo = [d for d in CORE_DOCS if (sdir / d).exists() and PLACEHOLDER in (sdir / d).read_text(encoding="utf-8")]
    out.append((not todo, "docs centrais preenchidos", f"preencha {', '.join(todo)} em {SPECS}/", []))

    def norm(x: str) -> str:  # "React Query" == "react-query", "Tailwind CSS" == "tailwindcss"
        return re.sub(r"[\s_.-]+", "", x.lower())
    arch = norm(" ".join((sdir / d).read_text(encoding="utf-8") for d in ("architecture.md", "stack.md") if (sdir / d).exists()))
    if arch:
        def mentioned(dep: str) -> bool:
            return any(norm(n) in arch for n in {dep, dep.lstrip("@").split("/")[-1], dep.lstrip("@").split("/")[0]})
        miss = [d for d in info.get("deps", []) if not mentioned(d)]
        out.append((not miss, "dependências de arquitetura citadas em architecture.md/stack.md",
                    "documente-as (ou remova a dependência)", miss))

    feats = load_features(root)
    nospec = [f["dir"].name for f in feats if not f["has_spec"]]
    out.append((not nospec, f"features com spec.md ({len(feats)})", "crie o spec.md (ou aponte o CR que é a spec)", nospec))
    idx = sdir / "features.md"
    out.append((idx.exists() and idx.read_text(encoding="utf-8") == index_text(root),
                "features.md em dia com as pastas e os CRs", "sddkit index", []))

    changes = load_changes(root)
    ids: dict[str, list[str]] = {}
    for c in changes:
        ids.setdefault(str(c.get("id", "—")), []).append(c["file"].name)
    dup = [f"{i}: {', '.join(fs)}" for i, fs in ids.items() if len(fs) > 1 or i == "—"]
    out.append((not dup, f"change requests com id único ({len(changes)})", "renumere com o próximo id livre", dup))
    st = [f"{c['file'].name}: {c.get('status', '—')}" for c in changes if c.get("status") not in CR_STATUS]
    out.append((not st, "status de CR no enum (" + " | ".join(CR_STATUS) + ")", "datas e notas vão no corpo do CR", st))
    nof = [c["file"].name for c in changes if not str(c.get("feature", "")).strip()]
    out.append((not nof, "CRs com campo feature (NNN, slug ou none)", "acrescente `feature:` no frontmatter", nof))

    if (root / ".claude").is_dir():
        cm = root / "CLAUDE.md"
        out.append((cm.exists() and "@AGENTS.md" in cm.read_text(encoding="utf-8"), "CLAUDE.md importa @AGENTS.md",
                    "sddkit sync --agents claude (ou crie CLAUDE.md com @AGENTS.md)", []))
    return out
