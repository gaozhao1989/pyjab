"""What the #195 return-value sweep can be checked for without Windows.

The measurement needs a JVM, a JAB bridge and a desktop, none of which exist here.  What
does exist anywhere is the machinery that decides what the sweep may claim: the recorder
that reads the raw return, the watchdog that keeps one hung call from costing the run, the
line between **"returned falsy"** and **"never reached"**, and -- the one that turned out to
matter -- **whether the target JVM was still alive**.  An earlier dispatch's artifacts show
the target dying with ``EXCEPTION_ACCESS_VIOLATION`` about 13s in, which is what a harness
"cannot drive the application" looks like from the inside.

Everything is driven through a fake driver, a fake bridge and a fake ``hs_err`` log, so this
runs in the portable suite.  Nothing here reaches a real JAB symbol; ``pyjab.jabelement`` and
``pyjab.jabdriver`` refuse to import off Windows, so the tool reaches them lazily and this
module installs fakes.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def load():
    """verify_jab_return_values by path: tools/ is not a package."""
    spec = importlib.util.spec_from_file_location(
        "verify_jab_return_values", REPO_ROOT / "tools" / "verify_jab_return_values.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_jab_return_values"] = module
    spec.loader.exec_module(module)
    return module


tool = load()


class FakeBridge:
    """Every JAB symbol, answering from one dict, with a default for the rest."""

    def __init__(self, returns=None, default=1):
        self.returns, self.default, self.calls = returns or {}, default, []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append(name)
            return self.returns.get(name, self.default)
        return call


class FakeElement:
    """The element surface the drives touch.

    ``name`` is a **property that makes the bridge call**, because that is what the real
    ``JABElement.name`` does and it is the call being measured.  An attribute would let a row
    pass while the recorder saw nothing, which is the failure ``measure`` catches with its
    ``hits < 1`` check.

    The constructor signature matches ``JABElement.__init__`` positionally: the tool's
    ``install_wrapping`` passes all four arguments through by position.
    """

    def __init__(self, bridge=None, hwnd=None, vmid=None, accessible_context=None,
                 label="an element"):
        self._bridge, self._label, self.released = bridge, label, 0

    @property
    def bridge(self):
        return self._bridge

    @bridge.setter
    def bridge(self, value):
        self._bridge = value

    @property
    def name(self):
        return self.bridge.getAccessibleContextInfo(self.vmid, 1)

    @property
    def vmid(self):
        return 1

    def release_jabelement(self):
        self.released += 1

    def send_text(self, value, **kwargs):
        return self.bridge.setTextContents(1, 1, value)

    def get_cell(self, row, column):
        return FakeElement(self.bridge)

    def children(self):
        return iter([FakeElement(self.bridge)])

    def get_visible_children(self):
        return [FakeElement(self.bridge)]

    def _get_top_level_object(self):
        return self.bridge.getTopLevelObject(1, 1)


class FakeJABDriver:
    """The driver surface the two binding rows need."""

    def __init__(self, **kwargs):
        self.kwargs, self.hwnd, self.vmid, self.detached = kwargs, 4242, 1, False

    def detach(self):
        self.detached = True


@pytest.fixture(autouse=True)
def fake_pyjab(monkeypatch):
    """Install fake ``pyjab.jabelement`` and ``pyjab.jabdriver`` for the whole module.

    Autouse because the tool imports ``JABElement`` lazily inside ``install_wrapping`` and
    ``JABDriver`` inside two drives, and the real ones raise ``ImportError`` off Windows.
    """
    jabelement = types.ModuleType("pyjab.jabelement")
    jabelement.JABElement = FakeElement
    jabdriver = types.ModuleType("pyjab.jabdriver")
    jabdriver.JABDriver = FakeJABDriver
    monkeypatch.setitem(sys.modules, "pyjab.jabelement", jabelement)
    monkeypatch.setitem(sys.modules, "pyjab.jabdriver", jabdriver)
    tool.install_wrapping()
    yield
    tool.ACTIVE = None


class FakeJab:
    """A bound JABDriver: the recorder is whichever bridge is installed on it."""

    def __init__(self, bridge, title="PyjabTestApp-1"):
        self._bridge, self.title, self.vmid, self.accessible_context = bridge, title, 1, 1
        self.detached = False
        self.root_element = FakeElement(bridge)
        self.root_element._label = "the window"

    @property
    def bridge(self):
        return self._bridge

    @bridge.setter
    def bridge(self, value):
        self._bridge = value

    def find_element_by_name(self, name):
        element = FakeElement(self.bridge)
        element._label = name
        return element

    def get_java_window_hwnd(self, title):
        return 4242

    def get_version_info(self):
        return {"VMVersion": "17"}

    def detach(self):
        self.detached = True


# ---------------------------------------------------------------------------
# The recorder: "reached" is observed, not inferred
# ---------------------------------------------------------------------------

def test_the_recorder_records_the_target_it_was_asked_for():
    recorder = tool.Recorder(FakeBridge({"getVisibleChildren": 0}), "getVisibleChildren")

    assert recorder.getVisibleChildren(1, 2) == 0
    assert (recorder.hits, recorder.result, recorder.falsy) == (1, 0, True)


def test_the_recorder_hands_every_other_symbol_through_uncounted():
    real = FakeBridge()
    recorder = tool.Recorder(real, "getVisibleChildren")

    assert recorder.getVersionInfo(1) == 1
    assert recorder.hits == 0, "another symbol must not count as a hit"
    assert real.calls == ["getVersionInfo"]


def test_a_symbol_that_never_arrived_is_none_rather_than_falsy():
    """``None`` until a call arrives, so "never asked" is not read as "answered 0"."""
    recorder = tool.Recorder(FakeBridge(), "getVisibleChildren")

    assert (recorder.hits, recorder.result, recorder.falsy) == (0, None, False)


def test_the_recorder_keeps_the_error_and_still_raises():
    class Refusing(FakeBridge):
        def getVisibleChildren(self, *args):
            raise RuntimeError("Result 0")

    recorder = tool.Recorder(Refusing(), "getVisibleChildren")

    with pytest.raises(RuntimeError, match="Result 0"):
        recorder.getVisibleChildren(1, 2)

    assert "Result 0" in recorder.error


# ---------------------------------------------------------------------------
# The watchdog: one hung call must cost one row, not the run
# ---------------------------------------------------------------------------

def test_a_drive_that_returns_reports_where_it_went():
    assert tool.watchdog(lambda ctx: "read .name", {}, 1.0) == ("read .name", None)


def test_a_drive_that_raises_reports_the_exception():
    def refuse(ctx):
        raise RuntimeError("no such component")

    where, problem = tool.watchdog(refuse, {}, 1.0)

    assert where is None
    assert "RuntimeError: no such component" in problem


def test_a_drive_that_never_returns_is_abandoned_with_its_deadline():
    where, problem = tool.watchdog(lambda ctx: __import__("time").sleep(30), {}, 0.1)

    assert where is None
    assert "no return from the drive within 0.1s" in problem


# ---------------------------------------------------------------------------
# One symbol, measured
# ---------------------------------------------------------------------------

def test_the_bridge_in_force_is_what_a_new_element_takes():
    """``find_element_by_name`` builds its own element, so the wrapper has to reach it."""
    recorder = tool.Recorder(FakeBridge(), "getVersionInfo")
    tool.ACTIVE = recorder

    assert FakeElement(bridge=FakeBridge()).bridge is recorder


def test_the_fake_element_name_really_goes_through_the_bridge():
    """The guard on the guard: a plain attribute would make every row below pass vacuously."""
    bridge = FakeBridge({"getAccessibleContextInfo": 7})

    assert FakeElement(bridge).name == 7
    assert bridge.calls == ["getAccessibleContextInfo"]


def test_a_measured_symbol_carries_its_raw_return_and_truthiness():
    row = tool.measure(FakeJab(FakeBridge({"getAccessibleContextInfo": 1})),
                       "getAccessibleContextInfo", 5.0)

    assert (row["symbol"], row["site"]) == ("getAccessibleContextInfo", "jabelement.py:632")
    assert (row["raw"], row["falsy"], row["reason"]) == (1, False, None)
    assert row["outcome"], "the report has to say how it was reached"


def test_a_falsy_raw_return_is_what_the_row_says():
    row = tool.measure(FakeJab(FakeBridge({"getAccessibleContextInfo": 0})),
                       "getAccessibleContextInfo", 5.0)

    assert row["falsy"] is True


def test_the_real_bridge_is_restored_after_a_measurement():
    """A row must not leave the recorder installed on the driver."""
    real = FakeBridge()
    jab = FakeJab(real)

    tool.measure(jab, "getVersionInfo", 5.0)

    assert jab.bridge is real
    assert jab.root_element.bridge is real


def _refuser(ctx):
    raise RuntimeError("deliberately broken")


def test_a_drive_that_raises_is_not_reached_with_the_exception(monkeypatch):
    monkeypatch.setitem(tool.DRIVES, "getVersionInfo", _refuser)

    row = tool.measure(FakeJab(FakeBridge()), "getVersionInfo", 5.0)

    assert row["raw"] is None and row["falsy"] is None
    assert row["reason"].startswith("not reached: the harness could not drive it")
    assert "deliberately broken" in row["reason"]


def test_a_drive_whose_symbol_never_reached_the_bridge_is_not_reached():
    """The reach claim is observed: a drive that ran but made no such call is not a row."""
    row = tool.measure(FakeJab(FakeBridge()), "getVersionInfo", 5.0)

    assert row["falsy"] is None
    assert "no call to getVersionInfo was observed" in row["reason"]


def test_a_hung_drive_is_one_not_reached_row(monkeypatch):
    monkeypatch.setitem(tool.DRIVES, "getVersionInfo",
                        lambda ctx: __import__("time").sleep(30))

    row = tool.measure(FakeJab(FakeBridge()), "getVersionInfo", 0.1)

    assert "no return from the drive" in row["reason"]


def test_every_symbol_has_a_drive_and_a_call_site():
    """A symbol with no drive would be measured as nothing and reported as nothing."""
    assert set(tool.SYMBOLS) == set(tool.DRIVES) == set(tool.SITES)
    assert len(tool.SYMBOLS) == 14


def test_every_widget_the_sweep_names_exists_in_the_test_application():
    """The names come from the Java source, so a rename there breaks this, not a dispatch."""
    source = (REPO_ROOT / "tests" / "java" / "PyjabTestApp.java").read_text(encoding="utf-8")

    for name in (tool.LABEL, tool.FIELD, tool.TABLE, tool.BUTTON):
        assert f'"{name}"' in source, f"{name!r} is not a widget in PyjabTestApp"


def test_the_seven_sites_that_ignore_the_result_are_marked_as_such():
    """#195's split decides the blast radius, so it is asserted rather than assumed."""
    ignoring = [symbol for symbol, (_site, what, _why) in tool.SITES.items()
                if what == "ignores"]

    assert len(ignoring) == 7
    assert "getVersionInfo" in ignoring and "getAccessibleContextInfo" not in ignoring


def test_the_drives_reach_the_driver_through_a_context_not_a_name():
    """``driver.<private>`` would fail ``tools/check_documented_api.py``; a dict does not."""
    source = (REPO_ROOT / "tools" / "verify_jab_return_values.py").read_text(encoding="utf-8")

    assert "driver._" not in source


# ---------------------------------------------------------------------------
# The control, and the report
# ---------------------------------------------------------------------------

def test_the_control_reads_the_root_and_records_its_raw_call():
    row = tool.control(FakeJab(FakeBridge({"getAccessibleContextInfo": 1})), 5.0)

    assert (row["raw"], row["falsy"], row["reason"]) == (1, False, None)


def test_a_falsy_control_is_a_falsy_control():
    row = tool.control(FakeJab(FakeBridge({"getAccessibleContextInfo": 0})), 5.0)

    assert row["falsy"] is True


def rows_for(falsy_symbol=None, unreached_symbol=None, control_raw=1):
    rows = []
    for symbol in tool.SYMBOLS:
        bad, gone = symbol == falsy_symbol, symbol == unreached_symbol
        rows.append(dict(symbol=symbol, site=tool.SITES[symbol][0], expects="checks",
                         reached_by=tool.SITES[symbol][2],
                         raw=None if gone else (0 if bad else 1), type="int",
                         falsy=None if gone else bad, outcome=None,
                         reason="not reached: no such component" if gone else None))
    control = {"raw": control_raw, "type": "int", "falsy": not control_raw, "reason": None}
    return rows, control


def test_a_complete_sweep_passes_and_says_every_symbol_was_read(capsys):
    rows, row_control = rows_for()

    assert tool.report(rows, row_control) == 0
    output = capsys.readouterr().out

    assert "PASSED: every one of the 14 symbols" in output
    assert "none returned falsy" in output
    for symbol in tool.SYMBOLS:
        assert f"  {symbol}: " in output


def test_a_falsy_return_is_reported_and_named(capsys):
    """A falsy return is the answer, not a failure: the tool measures, it does not judge."""
    rows, row_control = rows_for(falsy_symbol="setTextContents")

    assert tool.report(rows, row_control) == 0
    output = capsys.readouterr().out

    assert "raw setTextContents -> 0 (int)  falsy?" in output
    assert "FINDING: 1 symbol(s) return falsy" in output
    assert "falsy: setTextContents" in output


def test_an_unreached_symbol_makes_the_run_inconclusive(capsys):
    rows, row_control = rows_for(unreached_symbol="getVisibleChildren")

    code = tool.report(rows, row_control)
    output = capsys.readouterr().out

    assert code == 2
    assert "not reached: getVisibleChildren -> not reached: no such component" in output
    assert "INCONCLUSIVE" in output
    assert "PASSED" not in output


def test_a_control_that_did_not_come_back_truthy_makes_the_run_inconclusive(capsys):
    rows, row_control = rows_for(control_raw=0)

    assert tool.report(rows, row_control) == 2
    output = capsys.readouterr().out

    assert "FALSY -- so nothing below it is a measurement" in output
    assert "PASSED" not in output


def test_a_missing_control_is_inconclusive_rather_than_assumed_fine(capsys):
    rows, _row_control = rows_for()

    assert tool.report(rows, {"raw": None, "type": None, "falsy": None,
                              "reason": "not reached: reading root_element.name"}) == 2
    assert "FAIL" in capsys.readouterr().out


def test_the_note_says_minus_one_is_truthy():
    """The finding this tool must not lose: arming cannot catch a documented ``-1``."""
    assert tool.DOCUMENTED_ERROR == -1
    assert bool(tool.DOCUMENTED_ERROR) is True, "-1 is truthy, which is the whole point"
    assert "-1 is truthy" in tool.note_on_documented_error()
    assert "not made safe by arming it" in tool.note_on_documented_error()


# ---------------------------------------------------------------------------
# The target JVM died: that is the finding, so it goes in the summary
# ---------------------------------------------------------------------------

HS_ERR = """\
# A fatal error has been detected by the Java Runtime Environment:
#
#  EXCEPTION_ACCESS_VIOLATION (0xc0000005) at pc=0x00007ffb2c4d1f10, pid=2764, tid=9312
#
# JRE version: OpenJDK Runtime Environment Temurin-17.0.20.1+1 (17.0.20.1+1)
# Problematic frame:
# V  [jvm.dll+0x2c1f10]
#
# Core dump will be written. Default location: C:\\Users\\runneradmin\\hs_err_pid2764.mdmp
"""


def write_hs_err(tmp_path, body=HS_ERR):
    log = tmp_path / "hs_err_pid2764.log"
    log.write_text(body, encoding="utf-8")
    return log


def test_the_crash_log_is_parsed_for_the_signal_and_the_frame(tmp_path):
    write_hs_err(tmp_path)

    found = tool.hs_err(tmp_path)

    assert found["path"].endswith("hs_err_pid2764.log")
    assert "EXCEPTION_ACCESS_VIOLATION" in found["signal"]
    assert "0xc0000005" in found["signal"]
    assert "jvm.dll" in found["frame"]


def test_a_truncated_crash_log_still_gives_up_what_it_has(tmp_path):
    """The writer may die mid-file; a partial log is still the only evidence there is."""
    write_hs_err(tmp_path, "#  EXCEPTION_ACCESS_VIOLATION (0xc0000005)\n")

    found = tool.hs_err(tmp_path)

    assert "EXCEPTION_ACCESS_VIOLATION" in found["signal"]
    assert found["frame"] == ""


def test_no_crash_log_is_no_crash(tmp_path):
    assert tool.hs_err(tmp_path) is None


def test_new_hs_errs_names_the_logs_so_a_stale_one_is_not_a_crash(tmp_path):
    write_hs_err(tmp_path)

    assert tool.new_hs_errs(tmp_path) == ["hs_err_pid2764.log"]


def test_a_dead_target_is_reported_as_the_reason_the_run_is_inconclusive(capsys):
    rows, row_control = rows_for(unreached_symbol="getVisibleChildren")
    crash = {"path": "hs_err_pid2764.log", "signal": "EXCEPTION_ACCESS_VIOLATION "
             "(0xc0000005)", "frame": "V  [jvm.dll+0x2c1f10]"}

    code = tool.report(rows, row_control, crash=crash)
    output = capsys.readouterr().out

    assert code == 2
    assert "JVM crash -- died with EXCEPTION_ACCESS_VIOLATION (0xc0000005)" in output
    assert "jvm.dll+0x2c1f10" in output
    assert "hs_err_pid2764.log" in output
    assert "INCONCLUSIVE" in output


def test_a_dead_target_outranks_a_row_that_would_otherwise_have_passed(capsys):
    """A crash with no unreached row is still not a pass: the JVM was going away."""
    rows, row_control = rows_for()

    code = tool.report(rows, row_control,
                       crash={"path": "hs_err_pid1.log", "signal": "SIGSEGV", "frame": ""})

    assert code == 2
    assert "died with SIGSEGV" in capsys.readouterr().out


def test_a_live_target_says_so_in_the_summary(capsys):
    rows, row_control = rows_for()

    assert tool.report(rows, row_control, crash=None) == 0
    assert "JVM: alive at the end of the sweep" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# It must not run off Windows
# ---------------------------------------------------------------------------

def test_it_refuses_to_run_off_windows(capsys, monkeypatch):
    """Rather than measuring nothing and reporting it as a result."""
    monkeypatch.setattr(tool.sys, "platform", "darwin")
    monkeypatch.setattr(sys, "argv", ["verify_jab_return_values.py"])

    assert tool.main() == 2
    assert "needs Windows" in capsys.readouterr().err
