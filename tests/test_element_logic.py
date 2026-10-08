"""Logic tests for JABElement that need no Java application.

Most of pyjab's element behaviour is only reachable through a live Swing app,
but the parts exercised here are pure logic: they run anywhere, by importing
``pyjab.jabelement`` through the shared pywin32 stand-ins.

Every test in this module is a regression guard for a defect that was found by
reading the source and had no issue tracking it.
"""

import types
from ctypes import byref, c_int
from unittest.mock import MagicMock, patch

import pytest

# What byref() returns. ctypes stopped exporting CArgObject as a public name, so
# ask for an instance rather than importing the class.
BYREF_TYPE = type(byref(c_int()))

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import
from pyjab.accessibleinfo import (
    AccessibleContextInfo,
    AccessibleTextInfo,
    VisibleChildrenInfo,
)
from pyjab.common.by import By
from pyjab.common.exceptions import JABException
from pyjab.common.states import States
from pyjab.common.types import JOBJECT64
from pyjab.common.win32utils import Win32Utils

JABElement = _win32stubs.import_jabelement()

# Win32Utils is @singleton, so class-level patching must go through __wrapped__.
Win32UtilsClass = Win32Utils.__wrapped__


def make_element() -> "JABElement":
    return JABElement(
        bridge=MagicMock(), hwnd=1, vmid=1, accessible_context=JOBJECT64(0)
    )


# ---------------------------------------------------------------------------
# find_element_by_xpath is covered behaviourally, against a synthetic tree, in
# tests/test_xpath_traversal.py. The two tests that used to live here asserted
# on _get_element_by_node receiving a particular level -- an implementation
# detail of the traversal that the 1.4.0 pruning work replaced.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# find_element_by_states: a str locator must not be compared character by character
# ---------------------------------------------------------------------------

class _FakeElement:
    states_en_us = ["enabled", "showing"]


@pytest.mark.parametrize("value", [
    ["enabled", "showing"],
    "enabled,showing",
    "enabled, showing",
])
def test_states_locator_matches(value):
    assert JABElement._is_element_matched(_FakeElement(), By.STATES, value)


@pytest.mark.parametrize("value", ["enabled", ["enabled"], []])
def test_states_locator_rejects_a_different_set(value):
    assert not JABElement._is_element_matched(_FakeElement(), By.STATES, value)


def test_a_state_name_is_not_split_into_characters():
    """Regression: ``set("enabled")`` is a set of letters, so it never matched.

    The type annotation allowed a str and the docstring advertised a list, so a
    caller passing a single state name silently got no match.
    """
    assert JABElement._states_as_set("enabled") == {"enabled"}
    assert JABElement._states_as_set(["a", "b"]) == {"a", "b"}


# ---------------------------------------------------------------------------
# The wait helpers actually wait
# ---------------------------------------------------------------------------

def test_wait_for_value_to_be_repolls_the_value():
    """Regression: the caller's value was evaluated once, before the call.

    The comparison result therefore could not change, so the loop span until it
    timed out and could never succeed.
    """
    reads = []

    def current_text():
        reads.append(1)
        return "updated" if len(reads) >= 3 else ""

    JABElement._wait_for_value_to_be("updated", current_text, poll_interval=0.001)

    assert len(reads) == 3


def test_wait_for_value_to_be_still_accepts_a_plain_value():
    JABElement._wait_for_value_to_be("done", "done")


def test_wait_for_value_to_contain_repolls_the_value():
    reads = []

    def current_states():
        reads.append(1)
        return [States.SELECTED] if len(reads) >= 2 else []

    JABElement._wait_for_value_to_contain(
        [States.SELECTED, States.CHECKED], current_states, poll_interval=0.001
    )

    assert len(reads) == 2


def test_wait_helpers_back_off_instead_of_spinning():
    """A busy loop would poll thousands of times in this window.

    This is the portable half of the CPU check: it proves the loop sleeps,
    without needing to measure CPU time on a live application.
    """
    reads = []

    def never_matches():
        reads.append(1)
        return "something else"

    with pytest.raises(TimeoutError):
        JABElement._wait_for_value_to_be(
            "expected", never_matches, timeout=0.2, poll_interval=0.05
        )

    assert 1 <= len(reads) <= 10, f"polled {len(reads)} times in 0.2s"


def test_wait_helpers_time_out_with_the_expected_message():
    with pytest.raises(TimeoutError) as excinfo:
        JABElement._wait_for_value_to_be(
            "expected", "actual", timeout=0, error_msg_function="clear text"
        )

    assert "clear text" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Text: an empty element reads as ""
# ---------------------------------------------------------------------------

def element_with_text(char_count: int):
    element = make_element()
    acc_info = AccessibleContextInfo()
    acc_info.accessibleText = 1
    # _acc_info is bound to the method at construction, so patch the instance.
    element._acc_info = lambda: acc_info

    text_info = AccessibleTextInfo()
    text_info.charCount = char_count
    element._get_accessible_text_info = lambda *a, **k: text_info
    return element


def test_empty_text_reads_as_empty_string():
    """Regression: charCount 0 made chars_end -1, which JAB rejects.

    Reading a cleared text field raised RuntimeError, so ``clear()`` -- which
    waits for exactly that state -- could never succeed.
    """
    element = element_with_text(char_count=0)

    with patch.object(JABElement, "_get_accessible_text_range") as get_range:
        assert element.text == ""

    get_range.assert_not_called()


def test_non_empty_text_still_reads_the_range():
    element = element_with_text(char_count=5)

    with patch.object(JABElement, "_get_accessible_text_range") as get_range:
        element.text

    get_range.assert_called_once()


def test_element_without_text_interface_returns_none():
    """The declared type is Optional[str]: no interface means None, not ""."""
    element = make_element()
    acc_info = AccessibleContextInfo()
    acc_info.accessibleText = 0
    element._acc_info = lambda: acc_info

    assert element.text is None


# ---------------------------------------------------------------------------
# Visible children: one call supplies both the array and its length
# ---------------------------------------------------------------------------

def test_visible_children_uses_the_count_from_the_array_it_indexes():
    """Regression: the count and the array came from two separate JAB calls.

    The count from getVisibleChildrenCount was used to index the array returned
    by getVisibleChildren, so any disagreement read past the real contents.
    """
    element = make_element()

    info = VisibleChildrenInfo()
    info.returnedChildrenCount = 2
    info.children[0] = JOBJECT64(1)
    info.children[1] = JOBJECT64(2)

    with patch.object(JABElement, "_get_visible_children", return_value=info):
        # The other call now disagrees on purpose; it must be ignored.
        with patch.object(JABElement, "_get_visible_children_count", return_value=5):
            children = list(
                element._generate_childs_from_element(
                    jabelement=element, visible=True
                )
            )

    assert len(children) == 2


def test_no_visible_children_yields_nothing():
    element = make_element()

    info = VisibleChildrenInfo()
    info.returnedChildrenCount = 0

    with patch.object(JABElement, "_get_visible_children", return_value=info):
        children = list(
            element._generate_childs_from_element(jabelement=element, visible=True)
        )

    assert children == []


# ---------------------------------------------------------------------------
# doAccessibleActions: the failure index is written somewhere it survives
# ---------------------------------------------------------------------------

def test_do_accessible_action_passes_the_failure_index_by_reference():
    """Regression: a bare jint() instance was passed as the out-parameter.

    ctypes accepts that -- it passes the instance's own address -- so nothing
    raised, but the index was written into a temporary and discarded.
    """
    element = make_element()

    def get_actions(vmid, accessible_context, out):
        out._obj.actionsCount = 1

    element.bridge.getAccessibleActions.side_effect = get_actions

    element._do_accessible_action()

    args = element.bridge.doAccessibleActions.call_args.args
    assert len(args) == 4
    assert isinstance(args[3], BYREF_TYPE), (
        "the jint *failure out-parameter must be passed with byref()"
    )


# ---------------------------------------------------------------------------
# get_children and the name-pattern finders (contributed in #77)
# ---------------------------------------------------------------------------

class _FakeChild:
    """Enough of a JABElement for _is_element_matched and the pattern finders."""

    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"_FakeChild({self.name!r})"


def children_of(element, kids, method="_generate_childs_from_element"):
    """Patch a child generator to yield *kids*, and record releases."""
    generator = patch.object(JABElement, method, return_value=iter(kids))
    release = patch.object(JABElement, "release_jabelement")
    return generator, release


def test_get_children_returns_every_immediate_child():
    element = make_element()
    kids = [_FakeChild("alpha"), _FakeChild("beta")]

    generator, release = children_of(element, kids)
    with generator, release as released:
        result = element.get_children()

    assert result == kids
    released.assert_not_called()


def test_get_children_filters_and_releases_the_rest():
    """The filtered-out children must be released, not dropped.

    Java Access Bridge keeps its own reference to every object it hands out, so
    a child that is never returned to the caller has to be released here. Every
    other filtering method in jabelement.py does this; get_children did not.
    """
    element = make_element()
    kept, dropped = _FakeChild("keep"), _FakeChild("drop")

    generator, release = children_of(element, [kept, dropped])
    with generator, release as released:
        result = element.get_children(by=By.NAME, value="keep")

    assert result == [kept]
    released.assert_called_once_with(dropped)


def test_get_children_without_a_filter_releases_nothing():
    element = make_element()
    kids = [_FakeChild("a"), _FakeChild("b"), _FakeChild("c")]

    generator, release = children_of(element, kids)
    with generator, release as released:
        element.get_children(by=None)

    released.assert_not_called()


def test_get_children_of_a_childless_element_is_an_empty_list():
    """Not an error: no children is an ordinary state, unlike find_elements()."""
    element = make_element()

    generator, release = children_of(element, [])
    with generator, release:
        assert element.get_children() == []


@pytest.mark.parametrize("pattern, expected_names", [
    ("^Save", ["Save As", "Save"]),
    ("Save", ["Save As", "Save"]),
    ("As$", ["Save As"]),
    ("nothing-matches", []),
])
def test_find_elements_by_name_pattern(pattern, expected_names):
    element = make_element()
    kids = [_FakeChild("Save As"), _FakeChild("Save"), _FakeChild("Cancel")]

    generator, release = children_of(element, kids, "_generate_all_childs")
    with generator, release as released:
        if expected_names:
            result = element.find_elements_by_name_pattern(pattern)
            assert [c.name for c in result] == expected_names
        else:
            with pytest.raises(JABException):
                element.find_elements_by_name_pattern(pattern)

    # Whatever was not returned must have been released.
    assert released.call_count + len(expected_names) == len(kids)


def test_find_elements_by_name_pattern_ignores_case_on_request():
    element = make_element()
    kids = [_FakeChild("Save")]

    generator, release = children_of(element, kids, "_generate_all_childs")
    with generator, release:
        assert element.find_elements_by_name_pattern("save", ignorecase=True) == kids


def test_find_element_by_name_pattern_stops_at_the_first_match():
    element = make_element()
    first, second = _FakeChild("Cancel"), _FakeChild("Save")

    generator, release = children_of(element, [first, second], "_generate_all_childs")
    with generator, release as released:
        assert element.find_element_by_name_pattern("^Save") is second

    released.assert_called_once_with(first)


def test_find_element_by_name_pattern_raises_when_nothing_matches():
    element = make_element()
    kids = [_FakeChild("Cancel")]

    generator, release = children_of(element, kids, "_generate_all_childs")
    with generator, release:
        with pytest.raises(JABException):
            element.find_element_by_name_pattern("^Save")


# ---------------------------------------------------------------------------
# expand() expands, and says so
# ---------------------------------------------------------------------------

def element_reporting_states(states: str):
    """A JABElement whose accessibility states are whatever we say they are."""
    element = make_element()
    element._acc_info = lambda: types.SimpleNamespace(states_en_US=states)
    return element


def test_expanding_an_expanded_element_does_nothing():
    """Regression: expand() sent 'toggleexpand' unconditionally.

    So calling it on a node that was already open **collapsed** it, and the
    children the call was made for disappeared.  A tree that starts expanded --
    which is the default for a JTree -- could not be walked at all.
    """
    element = element_reporting_states("enabled,expandable,expanded")

    with patch.object(JABElement, "_do_accessible_action") as action:
        element.expand()

    action.assert_not_called()
    assert element.is_expanded()


def test_expanding_a_collapsed_element_sends_the_action():
    element = element_reporting_states("enabled,expandable,collapsed")

    with patch.object(JABElement, "_do_accessible_action") as action:
        element.expand()

    assert action.call_args.args[0] == "toggleexpand"


def test_expanding_something_that_cannot_expand_raises():
    element = element_reporting_states("enabled")

    with pytest.raises(JABException):
        element.expand()


def test_is_expanded_reports_the_state():
    assert element_reporting_states("enabled,expanded").is_expanded()
    assert not element_reporting_states("enabled,collapsed").is_expanded()
    assert not element_reporting_states("enabled").is_expanded()

# ---------------------------------------------------------------------------
# Mouse clicks: where they land, and what they refuse to do
# ---------------------------------------------------------------------------

def element_with_bounds(x, y, width, height):
    """A JABElement reporting the given bounds; bounds is a read-only property."""
    element = make_element()
    element._acc_info = lambda: types.SimpleNamespace(
        x=x, y=y, width=width, height=height, states_en_US="enabled"
    )
    return element


@pytest.mark.parametrize("x, y, width, height", [
    # What JAB reports for anything it does not place on screen, table cells
    # above all. Using these moves the cursor to the corner of the display.
    (-1, -1, -1, -1),
    (10, 10, 0, 40),
    (10, 10, 40, 0),
    (None, 10, 40, 40),
    (10, 10, None, 40),
])
def test_a_click_refuses_impossible_bounds(x, y, width, height):
    """Regression: only zero was rejected, not -1.

    ``click(simulate=True)`` on a table cell computed a point from -1 and moved
    the cursor there rather than saying the element cannot be clicked.
    """
    element = element_with_bounds(x, y, width, height)

    with pytest.raises(JABException) as excinfo:
        element._click_point()

    assert "no usable bounds" in str(excinfo.value)


def test_a_click_targets_the_centre_of_the_element():
    element = element_with_bounds(100, 200, 50, 40)

    assert element._click_point() == (125, 220)


def test_double_click_moves_the_mouse_twice_at_one_place():
    element = element_with_bounds(0, 0, 10, 10)

    with patch.object(Win32UtilsClass, "_set_window_foreground"):
        with patch.object(Win32UtilsClass, "_double_click_mouse") as double:
            element.double_click()

    double.assert_called_once_with(x=5, y=5)


def test_context_click_uses_the_right_button():
    element = element_with_bounds(0, 0, 10, 10)

    with patch.object(Win32UtilsClass, "_set_window_foreground"):
        with patch.object(Win32UtilsClass, "_click_mouse") as click:
            element.context_click()

    assert click.call_args.kwargs["button"] == "right"


def test_double_click_needs_bounds_like_any_other_mouse_click():
    element = element_with_bounds(-1, -1, -1, -1)

    with patch.object(Win32UtilsClass, "_set_window_foreground"):
        with pytest.raises(JABException):
            element.double_click()


# ---------------------------------------------------------------------------
# The double-click interval, which win32api does not have
# ---------------------------------------------------------------------------

def test_the_double_click_gap_is_half_the_system_interval(monkeypatch):
    """``user32.GetDoubleClickTime`` in milliseconds, halved, in seconds.

    Through ctypes rather than ``win32api`` because ``win32api`` does not expose
    ``GetDoubleClickTime`` at all -- which is how this was found.  The GUI suite
    failed on Windows with ``AttributeError: module 'win32api' has no attribute
    'GetDoubleClickTime'`` and CI stayed green, because CI never runs the GUI
    suite.  So the arithmetic gets a test that runs everywhere.
    """
    import ctypes
    import types

    from pyjab.common import win32utils

    user32 = types.SimpleNamespace(GetDoubleClickTime=lambda: 500)
    monkeypatch.setattr(ctypes, "windll", types.SimpleNamespace(user32=user32),
                        raising=False)

    assert win32utils.double_click_gap() == 0.25

    user32.GetDoubleClickTime = lambda: 900
    assert win32utils.double_click_gap() == 0.45


def test_double_click_waits_that_long_between_the_two_clicks(monkeypatch):
    """The gap is used, and it is the one the system reports."""
    from pyjab.common import win32utils

    slept = []
    monkeypatch.setattr(win32utils, "double_click_gap", lambda: 0.125)
    monkeypatch.setattr(win32utils.time, "sleep", slept.append)
    # This test is about the wait, not about what pywin32 exposes, so both the
    # module and its constants are replaced wholesale.  A partial or absent
    # pywin32 has to be able to run the suite -- AGENTS.md 4 -- and a bare
    # `win32con` has no MOUSEEVENTF_LEFTDOWN to look up.
    monkeypatch.setattr(win32utils, "win32api", types.SimpleNamespace(
        SetCursorPos=lambda where: None,
        mouse_event=lambda *args: None,
    ))
    monkeypatch.setattr(win32utils, "win32con", types.SimpleNamespace(
        MOUSEEVENTF_LEFTDOWN=1, MOUSEEVENTF_LEFTUP=2,
    ))

    Win32UtilsClass._double_click_mouse(x=3, y=4)

    assert slept == [0.125], "it did not wait half the interval"
