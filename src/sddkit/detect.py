"""Detecção de stack do projeto para sugerir skills."""
from __future__ import annotations

import json
import re
from pathlib import Path

SOURCE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".php",
              ".cs", ".vue", ".svelte", ".dart", ".swift", ".ex", ".exs", ".c", ".cpp", ".h"}
SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "dist", "build", "target", "__pycache__",
             ".agents", ".specify", ".claude", ".opencode", ".gemini", "specs", ".next"}

NODE_MAP = {
    "react": {"react", "frontend"},
    "vue": {"frontend"}, "nuxt": {"frontend"}, "svelte": {"frontend"}, "@sveltejs/kit": {"frontend"},
    "@angular/core": {"frontend"}, "solid-js": {"frontend"}, "astro": {"frontend"},
    "react-native": {"react-native", "react"}, "expo": {"expo", "react-native", "react"},
    "@modelcontextprotocol/sdk": {"mcp"}, "@anthropic-ai/sdk": {"anthropic-sdk"},
    "@anthropic-ai/claude-agent-sdk": {"anthropic-sdk"},
    "express": {"backend", "express"}, "fastify": {"backend"}, "@nestjs/core": {"backend"}, "hono": {"backend"},
    "koa": {"backend"}, "@trpc/server": {"backend"}, "next": {"next", "react", "frontend", "backend"},
    "prisma": {"db", "prisma"}, "@prisma/client": {"db", "prisma"}, "drizzle-orm": {"db"}, "typeorm": {"db"},
    "sequelize": {"db"}, "knex": {"db"}, "mongoose": {"db"}, "pg": {"db"}, "mysql2": {"db"},
    "@supabase/supabase-js": {"db"},
}
NODE_MAP.update({"bullmq": {"queue"}, "bull": {"queue"}, "bee-queue": {"queue"}, "pg-boss": {"queue"},
                 "amqplib": {"queue"}, "kafkajs": {"queue"}, "zod": {"zod"}, "fast-check": {"fast-check"},
                 "tailwindcss": {"tailwind"}, "@mui/material": {"mui"},
                 "@tanstack/react-query": {"tanstack-query"}, "@tanstack/react-router": {"tanstack-router"},
                 "electron": {"desktop"}, "@tauri-apps/api": {"desktop"}})
PY_PDF = {"pdfplumber", "pymupdf", "fitz", "pypdf", "pypdf2", "pdfminer.six", "pdfminer", "camelot-py",
          "tabula-py", "pytesseract", "pdf2image", "docling", "unstructured"}
PY_MAP = {"bullmq": {"queue"}, "celery": {"queue"}, "rq": {"queue"}, "pydantic": {"pydantic"},
          **{k: {"pdf-parser"} for k in PY_PDF},
          "mcp": {"mcp"}, "fastmcp": {"mcp"}, "anthropic": {"anthropic-sdk"},
          "claude-agent-sdk": {"anthropic-sdk"}, "fastapi": {"backend"},
          "flask": {"backend"}, "sqlalchemy": {"db"}, "alembic": {"db"}, "psycopg": {"db"},
          "psycopg2": {"db"}, "django": {"backend", "db"}}


def _count_source_files(root: Path, limit: int = 50) -> int:
    n = 0
    stack = [root]
    while stack and n < limit:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if e.name not in SKIP_DIRS and not e.name.startswith("."):
                    stack.append(e)
            elif e.suffix in SOURCE_EXT:
                n += 1
    return n


MANIFESTS = {"package.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt", "Pipfile"}


def _manifests(root: Path, max_depth: int = 3) -> list[Path]:
    """Manifestos na raiz e em pacotes de monorepo (até max_depth níveis)."""
    found, stack = [], [(root, 0)]
    while stack:
        d, depth = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_file() and e.name in MANIFESTS:
                found.append(e)
            elif e.is_dir() and depth < max_depth and e.name not in SKIP_DIRS and not e.name.startswith("."):
                stack.append((e, depth + 1))
    return sorted(found)


def detect(root: Path) -> dict:
    stacks: set[str] = set()
    evidence: list[str] = []
    deps_found: set[str] = set()
    py_text = ""

    for mf in _manifests(root):
        rel = str(mf.relative_to(root))
        if mf.name == "package.json":
            stacks.add("node")
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            hits = [d for d in NODE_MAP if d in deps]
            deps_found.update(hits)
            for dep in hits:
                stacks |= NODE_MAP[dep]
            if hits or mf.parent == root:
                evidence.append(rel + (f" ({', '.join(hits)})" if hits else ""))
        else:
            stacks.add("python")
            evidence.append(rel)
            try:
                py_text += mf.read_text(encoding="utf-8").lower() + "\n"
            except OSError:
                pass
    for dep, tags in PY_MAP.items():
        if dep == "fitz":
            continue
        if re.search(r'(^|["\'\s,\[])' + re.escape(dep) + r'([<>=~!\s"\',\]\[]|$)', py_text, re.M):
            stacks |= tags
            deps_found.add(dep)
            evidence.append(dep)

    for f, tag in [("go.mod", "go"), ("Cargo.toml", "rust"), ("pom.xml", "java"),
                   ("build.gradle", "java"), ("build.gradle.kts", "java"), ("Gemfile", "ruby"),
                   ("composer.json", "php"), ("pubspec.yaml", "flutter"),
                   ("vercel.json", "vercel"), ("Dockerfile", "docker")]:
        if (root / f).exists():
            stacks.add(tag)
            evidence.append(f)
    for tag in ("go", "rust", "java", "ruby", "php"):
        if tag in stacks:
            stacks.add("backend")
    for f, tag in [("docker-compose.yml", "docker"), ("compose.yaml", "docker"), ("compose.yml", "docker"),
                   (".github/workflows", "ci"), (".gitlab-ci.yml", "ci"), ("terraform", "iac"),
                   ("migrations", "db"), ("prisma/schema.prisma", "db"), ("alembic.ini", "db"),
                   ("components.json", "shadcn"), ("src-tauri", "desktop"), ("Package.swift", "apple")]:
        if (root / f).exists():
            stacks.add(tag)
            evidence.append(f)
    if "node" in stacks and "python" in stacks:
        stacks.add("polyglot")
    if any(root.glob("*.tf")):
        stacks.add("iac")
    if any(root.glob("*.xcodeproj")):
        stacks.add("apple")
    if (root / ".vercel").is_dir():
        stacks.add("vercel")
    if (root / "index.html").is_file():
        stacks.add("frontend")

    n_src = _count_source_files(root)
    return {
        "stacks": sorted(stacks),
        "has_code": n_src >= 5,
        "source_files": n_src if n_src < 50 else "50+",
        "evidence": evidence,
        "deps": sorted(deps_found),
        "git": (root / ".git").exists(),
    }


def matches(entry: dict, info: dict) -> bool:
    when = entry.get("when", {})
    if when.get("always"):
        return True
    if when.get("has_code") and info["has_code"]:
        return True
    return bool(set(when.get("stacks", [])) & set(info["stacks"]))
