"""The parts of the M0 comparison that can be checked without Windows.

The measurement itself needs a Java application, a JAB bridge and a UIA client on
Windows, and none of that exists here. What does exist anywhere is the reporting: which
rows were answered, what the verdict is, and -- the one that matters -- the difference
between "UIA reported nothing" and "UIA could not be asked".

That distinction is the whole reason this file is worth writing. A comparison script that
cannot read UIA would otherwise print "pyjab: 40 elements, UIA: 0" and look like a
decisive result for the thing under test, which is also the thing the author wants to
win. Unavailable is a status, not a number, and these tests hold that line.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def load():
    """verify_m0 by path: tools/ is not a package."""
    spec = importlib.util.spec_from_file_location(
        "verify_m0", REPO_ROOT / "tools" / "verify_m0.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_m0"] = module
    spec.loader.exec_module(module)
    return module


verify_m0 = load()


def a_full_pair():
    """One measurement of each side, both taken."""
    jab = {
        "windows": {"java": 1, "sample": ["PyjabTestApp"]},
        "elements": 40, "roles": 9, "named": 22, "depth": 6,
        "role_counts": {"panel": 12, "label": 8, "push button": 3},
        "table": {"role": "table", "name": "Grid", "children": 9},
        "cell": {"index": 6, "role": "label", "text": "row3col2", "of": 9},
        "tree": {"count": 4, "named": 4, "sample": ["root", "child"]},
        "button": {"count": 3, "sample": "push button", "states": "enabled,showing"},
    }
    uia = {
        "windows": {"top_level": 12, "sample": ["PyjabTestApp"]},
        "elements": 55, "roles": 11, "named": 30, "depth": 7,
        "role_counts": {"Pane": 20, "Button": 3},
        "table": {"role": "Table", "name": "Grid"},
        "cell": {"index": 6, "role": "Text", "text": "row3col2", "of": 9},
        "tree": {"count": 4, "named": 4, "sample": ["root", "child"]},
        "button": {"count": 3, "sample": "Button", "patterns": "invoke"},
    }
    return jab, uia


# ---------------------------------------------------------------------------
# Unavailable is not zero
# ---------------------------------------------------------------------------

def test_an_unavailable_reading_is_not_rendered_as_a_zero():
    """The failure this whole file exists for."""
    assert verify_m0.describe(verify_m0.Unavailable("no client")) == \
        "UNAVAILABLE (no client)"
    assert verify_m0.describe(0) == "0"


def test_a_missing_uia_client_makes_every_uia_row_unanswered():
    jab, _uia = a_full_pair()
    uia = {"_client": verify_m0.Unavailable("the uiautomation package is not importable")}

    lines, complete = verify_m0.report(jab, uia)
    rendered = "\n".join(lines)

    assert complete is False
    assert "could not be measured" in rendered
    assert "not zero" in rendered, "the report has to say so in words, not just omit"


def test_a_missing_client_does_not_make_the_verdict_a_win():
    """The answer that would most flatter pyjab is the one to refuse to give."""
    jab, _uia = a_full_pair()
    uia = {"_client": verify_m0.Unavailable("no client")}

    conclusion = verify_m0.verdict(jab, uia, complete=False)

    assert "INCONCLUSIVE" in conclusion
    assert "CLEARLY BETTER" not in conclusion


def test_one_unanswered_row_makes_the_whole_report_incomplete():
    """A comparison is only a comparison where both sides answered."""
    jab, uia = a_full_pair()
    uia["tree"] = verify_m0.Unavailable("no UIA element with 'tree' in its type")

    _lines, complete = verify_m0.report(jab, uia)

    assert complete is False


def test_a_fully_measured_pair_is_complete():
    jab, uia = a_full_pair()
    _lines, complete = verify_m0.report(jab, uia)
    assert complete is True


# ---------------------------------------------------------------------------
# The verdict follows the plan's decision table
# ---------------------------------------------------------------------------

def test_jab_reading_a_cell_that_uia_cannot_is_the_clear_win():
    """The plan's first row: UIA cannot read the table cell and pyjab can."""
    jab, uia = a_full_pair()
    uia["cell"] = {"index": 6, "role": "Pane", "text": "", "of": 9}

    conclusion = verify_m0.verdict(jab, uia, complete=True)

    assert "CLEARLY BETTER" in conclusion
    assert "Continue" in conclusion


def test_both_reading_the_cell_is_about_the_same():
    """The plan's second row, which is the one that would cost the most to miss."""
    jab, uia = a_full_pair()

    conclusion = verify_m0.verdict(jab, uia, complete=True)

    assert "ABOUT THE SAME" in conclusion
    assert "Downgrade" in conclusion


def test_uia_exposing_substantially_more_is_flagged_for_a_human():
    """The plan's third row, with a caveat: a bigger tree is not a better one."""
    jab, uia = a_full_pair()
    # Named elements, not the total: see the note in verdict().
    jab["named"] = 10
    uia["named"] = 60

    conclusion = verify_m0.verdict(jab, uia, complete=True)

    assert "UIA LOOKS BETTER" in conclusion
    assert "Check by hand" in conclusion


def test_an_empty_table_cell_on_both_sides_is_not_read_as_a_win_for_either():
    jab, uia = a_full_pair()
    jab["cell"] = {"index": 6, "role": "label", "text": "", "of": 9}
    uia["cell"] = {"index": 6, "role": "Text", "text": "", "of": 9}

    conclusion = verify_m0.verdict(jab, uia, complete=True)

    assert "CLEARLY BETTER" not in conclusion


# ---------------------------------------------------------------------------
# Small pieces
# ---------------------------------------------------------------------------

def test_counts_are_ordered_by_frequency():
    counts = verify_m0._counts(["a", "b", "a", "c", "a", "b"])
    assert list(counts.items()) == [("a", 3), ("b", 2), ("c", 1)]


def test_describe_omits_the_control_object():
    """It is a live COM object and must not reach the report or the JSON."""
    text = verify_m0.describe({"role": "Table", "name": "Grid", "control": object()})
    assert text == "role=Table, name=Grid"


def test_every_question_the_plan_names_is_asked():
    """The plan's four operations, plus the size questions that make them comparable."""
    keys = {key for key, _label in verify_m0.QUESTIONS}
    for required in ("windows", "table", "cell", "button", "elements"):
        assert required in keys, required


def test_it_refuses_to_run_off_windows(capsys, monkeypatch):
    """Rather than measuring nothing and reporting it as a result."""
    monkeypatch.setattr(verify_m0.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(sys, "argv", ["verify_m0.py", "--title", "X"])

    assert verify_m0.main() == 2
    assert "needs Windows" in capsys.readouterr().err


def keys_measured_by(function_name):
    """The keys a side's function puts into the dict it returns, read from its source.

    Mechanical because the alternative is what happened: ``windows`` was listed as a
    question in ``QUESTIONS``, both sides were written without measuring it, and the
    report said UNAVAILABLE for it on every run -- which made every comparison
    incomplete for a reason nobody would have looked for in the reporting code.
    """
    import ast

    source = (REPO_ROOT / "tools" / "verify_m0.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == function_name)

    keys = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not targets or "result" not in targets and "result" not in str(targets):
            continue
        if isinstance(node.value, ast.Dict):
            keys.update(k.value for k in node.value.keys
                        if isinstance(k, ast.Constant))
        # result["x"] = ... is a Subscript assignment, caught below
    for node in ast.walk(function):
        if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript)
                and isinstance(node.targets[0].slice, ast.Constant)):
            keys.add(node.targets[0].slice.value)
    return keys


@pytest.mark.parametrize("side", ["jab_side", "uia_side"])
def test_each_side_actually_measures_every_question_asked(side):
    """A question nobody measures is reported UNAVAILABLE for ever."""
    asked = {key for key, _label in verify_m0.QUESTIONS}
    measured = keys_measured_by(side)

    missing = asked - measured
    assert not missing, f"{side} never measures {sorted(missing)}"
