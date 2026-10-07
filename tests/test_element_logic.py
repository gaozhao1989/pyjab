"""Logic tests for JABElement that need no Java application.

Most of pyjab's element behaviour is only reachable through a live Swing app,
but the parts exercised here are pure logic: they run anywhere, by importing
``pyjab.jabelement`` through the shared pywin32 stand-ins.

Every test in this module is a regression guard for a defect that was found by
reading the source and had no issue tracking it.
"""

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
# find_element_by_xpath: the node level follows position, not node name
# ---------------------------------------------------------------------------

def test_xpath_levels_follow_position_not_node_name():
    """Regression: ``nodes.index(node)`` was used to decide the level.

    For a path whose nodes repeat -- ``//panel/panel`` -- ``index`` always
    returns 0, so the second node was looked up as a root-level node and the
    path silently degraded into a whole-tree search.
    """
    element = make_element()
    seen = []

    def record(node, level, jabelement, visible):
        seen.append((node, level))
        return MagicMock()  # truthy, so the loop continues

    with patch.object(JABElement, "_get_element_by_node", side_effect=record):
        with patch.object(Win32UtilsClass, "pump_messages"):
            element.find_element_by_xpath("//panel/panel")

    assert seen == [("panel", "root"), ("panel", "child")]


def test_xpath_with_a_slash_in_an_attribute_value_stays_one_node():
    """End-to-end guard for the quote-aware split, through the real caller."""
    element = make_element()
    seen = []

    def record(node, level, jabelement, visible):
        seen.append(node)
        return MagicMock()

    with patch.object(JABElement, "_get_element_by_node", side_effect=record):
        with patch.object(Win32UtilsClass, "pump_messages"):
            element.find_element_by_xpath("//panel[@name='a/b']")

    assert seen == ["panel[@name='a/b']"]


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
