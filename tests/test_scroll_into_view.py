"""Scrolling an element into view, which JAB gives no way to ask for.

There is no scroll-position call and no scroll-to API: the only tools are the
element rectangles, the mouse, and looking again.  So this is best effort by
construction, and what it returns says what it achieved rather than assuming it
worked -- which is what makes it testable at all.

Two of the three methods are pure enough to check exactly.  The third drives a
mouse, so the fake bridge's rectangles are moved underneath it and the loop is
checked for the three ways it can end: the element came inside, the bar reached
its end, or the step budget ran out.

What these tests cannot show is whether a real application repaints fast enough
for the next read to see the new position, or whether it moves the element at all.
That needs Windows (#15, #59).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import
from pyjab.common.role import Role
from pyjab.common.win32utils import Win32Utils
from tests._fakejab import bind, node, rect

# pyjab.jabelement raises ImportError off Windows unless sys.platform is faked
# for the import; the helper does that and restores it.  Importing the module
# directly here would fail, which is what the first version of this file did.
JABElement = _win32stubs.import_jabelement()

# Win32Utils is @singleton, so class-level patching goes through __wrapped__.
Win32UtilsClass = Win32Utils.__wrapped__


def a_viewport(target_bounds, viewport=rect(0, 0, 100, 100)):
    """A scroll pane holding a vertical scroll bar and one target child.

    Returns ``(target_element, viewport_element, target_node, bridge)``.
    """
    target = node("label", name="row 9", bounds=target_bounds)
    bar = node("scroll bar", name="vertical scroll bar", bounds=rect(90, 0, 10, 100))
    pane = node(Role.SCROLL_PANE, bar, target, name="viewport", bounds=viewport)
    element, bridge = bind(pane)
    # bind() wraps the pane; reach the target through the tree it built.
    children = element.get_children()
    bar_element = next(c for c in children if c.role_en_us == Role.SCROLL_BAR)
    target_element = next(c for c in children if c.name == "row 9")
    bar.releases = bar_element
    return target_element, element, target, bridge


# ---------------------------------------------------------------------------
# The geometry
# ---------------------------------------------------------------------------

def test_a_rectangle_inside_another_is_within_it():
    target, pane, _, _ = a_viewport(rect(10, 10, 20, 20))

    assert target.bounds_within(pane) is True


def test_a_rectangle_below_the_viewport_is_not_within_it():
    """The case the whole issue is about: a row further down the list."""
    target, pane, _, _ = a_viewport(rect(0, 200, 50, 20))

    assert target.bounds_within(pane) is False


@pytest.mark.parametrize("where", [
    rect(-5, 10, 20, 20),      # off the left edge
    rect(10, -5, 20, 20),      # above the top edge
    rect(95, 10, 20, 20),      # past the right edge
    rect(10, 95, 20, 20),      # past the bottom edge
])
def test_a_rectangle_hanging_over_an_edge_is_not_within(where):
    target, pane, _, _ = a_viewport(where)

    assert target.bounds_within(pane) is False


def test_invalid_bounds_answer_false_rather_than_doing_arithmetic_on_minus_one():
    """Swing reports -1 for a control it has no rectangle for.

    A table cell scrolled out of view is the usual case (#20, #61).  Comparing
    -1 against a real rectangle would give a confident wrong answer, so it is
    refused instead.
    """
    target, pane, _, _ = a_viewport(rect(-1, -1, -1, -1))

    assert target.bounds_within(pane) is False


def test_an_invalid_container_rectangle_also_answers_false():
    target, pane, _, _ = a_viewport(rect(10, 10, 20, 20), viewport=rect(-1, -1, -1, -1))

    assert target.bounds_within(pane) is False


# ---------------------------------------------------------------------------
# Finding what to scroll
# ---------------------------------------------------------------------------

def test_the_scrollable_ancestor_is_the_enclosing_scroll_pane():
    target, pane, _, _ = a_viewport(rect(0, 200, 50, 20))

    assert target._scrollable_ancestor().name == "viewport"


def test_a_panel_holding_a_scroll_bar_counts_as_scrollable():
    """Some applications lay the bar out beside the content rather than in a pane."""
    target = node("label", name="row 9", bounds=rect(0, 200, 20, 20))
    bar = node("scroll bar", name="bar", bounds=rect(90, 0, 10, 100))
    holder = node("panel", bar, target, name="holder", bounds=rect(0, 0, 100, 100))
    element, _ = bind(holder)

    target_element = next(c for c in element.get_children() if c.name == "row 9")

    assert target_element._scrollable_ancestor().name == "holder"


def test_an_element_with_no_scrollable_ancestor_finds_none():
    target = node("label", name="plain", bounds=rect(0, 0, 10, 10))
    root = node("panel", target, name="root", bounds=rect(0, 0, 500, 500))
    element, _ = bind(root)

    child = element.get_children()[0]

    assert child._scrollable_ancestor() is None


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

def scrolling_by(amount):
    """A _click_mouse stand-in that moves the target, as an application would."""
    def step(*args, **kwargs):
        return amount()
    return step


def test_an_element_already_inside_is_left_alone():
    target, pane, node_, _ = a_viewport(rect(10, 10, 20, 20))

    with patch.object(Win32UtilsClass, "_set_window_foreground"), \
         patch.object(Win32UtilsClass, "_click_mouse") as click:
        assert target.scroll_into_view(poll_interval=0) is True

    click.assert_not_called()


def test_scrolling_stops_as_soon_as_the_element_is_inside():
    target, pane, node_, _ = a_viewport(rect(0, 200, 50, 20))

    def step(*args, **kwargs):
        node_.bounds["y"] -= 60          # the application repaints it higher

    with patch.object(Win32UtilsClass, "_set_window_foreground"), \
         patch.object(Win32UtilsClass, "_click_mouse", side_effect=step) as click:
        assert target.scroll_into_view(max_steps=10, poll_interval=0) is True

    # From y=200 to inside a 0..100 viewport: 200 -> 140 -> 80, two steps.
    assert click.call_count == 2
    assert target.bounds_within(pane) is True


def test_scrolling_gives_up_when_the_rectangle_stops_moving():
    """The bar is at its end, or the mouse action did not take.

    Without this the loop would keep clicking the same pixel `max_steps` times and
    then report the same failure more slowly.
    """
    target, pane, node_, _ = a_viewport(rect(0, 200, 50, 20))

    with patch.object(Win32UtilsClass, "_set_window_foreground"), \
         patch.object(Win32UtilsClass, "_click_mouse") as click:
        assert target.scroll_into_view(max_steps=10, poll_interval=0) is False

    assert click.call_count == 1, "it kept scrolling after nothing changed"


def test_scrolling_gives_up_after_max_steps():
    """A slow application: each step moves it, but never far enough."""
    target, pane, node_, _ = a_viewport(rect(0, 900, 50, 20))

    def step(*args, **kwargs):
        node_.bounds["y"] -= 10

    with patch.object(Win32UtilsClass, "_set_window_foreground"), \
         patch.object(Win32UtilsClass, "_click_mouse", side_effect=step) as click:
        assert target.scroll_into_view(max_steps=3, poll_interval=0) is False

    assert click.call_count == 3


def test_an_element_that_cannot_scroll_reports_false_rather_than_raising():
    """No scrollable ancestor is not an error, it is a different situation."""
    target = node("label", name="plain", bounds=rect(0, 0, 10, 10))
    root = node("panel", target, name="root", bounds=rect(0, 0, 500, 500))
    element, _ = bind(root)
    child = element.get_children()[0]

    with patch.object(Win32UtilsClass, "_set_window_foreground"):
        assert child.scroll_into_view(poll_interval=0) is False


def test_the_ancestor_walk_does_not_leak_java_references():
    """Walking up obtains objects, and JAB keeps a reference to each.

    Obtaining one per call and releasing none accumulates for the life of the
    process -- which is the shape of #43, "gets slower until it stalls".  The
    walk releases every ancestor it discards, and the fake counts, so this
    asserts the balance rather than trusting it.
    """
    target, pane, _, bridge = a_viewport(rect(0, 200, 50, 20))
    before = dict(bridge.refs)

    with patch.object(Win32UtilsClass, "_set_window_foreground"), \
         patch.object(Win32UtilsClass, "_click_mouse", side_effect=lambda *a, **k: None):
        target.scroll_into_view(max_steps=1, poll_interval=0)

    grew = {h: bridge.refs[h] - before.get(h, 0)
            for h in bridge.refs if bridge.refs[h] > before.get(h, 0)}
    assert not grew, f"the ancestor walk leaked references to {grew}"


def test_the_ancestor_it_returns_is_not_released():
    """The one it hands back is the caller's to use, and to release."""
    target, pane, _, bridge = a_viewport(rect(0, 200, 50, 20))

    ancestor = target._scrollable_ancestor()

    handle = ancestor.accessible_context.value
    assert bridge.refs[handle] >= 1
    ancestor.release_jabelement()
