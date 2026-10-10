"""The parts of the return-value sweep that can be checked without Windows.

The measurement itself needs a Java application, a JAB bridge and an interactive desktop,
and none of that exists off Windows. What does exist anywhere is the machinery that decides
what the sweep may claim: how a raw return is described, what ``errcheck`` would do to it,
which symbols are still unpublished, and -- the one that matters -- the difference between
**"this symbol returned falsy"** and **"this symbol was never reached"**.

That distinction is the whole reason the tool is written this way. The easy version of it
prints a raw value for every symbol it can find a call site for and calls a run with no
falsy values a pass, which is also exactly the run that proves nothing for the symbols it
never reached. A partial sweep has to come out ``INCONCLUSIVE``, and these tests hold that
line.

The Rows/Verdict/Reach objects are driven directly: they are what ``report()`` reads, they
cross the boundary between the sweep and the output, and they are the only part of the file
whose behaviour is observable on this machine.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def load():
    """verify_jab_return_values by path: tools/ is not a package."""
    spec = importlib.util.spec_from_file_location(
        "verify_jab_return_values",
        REPO_ROOT / "tools" / "verify_jab_return_values.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_jab_return_values"] = module
    spec.loader.exec_module(module)
    return module


tool = load()


# ---------------------------------------------------------------------------
# One measurement, described
# ---------------------------------------------------------------------------

def test_describe_carries_the_type_as_well_as_the_value():
    """The type is the load-bearing half: ``1`` and ``True`` compare equal in Python."""
    assert tool.describe(1) == "1 (int)"
    assert tool.describe(True) == "True (bool)"
    assert tool.describe(None) == "None (NoneType)"


def test_describe_survives_a_repr_that_raises():
    """A ctypes handle can fail to render; that must not take the whole report down."""
    class Unhappy:
        def __repr__(self):
            raise RuntimeError("cannot render")

    rendered = tool.describe(Unhappy())

    assert "unreprable" in rendered
    assert "Unhappy" in rendered


def test_zero_is_falsy_and_one_is_not():
    assert tool.is_falsy(0) is True
    assert tool.is_falsy(1) is False
    assert tool.is_falsy(True) is False


def test_the_documented_error_is_truthy_and_passes_a_falsy_test():
    """The note the issue asks for, asserted rather than trusted.

    ``-1`` is what the JAB header documents for several of these calls. ``-1`` is truthy,
    so arming a row would let it through -- which means "arm the rows and the bad answers
    become exceptions" is wrong for every symbol whose failure answer is ``-1``.
    """
    assert tool.DOCUMENTED_ERROR == -1
    assert tool.is_falsy(tool.DOCUMENTED_ERROR) is False
    assert "-1 is truthy" in tool.note_on_documented_error()


# ---------------------------------------------------------------------------
# The difference between "falsy" and "not reached"
# ---------------------------------------------------------------------------

def verdict(symbol="getVisibleChildren", raw=1, error=None, candidate=True):
    found = tool.Verdict(symbol, "a probe", candidate=candidate)
    found.raw = raw
    found.error = error
    return found


def test_a_falsy_return_is_named_in_the_summary():
    rows = [verdict(raw=0)]
    assert tool.falsy_summary(rows) == "returned falsy in this run: getVisibleChildren"


def test_no_falsy_return_says_so_in_words():
    rows = [verdict(raw=1), verdict("getVersionInfo", raw=1)]
    assert tool.falsy_summary(rows) == "no candidate symbol returned falsy in this run"


def test_a_symbol_that_was_never_measured_is_not_reported_as_not_falsy():
    """The failure this file exists for.

    A call that raised has no value; counting it as "returned something nonzero" is how a
    partial sweep gets reported as a clean one.
    """
    rows = [verdict(raw=None, error="RuntimeError: boom")]

    assert tool.falsy_summary(rows) == "no candidate symbol returned falsy in this run"
    assert "INCONCLUSIVE" in tool.finding(rows)
    assert "boom" in tool.finding(rows)


def test_the_finding_names_the_call_site_and_what_it_does_with_the_result():
    rows = [verdict("setTextContents", raw=0)]

    found = tool.finding(rows)

    assert "setTextContents" in found
    assert "jabelement.py:1618" in found
    assert "would raise" in found, "the finding has to say what arming would do"


def test_the_finding_for_a_clean_run_says_arming_changes_nothing():
    rows = [verdict(raw=171), verdict("setTextContents", raw=1)]

    found = tool.finding(rows)

    assert "nonzero" in found
    assert "INCONCLUSIVE" not in found


def test_get_visible_children_is_named_once_even_though_it_is_probed_twice():
    """It is measured on the main panel and on the childless painted panel on purpose."""
    rows = [verdict("getVisibleChildren", raw=1), verdict("getVisibleChildren", raw=0)]

    assert tool.falsy_summary(rows) == "returned falsy in this run: getVisibleChildren"


# ---------------------------------------------------------------------------
# The falsy-return control
# ---------------------------------------------------------------------------

def control(raw=0):
    return verdict("getVisibleChildren", raw=raw, candidate=False)


def test_the_childless_panel_is_the_control_and_not_a_candidate():
    """Its falsy return is expected, so it must not be what the summary is reporting.

    Without this, the one probe that is *supposed* to come back falsy would make
    ``getVisibleChildren`` look like a row that cannot be armed -- and the main-panel probe
    that says the opposite would be invisible in the summary.
    """
    rows = [verdict("getVisibleChildren", raw=171), control(raw=0)]

    assert tool.falsy_summary(rows) == "no candidate symbol returned falsy in this run"
    assert tool.control_note(rows).startswith("ok")


def test_a_control_that_did_not_come_back_falsy_makes_the_run_inconclusive(capsys):
    """The confound: "nothing returned 0" is only evidence if something could have."""
    rows = a_full_sweep()
    rows.record(control(raw=1))

    code = tool.report(rows, CONTROL)
    output = capsys.readouterr().out

    assert code == 2
    assert "FAIL the childless panel's getVisibleChildren returned 1 (int), not falsy" \
        in output
    assert "PASSED" not in output


def test_a_control_that_was_reached_and_returned_zero_lets_the_run_pass(capsys):
    rows = a_full_sweep()
    rows.record(control(raw=0))

    assert tool.report(rows, CONTROL) == 0
    assert "falsy as #191 measured" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The element's lifetime: the raw call needs it, so it cannot be released early
# ---------------------------------------------------------------------------

class FakeElement:
    """An element that records whether it has been released."""

    def __init__(self, name="e"):
        self.name = name
        self.released = 0

    def release_jabelement(self, jabelement=None):
        self.released += 1


def test_held_elements_survive_until_they_are_released():
    """The regression that would have measured every symbol falsy.

    The first version released the element inside the drive, and the raw call then ran
    against a released handle -- which JAB answers with an error. Every symbol would have
    come back ``0`` and the run would have argued for arming all fourteen rows.
    """
    ctx = {}
    element = FakeElement()

    assert tool.hold(element, ctx) is element
    assert element.released == 0, "holding must not release"

    tool.release_held(ctx)

    assert element.released == 1
    assert ctx["held"] == [], "a released hold must not be released again"


def test_releasing_twice_releases_once_per_hold():
    ctx = {}
    first, second = FakeElement("a"), FakeElement("b")
    tool.hold(first, ctx)
    tool.hold(second, ctx)

    tool.release_held(ctx)
    tool.release_held(ctx)

    assert (first.released, second.released) == (1, 1)


def test_a_release_that_raises_does_not_stop_the_rest():
    """One bad handle must not leak the others."""
    class Exploding(FakeElement):
        def release_jabelement(self, jabelement=None):
            raise RuntimeError("already gone")

    ctx = {}
    bad, good = Exploding("bad"), FakeElement("good")
    tool.hold(bad, ctx)
    tool.hold(good, ctx)

    tool.release_held(ctx)

    assert good.released == 1


# ---------------------------------------------------------------------------
# The exit code
# ---------------------------------------------------------------------------

CONTROL = ("direct getAccessibleContextInfo on the root element", "ok  1 (int)  nonzero?")


def a_full_sweep(raw=1):
    rows = tool.Rows()
    for symbol in tool.SYMBOLS:
        rows.record(verdict(symbol, raw=raw))
    rows.record(control(raw=0))
    return rows


def test_a_complete_sweep_with_no_falsy_value_passes(capsys):
    assert tool.report(a_full_sweep(), CONTROL) == 0
    output = capsys.readouterr().out
    assert output.strip().endswith(
        "PASSED: every candidate symbol was reached and every direct call returned -- "
        "no candidate symbol returned falsy in this run")


def test_a_complete_sweep_with_a_falsy_value_still_passes_but_says_so(capsys):
    """A falsy return is the answer, not a failure: the tool measures, it does not judge."""
    rows = a_full_sweep()
    rows.verdicts[0].raw = 0

    assert tool.report(rows, CONTROL) == 0
    assert "returned falsy in this run" in capsys.readouterr().out


def test_one_unreached_symbol_makes_the_whole_run_inconclusive(capsys):
    rows = a_full_sweep()
    rows.skip("getAccessibleTableCellInfo",
              "no such component in this application: the table was not found")

    code = tool.report(rows, CONTROL)
    output = capsys.readouterr().out

    assert code == 2
    assert "not reached: no such component in this application" in output
    assert "INCONCLUSIVE" in output
    assert "PASSED" not in output


def test_one_direct_call_that_raised_makes_the_run_inconclusive(capsys):
    rows = a_full_sweep()
    rows.verdicts[3].error = "RuntimeError: the call refused"

    code = tool.report(rows, CONTROL)
    output = capsys.readouterr().out

    assert code == 2
    assert "unmeasured" in output
    assert "PASSED" not in output


def test_a_missing_control_is_inconclusive_rather_than_assumed_fine(capsys):
    """No control cannot be read as a healthy one -- the rule from verify_m0's control."""
    code = tool.report(a_full_sweep(), None)
    output = capsys.readouterr().out

    assert code == 2
    assert "did not even reach the bridge" in output


def test_the_report_writes_the_raw_line_and_the_pyjab_outcome(capsys):
    rows = tool.Rows()
    found = verdict("getVisibleChildren", raw=0)
    found.outcome = "get_visible_children() raised JABException"
    rows.record(found)

    tool.report(rows, CONTROL)
    output = capsys.readouterr().out

    assert "raw getVisibleChildren -> 0 (int)  falsy?" in output
    assert "pyjab path : get_visible_children() raised JABException" in output


def test_a_raw_line_for_a_call_that_raised_shows_the_exception_not_a_value():
    found = verdict(raw=None, error="RuntimeError: Result 0")
    assert found.raw_line() == "raw getVisibleChildren -> raised RuntimeError: Result 0"


# ---------------------------------------------------------------------------
# The recorder: "reached" is observed, not inferred
# ---------------------------------------------------------------------------

class FakeBridge:
    """A bridge stand-in that answers one symbol and records how often it was asked."""

    def __init__(self):
        self.calls = 0

    def getVisibleChildren(self, *args):
        self.calls += 1
        return 1

    def getVisibleChildrenCount(self, *args):
        return 3


def test_the_recorder_counts_the_target_symbol_and_delegates_the_rest():
    real = FakeBridge()
    recorder = tool.Recorder(real, "getVisibleChildren")

    assert recorder.getVisibleChildren(1, 2) == 1
    assert recorder.getVisibleChildrenCount(1, 2) == 3
    assert recorder.hits == 1, "the other symbol must not be counted"
    assert real.calls == 1


def test_a_recorder_that_never_saw_its_symbol_reports_zero():
    recorder = tool.Recorder(FakeBridge(), "getVisibleChildren")

    recorder.getVisibleChildrenCount(1, 2)

    assert recorder.hits == 0


# ---------------------------------------------------------------------------
# The candidate list itself
# ---------------------------------------------------------------------------

def test_every_published_symbol_has_a_driver_and_a_raw_call():
    """A symbol with no probe would be measured as nothing and reported as nothing."""
    for symbol in tool.SYMBOLS:
        assert symbol in tool.DRIVERS, symbol
        assert symbol in tool.RAW, symbol
        assert symbol in tool.CALL_SITES, symbol


def test_the_sweep_is_the_fourteen_symbols_the_issue_lists():
    assert len(tool.SYMBOLS) == 14
    assert set(tool.SYMBOLS) == set(tool.DRIVERS) == set(tool.RAW) == set(tool.CALL_SITES)
    assert [site for site, _what in tool.CALL_SITES.values()].count(
        "jabelement.py:597, jabdriver.py:301") == 1


def test_the_eight_sites_that_ignore_the_result_are_marked_as_such():
    """#195's split: seven sites read the return, eight ignore it.

    The count is asserted because it is what makes arming a per-row decision rather than a
    blanket one -- and because a symbol moved from one group to the other by accident would
    otherwise change the blast radius silently.
    """
    ignoring = [symbol for symbol, (_site, what) in tool.CALL_SITES.items()
                if what == "ignores"]
    reading = [symbol for symbol, (_site, what) in tool.CALL_SITES.items()
               if what == "checks"]

    assert len(ignoring) == 7
    assert len(reading) == 7
    assert set(ignoring) | set(reading) == set(tool.SYMBOLS)


def test_every_widget_the_sweep_names_exists_in_the_test_application():
    """The names come from the Java source, so a rename there breaks this rather than a run."""
    source = (REPO_ROOT / "tests" / "java" / "PyjabTestApp.java").read_text(encoding="utf-8")

    for name in (tool.LABEL_NAME, tool.TEXT_FIELD_NAME, tool.TABLE_NAME, tool.BUTTON_NAME,
                 tool.BUTTON_DISABLER_NAME, tool.BUTTON_ENABLER_NAME,
                 tool.MAIN_PANEL_NAME, tool.PAINTED_NAME):
        assert f'"{name}"' in source, f"{name!r} is not a widget in PyjabTestApp"


# ---------------------------------------------------------------------------
# The process boundary: a child reports a row, and a child that never reports
# ---------------------------------------------------------------------------

def test_a_verdict_survives_the_child_boundary_with_its_value_and_type():
    """The value crosses as JSON; the type is what keeps ``1`` and ``True`` apart."""
    original = verdict("getVersionInfo", raw=1)
    original.raw_type = "int"
    original.outcome = "get_version_info() returned VMVersion='17'"

    restored = tool.verdict_from_wire(tool.child_payload(original))

    assert restored.symbol == "getVersionInfo"
    assert restored.raw == 1
    assert restored.raw_type == "int"
    assert restored.outcome == original.outcome
    assert restored.falsy is False
    assert "1 (int)" in restored.raw_line(), "the type has to reach the printed line"


def test_a_value_that_is_not_json_serialisable_is_carried_as_text():
    """A JAB handle does not survive ``json.dumps``; its description does."""
    original = verdict("getTopLevelObject", raw=object())

    payload = tool.child_payload(original)

    assert isinstance(payload["raw"], str)
    assert tool.verdict_from_wire(payload).raw == payload["raw"]


def test_an_error_crosses_the_boundary_and_stays_unmeasured():
    original = verdict(raw=None, error="RuntimeError: the call refused")

    restored = tool.verdict_from_wire(tool.child_payload(original))

    assert restored.measured is False
    assert restored.error == "RuntimeError: the call refused"
    assert "INCONCLUSIVE" in tool.finding([restored])


def test_a_child_that_never_reports_is_a_gap_in_the_harness_not_a_clean_row(monkeypatch,
                                                                           capsys):
    """The bug the first dispatch found, pinned.

    The whole sweep in one process died inside a JAB call and took the run with it. With
    the parent enforcing the budget, the symbol is reported as unreached and the run says
    ``INCONCLUSIVE`` -- which is a fact, where a fifty-minute hang was nothing.
    """
    class Args:
        title = "PyjabTestApp"
        timeout = 5
        symbol_timeout = 1
        settle = 0

    def never_returns(*_args, **_kwargs):
        raise tool.subprocess.TimeoutExpired(cmd="child", timeout=1)

    monkeypatch.setattr(tool.subprocess, "run", never_returns)

    assert tool.run_child(Args(), symbol="getVersionInfo") is None
    assert "did not return" in capsys.readouterr().out


def test_a_child_whose_output_has_no_json_row_is_reported_with_its_stderr(monkeypatch,
                                                                         capsys):
    class Args:
        title = "PyjabTestApp"
        timeout = 5
        symbol_timeout = 1
        settle = 0

    class Finished:
        returncode = 1
        stdout = "Traceback (most recent call last):\nImportError: no bridge\n"
        stderr = ""

    monkeypatch.setattr(tool.subprocess, "run", lambda *a, **k: Finished())

    assert tool.run_child(Args(), symbol="getVersionInfo") is None
    assert "no JSON row" in capsys.readouterr().out


def test_the_child_argv_names_the_symbol_and_keeps_the_budget(monkeypatch):
    captured = {}

    class Args:
        title = "PyjabTestApp"
        timeout = 7
        symbol_timeout = 11
        settle = 0

    class Finished:
        returncode = 0
        stdout = '{"verdict": {"symbol": "getVersionInfo", "raw": 1}}'
        stderr = ""

    def capture(argv, **kwargs):
        captured["argv"] = argv
        captured["timeout"] = kwargs.get("timeout")
        return Finished()

    monkeypatch.setattr(tool.subprocess, "run", capture)

    payload = tool.run_child(Args(), symbol="getVersionInfo")

    assert payload == {"verdict": {"symbol": "getVersionInfo", "raw": 1}}
    assert "--child" in captured["argv"]
    assert "--symbol" in captured["argv"]
    assert "getVersionInfo" in captured["argv"]
    assert captured["timeout"] == 11


# ---------------------------------------------------------------------------
# Every attribute the tool reads of a pyjab object has to exist
# ---------------------------------------------------------------------------

def test_every_structure_field_the_tool_reads_exists():
    """The first dispatch died on ``info.role_EN_US``.

    ``AccessibleContextInfo`` spells it ``role_en_US``, and the control child raised
    ``AttributeError`` before one symbol had been measured -- the failure arrived as "the
    control child did not report", which is exactly the case a control is there to surface,
    but a whole dispatch was spent getting there.

    Checked against the real ctypes structures rather than a copy of their field names, so a
    structure that gains or renames a field is covered without editing this.
    """
    import ast

    from pyjab.accessibleinfo import AccessibleContextInfo
    from pyjab.accessibleinfo import AccessibleTextInfo
    from pyjab.accessibleinfo import AccessibleTableCellInfo
    from pyjab.accessibleinfo import AccessBridgeVersionInfo
    from pyjab.accessibleinfo import VisibleChildrenInfo

    structures = {
        "AccessibleContextInfo": AccessibleContextInfo,
        "AccessibleTextInfo": AccessibleTextInfo,
        "AccessibleTableCellInfo": AccessibleTableCellInfo,
        "AccessBridgeVersionInfo": AccessBridgeVersionInfo,
        "VisibleChildrenInfo": VisibleChildrenInfo,
    }
    source = (REPO_ROOT / "tools" / "verify_jab_return_values.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Local variables bound to a structure instance, per function.
    instances = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for item in ast.walk(node):
            if (isinstance(item, ast.Assign) and isinstance(item.value, ast.Call)
                    and isinstance(item.value.func, ast.Name)
                    and item.value.func.id in structures):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        instances.setdefault(node.name, {})[target.id] = \
                            item.value.func.id

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
            continue
        where = instances.get(_enclosing_function(tree, node)) or {}
        structure = where.get(node.value.id) or structures.get(node.value.id)
        if structure is None:
            continue
        fields = {name for name, _type in structures[structure]._fields_}
        if node.attr not in fields:
            offenders.append(f"{structure}.{node.attr}")

    assert not offenders, f"the tool reads fields that do not exist: {offenders}"


def _enclosing_function(tree, target):
    """The name of the function a node lives in, or None for module level."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and any(
                child is target for child in ast.walk(node)):
            return node.name
    return None


# ---------------------------------------------------------------------------
# It must not run off Windows
# ---------------------------------------------------------------------------

def test_it_refuses_to_run_off_windows(capsys, monkeypatch):
    """Rather than measuring nothing and reporting it as a result."""
    monkeypatch.setattr(tool.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(sys, "argv", ["verify_jab_return_values.py"])

    assert tool.main() == 2
    assert "needs Windows" in capsys.readouterr().err
