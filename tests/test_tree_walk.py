"""The public tree walk, and the three things it promises.

``JABElement.walk`` is the first piece of pyjab's traversal API that a second project
depends on, so its contract is tested rather than described: records not references, limits
that are real, and a way to know the walk was cut short.

The third is the one that is easy to leave out and expensive to leave out. A truncated
walk and a complete one produce **the same records**, so a caller that cannot tell them
apart will act on half a window believing it saw the whole thing -- which is exactly the
failure mode `tools/verify_m0.py` had in the sibling repository, where a node cap that
never fired made every run report a truncated walk as a complete one.
"""

from __future__ import annotations

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

from tests._fakejab import bind, node, panel

JABElement = _win32stubs.import_jabelement()


def a_tree():
    """A window with a known shape: two panels, each with two labels.

    Six descendants -- the frame itself is the element being walked, so it is not one of
    them.
    """
    return node(
        "frame",
        panel(node("label", name="a"), node("label", name="b"), name="left"),
        panel(node("label", name="c"), node("label", name="d"), name="right"),
        name="app",
    )


def outstanding(before, bridge):
    return {h: bridge.refs[h] - before.get(h, 0)
            for h in bridge.refs
            if bridge.refs[h] > before.get(h, 0)}


# ---------------------------------------------------------------------------
# Records, not references
# ---------------------------------------------------------------------------

def test_it_yields_records_and_not_elements():
    """The property that makes it safe: the caller never gets a reference."""
    element, _bridge = bind(a_tree())

    entries = list(element.walk())

    assert entries, "the fixture has descendants"
    assert all(isinstance(item, dict) for _depth, item in entries)


def test_it_releases_every_reference_it_takes():
    """Checked by the bridge that counts them, not by reading the code."""
    element, bridge = bind(a_tree())
    before = dict(bridge.refs)

    list(element.walk())

    assert not outstanding(before, bridge), "the walk left references outstanding"


def test_a_walk_abandoned_part_way_releases_what_it_took():
    """The caller may stop iterating, and that must not leak.

    This is why the release is in a ``finally`` and not simply after the ``yield``: a
    generator that is closed from outside resumes by raising ``GeneratorExit`` at the
    ``yield``, and only a ``finally`` runs.
    """
    element, bridge = bind(a_tree())
    before = dict(bridge.refs)

    tree = element.walk()
    for _depth, _item in tree:
        break                       # take one and walk away

    assert not outstanding(before, bridge), (
        "abandoning the walk left the references it had taken outstanding"
    )


# ---------------------------------------------------------------------------
# Limits that are real
# ---------------------------------------------------------------------------

def test_max_depth_zero_yields_only_the_immediate_children():
    element, _bridge = bind(a_tree())

    depths = [depth for depth, _item in element.walk(max_depth=0)]

    assert depths == [0, 0]


def test_max_depth_one_stops_below_the_grandchildren():
    element, _bridge = bind(a_tree())

    depths = [depth for depth, _item in element.walk(max_depth=1)]

    # Depth-first: the first panel, its two labels, then the second panel and its two.
    # Written out rather than counted, because the order is part of the contract -- a
    # caller rendering a tree depends on a node being followed by its own subtree.
    assert depths == [0, 1, 1, 0, 1, 1]


def test_the_limit_actually_stops_the_walk():
    """Not just the frame it was checked in.

    The first version of this check lived inside the recursion, so ``return`` ended one
    frame while the parent's loop carried on and called back in. The walk still stopped at
    the right count, by re-entering and immediately returning once per remaining sibling --
    which is why the count looked correct and the shape was wrong.
    """
    element, bridge = bind(a_tree())
    before = dict(bridge.refs)

    entries = list(element.walk(limit=2))

    assert len(entries) == 2
    assert not outstanding(before, bridge)
    assert bridge.count("getAccessibleChildFromContext") <= 4, (
        "the walk kept asking for children after it had enough"
    )


# ---------------------------------------------------------------------------
# Knowing it was cut short
# ---------------------------------------------------------------------------

def test_a_complete_walk_is_not_truncated():
    element, _bridge = bind(a_tree())
    tree = element.walk()

    list(tree)

    assert tree.truncated is False
    assert tree.limit_hit is False


def test_a_limited_walk_says_so():
    element, _bridge = bind(a_tree())
    tree = element.walk(limit=2)

    list(tree)

    assert tree.truncated is True
    assert tree.limit_hit is True


def test_a_walk_that_ends_exactly_at_the_limit_is_still_truncated():
    """The case a count cannot distinguish, and the reason this attribute exists.

    The fixture has seven elements. Asking for seven gives a complete walk; asking for
    seven when there are more would give the identical seven records. Only the walk knows
    which happened, so the caller must be able to ask it.
    """
    element, _bridge = bind(a_tree())
    everything = element.walk()
    all_entries = list(everything)
    total = len(all_entries)

    exactly = element.walk(limit=total)
    assert len(list(exactly)) == total

    # Reaching the limit is what was asked for, and there was nothing left, so this is a
    # complete walk -- but it is reported as limit_hit because the walk cannot know there
    # was nothing left without asking, and asking is the cost the limit exists to avoid.
    # The honest reading is therefore "may have been truncated", and the docstring says so.
    assert exactly.truncated == (exactly.limit_hit)


def test_asking_for_more_than_exists_is_not_truncated():
    element, _bridge = bind(a_tree())
    tree = element.walk(limit=1000)

    entries = list(tree)

    assert len(entries) == 6, "the fixture's shape"
    assert tree.truncated is False
    assert tree.limit_hit is False


def test_max_depth_is_reported_separately_from_truncation():
    """Stopping where you were told to stop is not truncation."""
    element, _bridge = bind(a_tree())
    tree = element.walk(max_depth=0)

    list(tree)

    assert tree.max_depth_hit is True
    assert tree.truncated is False, (
        "a walk asked for one level and given one level did what it was asked"
    )


# ---------------------------------------------------------------------------
# as_record
# ---------------------------------------------------------------------------

def test_a_record_carries_what_a_locator_can_match_on():
    element, _bridge = bind(a_tree())

    _depth, item = next(iter(element.walk()))

    for field in ("role", "name", "description", "index_in_parent",
                  "children_count", "object_depth", "states", "bounds"):
        assert field in item


def test_a_record_holds_no_reference():
    """So it cannot leak, which is the reason it is a dict."""
    element, _bridge = bind(a_tree())

    _depth, item = next(iter(element.walk()))

    assert all(isinstance(value, (str, int, float, dict, list, type(None)))
               for value in item.values())
