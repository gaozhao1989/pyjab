"""The DPI verifier's own arithmetic, which has been wrong twice.

Both bugs were in reading Windows, not in pyjab:

* the scale came from ``GetDpiForWindow()``, which returns 96 for a DPI-unaware
  window by definition, so the scale was 1.0 on every machine and the scaled
  half of the check never ran;
* the target's awareness was read with a process *id* where the API takes a
  process *handle*, which came back as ``-0x7ff8ffa9`` -- ``0x80070057``,
  ``E_INVALIDARG``.

Neither is reachable from the portable suite as behaviour, because both need
Windows and a live Java application. What is testable is the decoding and the
argument handling, and those are the parts that were wrong.
"""

from __future__ import annotations

import ctypes
import importlib.util
import sys
from pathlib import Path

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_tool():
    """Import tools/verify_dpi.py without running it."""
    spec = importlib.util.spec_from_file_location(
        "verify_dpi_under_test", REPO_ROOT / "tools" / "verify_dpi.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except SystemExit:
        pass  # it exits on non-Windows; the definitions above that are what we want
    return module


tool = load_tool()


def test_it_loads_off_windows():
    """It has to be importable to be testable at all."""
    assert hasattr(tool, "describe_target_dpi")


@pytest.mark.parametrize("hresult, expected", [
    # The value the real run produced, and the reason it looked like a fact about
    # the application rather than a bug in the tool.
    (-0x7ff8ffa9, "0x80070057"),
    (-0x7ff8fffb, "0x80070005"),
    (0, "0x00000000"),
])
def test_the_signed_hresult_is_also_shown_unsigned(hresult, expected):
    assert expected in tool.decode_hresult(hresult)


def test_the_run_that_found_the_bug_decodes_to_invalid_argument():
    """Pinned to the exact string from the 150% run."""
    decoded = tool.decode_hresult(-0x7ff8ffa9)

    assert "0x80070057" in decoded
    assert "facility 7" in decoded
    assert "code 87" in decoded, "87 is ERROR_INVALID_PARAMETER"


def test_a_bad_hresult_sign_extends_correctly():
    """`hresult & 0xFFFFFFFF` rather than a hand-rolled negative branch.

    ctypes hands these back as signed 32-bit ints, and getting the masking wrong
    would report a facility and code belonging to a different error.
    """
    assert "code 5" in tool.decode_hresult(-0x7ff8fffb)


class FakeWindll:
    """Enough of ctypes.windll to exercise describe_target_dpi."""

    def __init__(self, open_returns=1234, hresult=0, awareness=2, last_error=0):
        self.calls = []
        outer = self

        class Kernel32:
            def OpenProcess(self, access, inherit, pid):
                outer.calls.append(("OpenProcess", access, inherit, pid))
                return open_returns

            def CloseHandle(self, handle):
                outer.calls.append(("CloseHandle", handle))
                return True

            def GetLastError(self):
                return last_error

        class Shcore:
            def GetProcessDpiAwareness(self, handle, out):
                outer.calls.append(("GetProcessDpiAwareness", handle))
                if hresult == 0:
                    out._obj.value = awareness
                return hresult

        self.kernel32 = Kernel32()
        self.shcore = Shcore()


@pytest.fixture
def fake_windll(monkeypatch):
    def install(fake):
        monkeypatch.setattr(ctypes, "windll", fake, raising=False)
        monkeypatch.setattr(ctypes, "get_last_error", lambda: 0, raising=False)
        return fake
    return install


def test_it_opens_a_handle_before_asking(fake_windll):
    """The bug, pinned: OpenProcess has to come first, and CloseHandle after.

    Passing the id straight in returned E_INVALIDARG, and the tool reported it as
    though it were a property of the target application.
    """
    fake = fake_windll(FakeWindll(awareness=3))

    facts = tool.describe_target_dpi(4321)

    names = [call[0] for call in fake.calls]
    assert names[0] == "OpenProcess", names
    assert "GetProcessDpiAwareness" in names
    assert names[-1] == "CloseHandle", "the handle has to be closed"
    assert facts["GetProcessDpiAwareness(pid)"] == "PER_MONITOR_AWARE"
    assert facts["_aware"] is True


def test_it_asks_for_limited_information(fake_windll):
    """PROCESS_QUERY_LIMITED_INFORMATION, which works on most targets unelevated."""
    fake = fake_windll(FakeWindll())

    tool.describe_target_dpi(4321)

    open_call = next(c for c in fake.calls if c[0] == "OpenProcess")
    assert open_call[1] == 0x1000


def test_an_unaware_target_is_reported_as_such(fake_windll):
    fake = fake_windll(FakeWindll(awareness=1))

    facts = tool.describe_target_dpi(4321)

    assert facts["_aware"] is False, "this is the case issue #62 describes"


def test_a_failed_open_says_so_rather_than_claiming_a_result(fake_windll):
    """An elevated target cannot be asked; that is not the same as 'unaware'."""
    fake = fake_windll(FakeWindll(open_returns=0))

    facts = tool.describe_target_dpi(4321)

    assert facts["_aware"] is None
    assert "OpenProcess failed" in facts["GetProcessDpiAwareness(pid)"]
    assert not any(call[0] == "CloseHandle" for call in fake.calls)


def test_a_failed_query_names_the_hresult_and_what_it_means(fake_windll):
    fake = fake_windll(FakeWindll(hresult=-0x7ff8ffa9))

    facts = tool.describe_target_dpi(4321)

    assert facts["_aware"] is None
    assert "0x80070057" in facts["GetProcessDpiAwareness(pid)"]
    assert "E_INVALIDARG" in facts["GetProcessDpiAwareness(pid)"]
    assert any(call[0] == "CloseHandle" for call in fake.calls), (
        "a failed query still has to close the handle"
    )


def test_access_denied_is_named_too(fake_windll):
    fake = fake_windll(FakeWindll(hresult=-0x7ff8fffb))

    facts = tool.describe_target_dpi(4321)

    assert "E_ACCESSDENIED" in facts["GetProcessDpiAwareness(pid)"]


def test_the_scale_no_longer_comes_from_the_unaware_reading():
    """The first bug, pinned by reading the source.

    There is no way to assert the arithmetic without Windows, so this asserts the
    thing that was wrong: the scale is taken from the display DPI, not from
    GetDpiForWindow(), which answers 96 for an unaware window by definition.
    """
    source = (REPO_ROOT / "tools" / "verify_dpi.py").read_text(encoding="utf-8")

    assert 'measurement["win32"].get("display DPI"' in source
    assert 'get("GetDpiForWindow()", 96) / 96.0' not in source
    assert "SetThreadDpiAwarenessContext" in source, (
        "an unaware process cannot read a scaled display without switching context"
    )
    assert "GetThreadDpiAwarenessContext" in source, "and it has to switch back"
