"""The local-only files guard.

What this test is for: `.gitignore` does not protect an sdist. An sdist is built
from the *working tree*, so a gitignored file is still there when setuptools
walks it, and `MANIFEST.in` is the only thing that excludes it. Two facts are
therefore being kept true at once, and they fail independently.

The guard itself is mutation-tested: removing `/.agents/` from `.gitignore`
makes it report `FAILED: git does not ignore '.agents'`, and putting
`graft .agents` into `MANIFEST.in` makes it report `FAILED: '.agents' is inside
the sdist`. A guard that could not fail would be decoration -- 24 pins in a
sibling project looked complete until none of them was ever made to go red.

These tests cover the parts the mutation test cannot: the archive parsing, and
that the two records have not drifted apart.
"""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_local_only_files as guard  # noqa: E402


def test_every_local_path_is_also_named_in_gitignore():
    """Two records, or one of them is not a check.

    A path that is listed here and missing from `.gitignore` is a local note
    that stops being local without anybody deciding that.
    """
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    missing = [p for p in guard.LOCAL_PATHS if p not in gitignore]
    assert not missing, f"not named in .gitignore: {missing}"


def test_the_list_is_not_empty():
    assert len(guard.LOCAL_PATHS) >= 5


def test_git_ignores_says_yes_for_a_local_path_and_no_for_a_shipped_one():
    """The control. Without it, a `git_ignores` that always returned True would
    pass every other test here."""
    assert guard.git_ignores(".agents") is True
    assert guard.git_ignores("README.rst") is False


def test_the_guard_passes_on_this_checkout_without_building_anything():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_local_only_files.py"), "--no-sdist"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASSED" in result.stdout


def a_tarball(tmp_path, name, members):
    archive = tmp_path / name
    with tarfile.open(archive, "w:gz") as tar:
        for member in members:
            data = b"x"
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return archive


def test_sdist_members_strips_the_single_top_level_directory(tmp_path):
    archive = a_tarball(tmp_path, "pyjab-1.0.0.tar.gz", [
        "pyjab-1.0.0/PKG-INFO",
        "pyjab-1.0.0/pyjab/__init__.py",
    ])
    assert guard.sdist_members(archive) == ["PKG-INFO", "pyjab/__init__.py"]


def test_sdist_members_finds_a_local_path_when_it_is_there(tmp_path):
    """The archive half, on a synthetic archive, so it needs no build.

    This is the assertion that would have caught the `docs/` notes reaching
    PyPI, and it is the one the mutation test exercises end to end.
    """
    archive = a_tarball(tmp_path, "pyjab-1.0.0.tar.gz", [
        "pyjab-1.0.0/PKG-INFO",
        "pyjab-1.0.0/AGENTS.md",
        "pyjab-1.0.0/.agents/skills/pyjab-testing/SKILL.md",
    ])
    members = guard.sdist_members(archive)
    assert "AGENTS.md" in members
    assert any(m.startswith(".agents/") for m in members)
