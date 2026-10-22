"""Checagens do hook commit_msg.py. Roda com pytest ou `python tests/test_commit_msg.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "sddkit" / "templates" / "hooks"))
import commit_msg as m  # noqa: E402


def test_blocks_ai_attribution():
    assert m.problems("fix: a\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    assert m.problems("feat: a\n\nCo-authored-by: GitHub Copilot <copilot@github.com>")
    assert m.problems("feat: a\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)")
    assert m.problems("feat: a\n\nClaude-Session: https://claude.ai/code/x")


def test_allows_humans_and_plain_words():
    assert not m.problems("fix: a\n\nCo-authored-by: Maria <maria@x.com>")
    assert not m.problems("docs: explain the cursor position bug")
    assert not m.problems("fix: a\n# Co-Authored-By: Claude (comentário, o git remove)")


def test_conventional_header():
    assert m.problems("added stuff", conventional=True)
    assert not m.problems("feat(api)!: drop v1", conventional=True)
    assert not m.problems("Merge branch 'main'", conventional=True)
    assert not m.problems("added stuff")  # sem --conventional o cabeçalho fica com o commitlint


if __name__ == "__main__":
    test_blocks_ai_attribution()
    test_allows_humans_and_plain_words()
    test_conventional_header()
    print("ok")
