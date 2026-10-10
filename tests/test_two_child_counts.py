"""Two counts of children, named, because they come from different calls.

`children_count` is the **total**, from the accessibility context info; `visible_children_count`
is the count the bridge calls visible. Both are correct and they differ whenever an element has
hidden children.

**A walk uses `children_count`, not the visible one** -- this file said otherwise when it was
written, and a measurement said otherwise in turn. See #179.

**The visible count cannot detect a refused call.** `getVisibleChildrenCount` answers `0`
both for an element with no visible children and for a call it refuses, so
`visible_children_count` returns the number rather than raising. The readable signal is
`children_count`, whose `getAccessibleContextInfo` check is live. See #191.

The tests here pin the distinction and the reason `as_record()` carries only one of them.
"""

from __future__ import annotations

import _win32stubs  # noqa: F401

JABElement = _win32stubs.import_jabelement()


def test_both_counts_are_public_and_separately_named():
    assert hasattr(JABElement, "children_count")
    assert hasattr(JABElement, "visible_children_count")


def test_as_record_carries_one_count_and_not_the_other():
    """The design decision, asserted so it is not undone by accident.

    `as_record()` is the record a walk produces **per node**. `children_count` comes from
    the context info a walk has already fetched; the visible count is a second bridge call
    per node. Putting both in doubled the traffic of every walk, which is what the first
    attempt did and what eighteen failing tests said.
    """
    from tests._fakejab import bind, node

    element, _bridge = bind(node("panel", node("label", name="a"), name="p"))
    record = element.as_record()

    assert "children_count" in record
    assert "visible_children_count" not in record


def test_the_two_docstrings_point_at_each_other():
    """A caller reading either one has to be able to find out about the other.

    Cheap to assert and it is the whole point: the counts disagree legitimately, so the
    documentation is the mechanism that stops that being a mystery.
    """
    total = JABElement.children_count.__doc__ or ""
    visible = JABElement.visible_children_count.__doc__ or ""

    assert "visible_children_count" in total
    assert "children_count" in visible


def test_a_zero_visible_count_is_returned_as_zero():
    """A childless element is not an error, and the bridge answers zero for it.

    Measured on a real JVM (#191): ``getVisibleChildrenCount`` returns ``0`` for a
    childless self-painting panel, and ``0`` again when it refuses the call -- never the
    ``-1`` the JAB header documents. So there is no sentinel to raise on, and this
    property reports the number the bridge returned.
    """
    from unittest.mock import patch

    from tests._fakejab import bind, node

    element, _bridge = bind(node("panel", name="p"))
    with patch.object(JABElement, "bridge", create=True,
                      new=type("B", (), {"getVisibleChildrenCount": lambda *a: 0})()):
        assert element.visible_children_count == 0


def test_the_visible_count_is_the_bridge_return_passed_through():
    """Whatever the bridge answered, including a refused-looking value, is the answer.

    The companion to the test above: a non-zero return has to survive too, so a property
    that returned a constant zero would not pass this pair.
    """
    from unittest.mock import patch

    from tests._fakejab import bind, node

    element, _bridge = bind(node("panel", name="p"))
    with patch.object(JABElement, "bridge", create=True,
                      new=type("B", (), {"getVisibleChildrenCount": lambda *a: 7})()):
        assert element.visible_children_count == 7
