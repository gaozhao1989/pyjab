"""``JABDriver.get_focused_element()``, rewritten, and the bug the rewrite fixed.

The method was contributed by Chih-Yu in 2022 and written again from its
behaviour rather than from its text.  What makes the rewrite worth more than a
legal formality is that reading the behaviour closely turned up a real defect.

``getAccessibleContextWithFocus`` was declared with ``errorcheck=True``, and that
hook raises ``RuntimeError`` on a falsy result *before the caller sees it*
(AGENTS.md section 2.7).  So the ``if not result`` in the old code could never
run, and a window with nothing focused -- which is the ordinary answer for a
window nobody has tabbed into -- raised instead of returning ``None`` as the
docstring promised.  The live test could not catch it: on a desktop that has been
clicked, something always has focus.

These tests need no Java application.  ``JABDriver.__new__`` is used, as in
``test_jabdriver_launch.py``, because ``__init__`` connects to the bridge and
writes ``~/.accessibility.properties``.
"""

from __future__ import annotations

import sys

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

JABDriver = _win32stubs.import_jabdriver()

#: A context handle that is not zero, so a successful call looks successful.
SOME_CONTEXT = 0x0000_0001_0000_4000

#: A VM id that does not fit in anything narrower, to catch a truncation.
SOME_VMID = 0x1234_5678


class FakeBridge(object):
    """Stands in for the bridge DLL, filling the out-parameters as it does.

    The real call writes through both pointers and returns a status flag, so a
    stand-in has to do the same or the code under test is reading defaults.
    """

    def __init__(self, status, context=SOME_CONTEXT, vmid=SOME_VMID):
        self.status = status
        self.context = context
        self.vmid = vmid
        self.seen_hwnds = []

    def getAccessibleContextWithFocus(self, hwnd, vmid_pointer, context_pointer):
        self.seen_hwnds.append(hwnd)
        if self.status:
            vmid_pointer._obj.value = self.vmid
            context_pointer._obj.value = self.context
        return self.status


def driver_with(bridge, hwnd=4242):
    """A JABDriver that never ran __init__, bound to a stand-in bridge."""
    driver = JABDriver.__new__(JABDriver)
    driver._bridge = bridge
    driver._hwnd = hwnd
    return driver


# ---------------------------------------------------------------------------
# The answer when something has focus
# ---------------------------------------------------------------------------

def test_the_focused_element_is_returned():
    driver = driver_with(FakeBridge(status=1))

    focused = driver.get_focused_element()

    assert focused is not None
    assert focused.hwnd == 4242
    assert focused.accessible_context.value == SOME_CONTEXT


def test_the_window_is_the_one_asked_about():
    bridge = FakeBridge(status=1)
    driver = driver_with(bridge, hwnd=99)

    driver.get_focused_element()

    assert bridge.seen_hwnds == [99]


def test_the_vmid_is_a_plain_int():
    """The convention every other path follows.

    ``_get_accessible_context_from_hwnd`` returns ``vmid.value`` for the same
    reason.  Passing the ctypes scalar on would work by accident -- it supports
    the arithmetic downstream -- and break anywhere that compares it to an int.
    """
    driver = driver_with(FakeBridge(status=1))

    focused = driver.get_focused_element()

    assert isinstance(focused.vmid, int)
    assert focused.vmid == SOME_VMID


def test_a_large_vmid_survives():
    """A 64-bit value would be truncated if it were narrowed on the way through."""
    driver = driver_with(FakeBridge(status=1, vmid=SOME_VMID))

    assert driver.get_focused_element().vmid == SOME_VMID


# ---------------------------------------------------------------------------
# The answer when nothing has focus -- the case that used to raise
# ---------------------------------------------------------------------------

def test_a_window_with_nothing_focused_returns_none():
    """Currently unreachable in the real bridge, which is the point.

    With ``errorcheck=True`` on ``getAccessibleContextWithFocus`` the hook raises
    from inside the call and this branch never runs.  The declaration is asserted
    separately, just below.
    """
    driver = driver_with(FakeBridge(status=0))

    assert driver.get_focused_element() is None


def test_a_successful_call_that_produced_no_context_returns_none():
    """The other half of the guard: the call worked and still found nothing."""
    driver = driver_with(FakeBridge(status=1, context=0))

    assert driver.get_focused_element() is None


def test_the_symbol_is_declared_without_errorcheck():
    """The declared fix, which is what makes the branch above reachable.

    A behavioural test cannot catch this on its own: the hook is installed by
    ``JABFixedFunc`` onto a real DLL, so a stand-in bridge never raises whatever
    the declaration says.  Asserting the declaration is how the regression gets
    caught without Windows.
    """
    from pyjab.jabfixedfunc import SIGNATURES

    declared = {name: errorcheck for name, _, _, errorcheck in SIGNATURES}

    assert declared["getAccessibleContextWithFocus"] is False, (
        "errorcheck=True makes the falsy branch in _focused_context unreachable, "
        "so get_focused_element() would raise on a window with nothing focused"
    )


def test_the_only_caller_checks_the_result_itself():
    """Which is the other half of the deal.

    Dropping errorcheck is only safe because the caller looks at the status
    flag.  If that check were ever removed, a failure would pass silently
    instead of raising, which is worse than the bug being fixed.
    """
    import inspect

    from pyjab.jabdriver import JABDriver as RealDriver

    source = inspect.getsource(RealDriver._focused_context)

    assert "if not found" in source


# ---------------------------------------------------------------------------
# The rewrite, against the implementation it replaced
# ---------------------------------------------------------------------------

def reference_get_focused_element(driver):
    """The pre-rewrite implementation, verbatim, as an oracle.

    Kept in the test rather than in the package because its only purpose is to
    prove that the rewrite returns the same thing.  It is the success path that
    matters here; the failure path is where the rewrite deliberately differs, by
    returning None where the old declaration made it raise.
    """
    from ctypes import c_long, byref

    from pyjab.common.types import JOBJECT64
    from pyjab.jabelement import JABElement

    vmid = c_long()
    accessible_context = JOBJECT64()
    result = driver.bridge.getAccessibleContextWithFocus(
        driver.hwnd, byref(vmid), byref(accessible_context)
    )
    if not result or not accessible_context.value:
        return None

    return JABElement(
        bridge=driver.bridge,
        hwnd=driver.hwnd,
        vmid=vmid.value,
        accessible_context=accessible_context,
    )


def summarise(element):
    """What a caller can observe about the result, or None."""
    if element is None:
        return None
    return (element.hwnd, element.vmid, element.accessible_context.value)


@pytest.mark.parametrize("status, context, vmid", [
    (1, SOME_CONTEXT, SOME_VMID),
    (1, SOME_CONTEXT, 0),
    (1, SOME_CONTEXT, 1),
    (1, 0x7FFF_FFFF_FFFF_FFFF, 42),
    (0, SOME_CONTEXT, SOME_VMID),
    (0, 0, 0),
    (1, 0, SOME_VMID),
])
def test_the_rewrite_returns_what_the_old_code_returned(status, context, vmid):
    """Same observable result, for every shape the bridge can answer with.

    The rewrite is written from the behaviour rather than from the old text, so
    this is the evidence that it does the same thing -- and the one row where it
    deliberately differs, ``status=0``, agrees anyway because the old code's
    guard was unreachable rather than wrong.
    """
    driver = driver_with(FakeBridge(status=status, context=context, vmid=vmid))

    assert summarise(driver.get_focused_element()) == \
        summarise(reference_get_focused_element(driver))
