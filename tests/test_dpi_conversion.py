"""Converting JAB's point into the point the mouse API wants -- issue #62.

Measured on a real 150% display with an unaware target:

    calling thread unaware   clicking (278, 109)   -> landed
    calling thread aware     clicking (278, 109)   -> nothing happened
    calling thread aware     clicking (417, 164)   -> landed

417 is 278 x 1.5. So the rule is to convert only when the caller and the target
are in different spaces, and these tests are that table.

Nothing here can click anything: what is tested is which point gets handed to
``SetCursorPos``, for each combination of the two awarenesses.
"""

from __future__ import annotations

import sys

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

from pyjab.common import win32utils


@pytest.fixture
def dpi(monkeypatch):
    """Set the three readings physical_point consults, and return the setter."""
    state = {"scale": 1.0, "caller": False, "target": False}

    monkeypatch.setattr(win32utils, "display_scale", lambda hwnd: state["scale"])
    monkeypatch.setattr(win32utils, "thread_dpi_aware", lambda: state["caller"])
    monkeypatch.setattr(win32utils, "target_dpi_aware", lambda hwnd: state["target"])
    return state


def test_150_percent_unaware_caller_unaware_target_is_unchanged(dpi):
    """The measured working case, and the default one.

    Both ends are in the same virtualised space, so the logical point JAB reports
    is the logical point SetCursorPos wants. Converting here would break it.
    """
    dpi.update(scale=1.5, caller=False, target=False)

    assert win32utils.physical_point(278, 109, hwnd=1) == (278, 109)


def test_150_percent_aware_caller_unaware_target_is_scaled_up(dpi):
    """The measured failing case: this is the fix.

    An aware caller has its mouse coordinates taken as physical; the target's are
    logical. 278 x 1.5 is 417, which is the point that landed.
    """
    dpi.update(scale=1.5, caller=True, target=False)

    assert win32utils.physical_point(278, 109, hwnd=1) == (417, 164)


def test_150_percent_unaware_caller_aware_target_is_scaled_down(dpi):
    """The other mixed case, which the measurement did not cover.

    Here JAB reports physical coordinates and the caller's mouse is virtualised, so
    Windows would scale the point up again. Handing it the physical value
    overshoots; the logical one is what it wants.
    """
    dpi.update(scale=1.5, caller=False, target=True)

    assert win32utils.physical_point(417, 164, hwnd=1) == (278, 109)


def test_both_aware_is_unchanged(dpi):
    """Both physical, so both already agree."""
    dpi.update(scale=1.5, caller=True, target=True)

    assert win32utils.physical_point(417, 164, hwnd=1) == (417, 164)


def test_a_100_percent_display_is_never_converted(dpi):
    """No scaling means no difference to reconcile, whatever the awarenesses are."""
    for caller in (True, False):
        for target in (True, False):
            dpi.update(scale=1.0, caller=caller, target=target)
            assert win32utils.physical_point(278, 109, hwnd=1) == (278, 109)


def test_an_unknown_target_leaves_the_point_alone(dpi):
    """An elevated target cannot be opened, and that is not 'unaware'.

    Guessing there would move the cursor on a setup that works, which is the one
    outcome worth avoiding: the failure is silent and in the opposite direction.
    """
    dpi.update(scale=1.5, caller=True, target=None)

    assert win32utils.physical_point(278, 109, hwnd=1) == (278, 109)


def test_an_unknown_caller_leaves_the_point_alone(dpi):
    dpi.update(scale=1.5, caller=None, target=False)

    assert win32utils.physical_point(278, 109, hwnd=1) == (278, 109)


def test_it_returns_integers(dpi):
    """SetCursorPos takes integers, and 109 x 1.5 wants a decision either way."""
    dpi.update(scale=1.5, caller=True, target=False)

    x, y = win32utils.physical_point(101, 101, hwnd=1)

    assert isinstance(x, int) and isinstance(y, int)
    assert (x, y) == (152, 152), "round, not truncate: 151.5 -> 152"


def test_a_125_percent_display_works_the_same(dpi):
    """120 DPI, the other common scaling."""
    dpi.update(scale=1.25, caller=True, target=False)

    assert win32utils.physical_point(400, 200, hwnd=1) == (500, 250)


def test_the_element_converts_before_it_clicks():
    """The wiring: a click on an element converts before it moves the mouse.

    Patched with `with` blocks rather than the fixture, because Win32Utils is a
    @singleton: an attribute left on that one instance shadows the class, so a
    later test that patches the class sees its patch ignored. That is exactly what
    happened -- three scroll tests failed with `_click_mouse` never called -- and
    scoping the patches to the block is the fix.
    """
    from unittest.mock import patch

    from tests._fakejab import bind, node

    JABElement = _win32stubs.import_jabelement()
    element, _ = bind(node("frame", node("push button", name="OK"), name="app"))
    clicked = []

    with patch.object(JABElement, "_click_point", lambda self: (10, 20)), \
         patch.object(JABElement, "_physical_point",
                      lambda self, x, y: (clicked.append((x, y)) or (x + 1, y + 1))), \
         patch.object(element.win32_utils, "_set_window_foreground",
                      lambda hwnd=None: None), \
         patch.object(element.win32_utils, "_click_mouse",
                      lambda x, y, hold=0, button="left": clicked.append((x, y))):
        element.click(simulate=True)

    assert clicked[0] == (10, 20), "converted first"
    assert clicked[1] == (11, 21), "and the converted point is what is clicked"


def test_nothing_in_the_package_calls_the_mouse_helpers_directly():
    """No call site may skip the conversion.

    Reading the source, because a call site added later is the failure this guards
    and there is no way to notice it from behaviour until someone runs at 150%.
    """
    import ast
    import pathlib

    source = pathlib.Path(
        __import__("pyjab.jabelement", fromlist=["x"]).__file__
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Every function that moves the mouse has to mention _physical_point somewhere
    # in its body. Checking the arguments themselves needs dataflow -- two of the
    # sites convert on the previous line into named locals and one passes the tuple
    # through -- and a dataflow-free approximation that catches "a new function
    # moves the mouse and never converts" is the case worth having.
    def calls(node, name):
        return any(
            isinstance(child, ast.Call)
            and getattr(child.func, "attr", None) == name
            for child in ast.walk(node)
        )

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not (calls(node, "_click_mouse") or calls(node, "_double_click_mouse")):
            continue
        if calls(node, "_physical_point"):
            continue
        offenders.append((node.lineno, node.name))

    assert not offenders, (
        "these move the real mouse and never convert: "
        f"{offenders}"
    )
