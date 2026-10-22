"""Checagens de specs.py: id de CR, status de feature e referências quebradas. Roda com pytest ou `python tests/test_specs.py`."""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sddkit import specs  # noqa: E402
from sddkit.out import Out  # noqa: E402


def _project() -> Path:
    root = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    feat = root / specs.SPECS / "features" / "001-faturas"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Feature Specification: Faturas\n")
    (feat / "tasks.md").write_text("- [x] T001 a\n- [ ] T002 b\n")
    (root / "libs").mkdir()
    (root / "libs" / "atRest.ts").write_text("")
    (root / "app" / "lib").mkdir(parents=True)
    (root / "app" / "lib" / "summary.ts").write_text("")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


def test_change_ids_feature_status_and_index():
    root = _project()
    a = specs.new_change(root, "Parcelar faturas", "001")
    b = specs.new_change(root, "Ação rápida")
    ids = [c["id"] for c in specs.load_changes(root)]
    assert sorted(ids) == ["CHANGE-001", "CHANGE-002"]
    assert b.name.endswith("acao-rapida.md")
    assert specs.next_change_id(specs.load_changes(root)) == "CHANGE-003"
    f = specs.load_features(root)[0]
    assert (f["id"], f["name"], f["status"], f["done"], f["total"]) == ("001", "Faturas", "In Progress", 1, 2)
    specs.write_index(root, Out(root, {}))
    assert "| 001 | Faturas | In Progress | 1/2 | CHANGE-001 |" in (root / specs.SPECS / "features.md").read_text()
    a.write_text(a.read_text().replace("CHANGE-001", "CHANGE-002"))  # id duplicado
    checks = {msg.split(" (")[0]: ok for ok, msg, *_ in specs.drift_checks(root, {"deps": []})}
    assert checks["change requests com id único"] is False


def test_broken_refs():
    root = _project()
    doc = root / "AGENTS.md"
    doc.write_text("Leia `missing.md`, `/specs/x.md`, `/contracts/openapi`, `libs/atRest`, `lib/summary.ts`,\n"
                   "`/v1/internal/events`, `/.well-known/jwks.json`, `spec.md`, `.agents/specs/features/<x>.md`.\n"
                   "```\n`ignored.md`\n```\n")
    (root / "contracts").mkdir()
    assert specs.broken_refs(root, doc) == ["missing.md", "/specs/x.md", "/contracts/openapi"]


if __name__ == "__main__":
    test_change_ids_feature_status_and_index()
    test_broken_refs()
    print("ok")
