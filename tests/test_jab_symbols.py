"""The JAB signature table and the tool that checks it against a real bridge.

The check itself needs a JDK, so what runs here is the part that does not: that
the table is well formed, and that a DEF file is parsed the way DEF files are
actually written.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: tools/ is not a package, so load the checker by path.
_spec = importlib.util.spec_from_file_location(
    "check_jab_symbols", REPO_ROOT / "tools" / "check_jab_symbols.py"
)
checker = importlib.util.module_from_spec(_spec)
sys.modules["check_jab_symbols"] = checker
_spec.loader.exec_module(checker)


# ---------------------------------------------------------------------------
# The table itself
# ---------------------------------------------------------------------------

def test_every_signature_is_a_four_tuple():
    from pyjab.jabfixedfunc import SIGNATURES

    for entry in SIGNATURES:
        assert len(entry) == 4, entry
        name, _restype, argtypes, errorcheck = entry
        assert isinstance(name, str) and name, entry
        assert isinstance(argtypes, tuple), entry
        assert isinstance(errorcheck, bool), entry


def test_no_symbol_is_declared_twice():
    """A second declaration would silently override the first."""
    from pyjab.jabfixedfunc import SIGNATURES

    names = [entry[0] for entry in SIGNATURES]

    assert len(names) == len(set(names))


def test_the_symbols_called_by_pyjab_are_all_declared():
    """Nothing may be called before its signature is set.

    getattr on the DLL works without a declaration, so a missing entry does not
    fail loudly -- it truncates 64-bit arguments instead.
    """
    import ast
    from pyjab.jabfixedfunc import SIGNATURES

    declared = {entry[0] for entry in SIGNATURES}

    called = set()
    for path in (REPO_ROOT / "pyjab").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute) \
                    and node.value.attr == "bridge":
                called.add(node.attr)

    missing = sorted(called - declared)
    assert not missing, f"called but never declared: {missing}"


# ---------------------------------------------------------------------------
# Reading a DEF file
# ---------------------------------------------------------------------------

@pytest.fixture
def def_file(tmp_path):
    def write(text):
        path = tmp_path / "WinAccessBridge.DEF"
        path.write_text(text, encoding="utf-8")
        return path
    return write


def test_a_bare_export_list_is_read(def_file):
    path = def_file(
        "LIBRARY WinAccessBridge\n"
        "EXPORTS\n"
        "\n"
        "    Windows_run\n"
        "    getAccessibleContextInfo\n"
    )

    assert checker.exported_symbols(path) == {"Windows_run", "getAccessibleContextInfo"}


def test_comments_ordinals_and_renames_are_handled(def_file):
    """All three appear in the real file."""
    path = def_file(
        "; a comment\n"
        "EXPORTS\n"
        "    Windows_run\n"
        "    releaseJavaObject @12\n"
        "    getVersionInfo=getVersionInfoInternal\n"
        "    ; trailing comment after a symbol\n"
        "    isJavaWindow     ; and one here\n"
    )

    assert checker.exported_symbols(path) == {
        "Windows_run", "releaseJavaObject", "getVersionInfo", "isJavaWindow",
    }


def test_only_the_exports_section_is_read(def_file):
    """SECTIONS comes after EXPORTS and must not be mistaken for symbols."""
    path = def_file(
        "LIBRARY WinAccessBridge\n"
        "EXPORTS\n"
        "    Windows_run\n"
        "SECTIONS\n"
        "    .data READ WRITE\n"
    )

    assert checker.exported_symbols(path) == {"Windows_run"}


def test_a_missing_def_is_reported_not_crashed(monkeypatch, tmp_path):
    monkeypatch.setenv("JAVA_HOME", str(tmp_path / "nowhere"))
    monkeypatch.setattr(checker, "DEF_RELATIVE_PATHS", ())

    with pytest.raises(SystemExit) as excinfo:
        checker.find_def(str(tmp_path / "absent.DEF"))

    assert "no such file" in str(excinfo.value)


@pytest.mark.parametrize("entry", ["", "   ", "; only a comment", "EXPORTS"])
def test_an_empty_def_yields_no_symbols(def_file, entry):
    assert checker.exported_symbols(def_file(entry)) == set()
