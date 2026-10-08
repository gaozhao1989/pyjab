"""How find_element_by_* walks the accessibility tree.

Every test here runs against a synthetic tree (``tests/_fakejab.py``) whose
bridge counts the cross-process JAB calls a lookup makes. That is what makes the
performance claims in this module checkable without a Windows machine: the cost
of a lookup is dominated by JAB round-trips, and the fake counts exactly those.

The behaviour being pinned down:

* a node is tested **before** its subtree is entered, so a shallow match is found
  without walking what is underneath it;
* the path prunes the walk, and the search backtracks when the rest of a path
  does not fit under a candidate;
* a locator starting with ``.`` is relative to the element it is issued from.
"""

import logging
from unittest.mock import patch

import pytest

from _fakejab import JABElement, bind, node, panel, table
from pyjab.common.exceptions import JABException
from pyjab.common.types import JOBJECT64
from pyjab.common.win32utils import Win32Utils

Win32UtilsClass = Win32Utils.__wrapped__


@pytest.fixture(autouse=True)
def no_real_pump():
    """The pump is unrelated to traversal; keep it out of the counts."""
    with patch.object(Win32UtilsClass, "pump_messages"):
        yield


def find(root, xpath_or_call):
    element, bridge = bind(root)
    if callable(xpath_or_call):
        result = xpath_or_call(element)
    else:
        result = element.find_element_by_xpath(xpath_or_call)
    return result, bridge


def bind_to(bridge, target):
    return JABElement(bridge=bridge, hwnd=1234, vmid=1,
                      accessible_context=JOBJECT64(target.handle))


# ---------------------------------------------------------------------------
# Cost follows the path, not the size of the tree
# ---------------------------------------------------------------------------

def big_window(rows):
    """A window shaped like the one in issue #33: a deep path over a big table."""
    inner = panel(table(rows, 10), node("push button", name="Submit"), index=1)
    return node("frame", node("root pane", node("layered pane",
                panel(panel(inner, index=0), index=0))))


ISSUE_33_PATH = (
    "//root pane/layered pane"
    "/panel[@indexinparent=0]/panel[@indexinparent=0]"
    "/panel[@indexinparent=1]/push button"
)


def test_a_deep_path_costs_the_same_in_a_big_tree_as_a_small_one():
    """Regression for issues #33 and #29.

    The first node of a path used to be searched with a post-order walk of the
    entire subtree: a node was yielded only after everything below it had been
    visited, so the search root's own first child was reached last. On the
    window from #33 -- a deep path over a table with a few thousand cells --
    that was thousands of JAB calls for an answer six levels down, and it is
    where the reported 40 seconds went.

    The assertion is deliberately about *scaling* rather than a call count: a
    lookup whose answer is at a known depth must not care how much else the
    window contains.
    """
    small, small_bridge = find(big_window(2), ISSUE_33_PATH)
    large, large_bridge = find(big_window(200), ISSUE_33_PATH)

    assert small.name == "Submit"
    assert large.name == "Submit"
    assert large_bridge.total == small_bridge.total, (
        "lookup cost grew with the size of the window: "
        f"{small_bridge.total} calls for a small tree, "
        f"{large_bridge.total} for a large one"
    )
    assert large_bridge.total < 100


def test_a_match_is_found_before_its_own_subtree_is_walked():
    """Regression: the walk was post-order, so a node came after its subtree."""
    bulk = node("table", *[node("label", name=f"c{i}") for i in range(200)])
    root = node("frame", node("panel", bulk, name="Target"))

    found, bridge = find(root, lambda e: e.find_element_by_role("panel"))

    assert found.name == "Target"
    assert bridge.total < 20, (
        f"walked {bridge.total} nodes to reach a node one level down"
    )


def test_find_element_by_role_uses_the_same_walk_as_xpath():
    """find_element() is the single entry point every locator uses."""
    bulk = node("table", *[node("label", name=f"c{i}") for i in range(200)])
    root = node("frame", node("push button", bulk, name="Target"))

    found, bridge = find(root, lambda e: e.find_element_by_role("push button"))

    assert found.name == "Target"
    assert bridge.total < 20


# ---------------------------------------------------------------------------
# The path prunes, and the search backtracks
# ---------------------------------------------------------------------------

def test_a_later_node_is_a_child_of_the_earlier_one():
    """Regression: ``nodes.index(node)`` decided the level.

    For a path whose nodes repeat -- ``//panel/panel`` -- ``index`` always
    returns 0, so the second node was looked up as a root-level node and the
    path silently degraded into a whole-tree search.
    """
    inner = node("panel", node("push button", name="Target"), name="inner")
    root = node("frame", node("panel", inner, name="outer"))

    found, _ = find(root, "//panel/panel")

    assert found.name == "inner"


def test_the_search_backtracks_when_the_rest_of_the_path_does_not_fit():
    """The old implementation took the first match and gave up.

    It found the first node whose role and attributes matched, then required the
    remainder of the path underneath *that* one, and raised if it was not there.
    """
    first = node("panel", node("label", name="nothing"), name="first")
    second = node("panel", node("push button", name="Target"), name="second")
    root = node("frame", first, second)

    found, _ = find(root, "//panel/push button")

    assert found.name == "Target"


def test_a_path_that_matches_nothing_raises():
    root = node("frame", node("panel", node("label", name="x")))

    with pytest.raises(Exception) as info:
        find(root, "//push button")

    assert "no JABElement found by xpath" in str(info.value)


def test_a_slash_inside_an_attribute_value_stays_in_one_node():
    """End-to-end guard for the quote-aware split, through the real caller."""
    root = node("frame", node("panel", name="a/b"))

    found, _ = find(root, "//panel[@name='a/b']")

    assert found.name == "a/b"


def test_an_attribute_predicate_still_filters():
    root = node("frame",
                node("panel", name="first"),
                node("panel", name="second"))

    found, _ = find(root, "//panel[@name='second']")

    assert found.name == "second"


# ---------------------------------------------------------------------------
# Relative locators (issue #54)
# ---------------------------------------------------------------------------

def test_a_leading_dot_searches_from_this_element():
    """Regression for #54.

    A lookup issued from a child used to have ``self.parent`` substituted for the
    starting node, so it silently began one level up. An absolute locator now
    means the whole window, as XPath's '//' does, and a leading '.' means "from
    here".
    """
    sibling = node("panel", node("push button", name="Sibling"))
    child = node("panel", node("push button", name="Target"))
    root = node("frame", sibling, child)

    _, bridge = bind(root)
    from_child = bind_to(bridge, child)

    assert from_child.find_element_by_xpath("//push button").name == "Sibling"
    assert from_child.find_element_by_xpath(".//push button").name == "Target"


def test_a_relative_locator_does_not_see_a_sibling_subtree():
    sibling = node("panel", node("push button", name="Sibling"))
    child = node("panel", node("label", name="Target"))
    root = node("frame", sibling, child)

    _, bridge = bind(root)
    from_child = bind_to(bridge, child)

    with pytest.raises(Exception):
        from_child.find_element_by_xpath(".//push button")


# ---------------------------------------------------------------------------
# Ownership: every node created is released exactly once
# ---------------------------------------------------------------------------

def test_a_failed_search_releases_every_node_it_created():
    root = node("frame", node("panel", table(3, 3)))

    with pytest.raises(Exception):
        find(root, "//push button")


def test_a_successful_search_releases_everything_but_the_match():
    """The fake raises on a released handle being used, and on a double release.

    A traversal that releases a node and then descends into it is the failure
    mode this catches, and it is easy to introduce when reordering a walk.
    """
    root = node("frame",
                node("panel", node("label", name="skip")),
                node("panel", node("push button", name="Target")))

    found, bridge = find(root, "//push button")

    assert found.name == "Target"
    assert bridge.calls["releaseJavaObject"] > 0


# ---------------------------------------------------------------------------
# The tree is not guaranteed to be one
# ---------------------------------------------------------------------------

def make_a_cycle(depth=6):
    """A bound element whose tree loops back on itself.

    Java Access Bridge will report a parent among a node's descendants when the
    application's accessibility implementation is wrong or mid-update.  The walk
    is recursive and every step is a fresh cross-process call that succeeds, so
    following that is a hang rather than an error -- which is what a lookup on a
    real colour chooser panel did.

    The cycle is added *after* bind(), because the fake indexes the tree
    recursively when it is built and would loop there instead.
    """
    leaf = node("label", name="deep")
    root = node("panel", leaf, name="root")
    element, bridge = bind(root)
    # The leaf now has the root as a child, so walking down never terminates.
    leaf.children.append(root)
    root.parent = leaf
    return element, bridge


def test_a_cyclic_tree_does_not_hang_a_name_lookup():
    """It returns, and says why, instead of walking forever.

    Before the ceiling this ended in ``RecursionError`` from inside a frame the
    caller never wrote, after seconds of cross-process calls.  A cyclic tree that
    loops *within* one subtree rather than straight down would not even get that
    far -- each step is a call that succeeds, so it simply keeps going.  The
    ceiling makes both cases an ordinary "not found" with a warning.
    """
    element, _ = make_a_cycle()

    with pytest.raises(JABException):
        element.find_element_by_name("not in this tree")


def test_a_cyclic_tree_does_not_hang_an_xpath_lookup():
    element, _ = make_a_cycle()

    # Not a role the tree contains, so the walk has to exhaust it -- which is
    # where an unbounded one never comes back.
    with pytest.raises(JABException):
        element.find_element_by_xpath("//push button")


def test_the_cycle_is_reported_rather_than_silently_swallowed(caplog):
    """A depth stop is a warning, not a quiet miss.

    If it were silent, a genuinely too-deep tree would look like a locator
    problem and be debugged as one.
    """
    element, _ = make_a_cycle()

    with caplog.at_level(logging.WARNING, logger="pyjab"):
        with pytest.raises(JABException):
            element.find_element_by_name("not in this tree")

    assert any("MAX_SEARCH_DEPTH" in record.message or
               "MAX_SEARCH_DEPTH" in str(record.args)
               for record in caplog.records), caplog.text


def test_a_normal_tree_is_not_affected_by_the_ceiling():
    """The ceiling must be far past anything real: 100 against a depth of 3."""
    root = node("panel", node("panel", node("label", name="target"),
                              name="inner"), name="outer")
    element, _ = bind(root)

    assert element.find_element_by_name("target").name == "target"
