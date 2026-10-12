"""What ``tools/session_metrics.py`` counts, asserted rather than trusted.

The tool reports on how this project is worked on, and until now nothing asserted its own
numbers: no test referenced it at all.  An audit mutated two load-bearing lines in
:func:`session_metrics.collect` and the output changed silently -- ``data.name`` read as
``data.toolName`` named every call ``(unnamed)``, and reading the ``skill`` tool's
``arguments`` as an object rather than a JSON string reported every skill as ``NEVER``.  Both
are the kind of mistake the tool exists to find in other people's work, so both get a test
here.

Everything is driven through synthetic transcript rows and a fake ``read_transcript``: the
real transcripts are ``zstd``-compressed inside the working environment's own state
directory, which a portable test must not read and must not name.  Nothing here touches
it, and nothing here needs it.
"""

from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def load():
    """session_metrics by path: tools/ is not a package."""
    spec = importlib.util.spec_from_file_location(
        "session_metrics", REPO_ROOT / "tools" / "session_metrics.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["session_metrics"] = module
    spec.loader.exec_module(module)
    return module


tool = load()


#: Two rows in the shape the tool reads: one ordinary call, and one ``skill`` call whose
#: ``arguments`` is a JSON **string** -- which is what the transcript holds, and the half of
#: the tool's docstring that is easiest to get wrong.
ROWS = [
    {"type": "tool/call", "data": {"name": "Bash", "arguments": {"command": "ls"}}},
    {"type": "tool/call", "data": {"name": "skill",
                                   "arguments": '{"name": "pyjab-testing"}'}},
]


@pytest.fixture
def transcripts(monkeypatch):
    """Install synthetic rows in place of the zstd transcripts ``collect`` would read."""
    def install(rows):
        monkeypatch.setattr(tool, "read_transcript", lambda path: iter(rows))
    return install


def test_an_ordinary_tool_call_is_counted_under_its_own_name(transcripts):
    """``data.toolName`` instead of ``data.name`` names every call ``(unnamed)``."""
    transcripts(ROWS)

    tools, _skills, calls = tool.collect([Path("synthetic")])

    assert calls == 2
    assert tools == Counter({"Bash": 1, "skill": 1})
    assert "(unnamed)" not in tools


def test_a_skill_call_is_counted_under_the_skill_in_its_json_string(transcripts):
    """``arguments`` is a JSON string; reading it as an object names no skill at all."""
    transcripts(ROWS)

    _tools, skills, _calls = tool.collect([Path("synthetic")])

    assert skills == Counter({"pyjab-testing": 1})
    assert "(unparsed)" not in skills


def test_the_empty_result_names_the_workspace_it_searched(capsys, monkeypatch, tmp_path):
    """From a worktree the slug matches no session; the message has to say where it looked."""
    monkeypatch.setattr(tool, "workspace_session_dirs", lambda workspace: [])
    monkeypatch.setattr(sys, "argv", ["session_metrics.py", "--workspace", str(tmp_path)])

    assert tool.main() == 0
    output = capsys.readouterr().out

    assert "No tool calls found" in output
    assert str(tmp_path.resolve()) in output
