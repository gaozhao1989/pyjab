"""Bringing a window forward, and saying whether it worked.

Issue #180: `send_keys`'s own docstring told callers to bring the window forward first, and
there was no public way to do it. The twelve call sites of `_set_window_foreground` were all
inside `jabelement.py`.

The interesting assertion is not that the method calls `SetForegroundWindow` — it is that it
**reports what happened**, because Windows refuses foreground activation from a service
session and that refusal is a normal outcome rather than an error (#68).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import _win32stubs  # noqa: F401

from pyjab.common.win32utils import Win32Utils

Win32UtilsClass = Win32Utils.__wrapped__
JABElement = _win32stubs.import_jabelement()


def a_utils(foreground_after):
    """A Win32Utils whose foreground window read-back returns a scripted value."""
    utils = Win32Utils()
    reads = iter(foreground_after)

    def read():
        return next(reads, foreground_after[-1])

    return utils, read


def test_it_says_true_when_the_window_ends_up_in_front():
    utils, read = a_utils([None, 4321])

    with patch.object(Win32UtilsClass, "_get_foreground_window", staticmethod(read)), \
         patch("win32gui.SetForegroundWindow"), \
         patch("win32com.client.Dispatch"):
        assert utils.set_window_foreground(4321) is True


def test_it_says_false_when_windows_refuses():
    """The documented outcome in a service session, and it must not raise.

    `SetForegroundWindow` returns nothing useful and pywin32 raises rather than reporting a
    status, so the only honest answer is the state left behind.
    """
    utils, read = a_utils([None, 9999])

    with patch.object(Win32UtilsClass, "_get_foreground_window", staticmethod(read)), \
         patch("win32gui.SetForegroundWindow"), \
         patch("win32com.client.Dispatch"):
        assert utils.set_window_foreground(4321) is False


def test_a_refusal_does_not_propagate_as_an_exception():
    """If the caller has to catch, returning a bool was pointless."""
    utils, read = a_utils([None, 9999])

    with patch.object(Win32UtilsClass, "_get_foreground_window", staticmethod(read)), \
         patch("win32gui.SetForegroundWindow", side_effect=RuntimeError("refused")), \
         patch("win32com.client.Dispatch"):
        assert utils.set_window_foreground(4321) is False


def test_a_window_already_in_front_costs_nothing():
    """No keystroke, and it must not send one.

    The space bar is sent to take the foreground, and a space bar goes to whatever has focus
    -- so sending it when the window is already in front is a stray keystroke in somebody
    else's application for no reason.
    """
    utils, read = a_utils([4321])

    with patch.object(Win32UtilsClass, "_get_foreground_window", staticmethod(read)), \
         patch("win32com.client.Dispatch") as shell, \
         patch("win32gui.SetForegroundWindow") as setter:
        assert utils.set_window_foreground(4321) is True

    assert not shell.called, "a keystroke was sent to a window that was already in front"
    assert not setter.called


def test_the_private_name_still_works_for_its_twelve_callers():
    """It is kept, and delegates. Removing it would be a change to internals for no gain."""
    utils, read = a_utils([4321])

    with patch.object(Win32UtilsClass, "_get_foreground_window", staticmethod(read)), \
         patch("win32com.client.Dispatch"), \
         patch("win32gui.SetForegroundWindow"):
        assert utils._set_window_foreground(4321) is None


def test_the_driver_and_the_element_both_expose_it():
    """An element is what a caller has in hand after a lookup; the driver is the entry point."""
    from tests._fakejab import bind, node

    assert hasattr(JABElement, "focus")
    element, _bridge = bind(node("frame", name="app"))
    assert callable(element.focus)
