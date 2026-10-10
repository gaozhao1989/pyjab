"""Two counts of children, named, because they come from different calls.

`children_count` is the **total**, from the accessibility context info; `visible_children_count`
is the count the bridge calls visible. Both are correct and they differ whenever an element has
hidden children.

**A walk uses `children_count`, not the visible one** -- this file said otherwise when it was
written, and a measurement said otherwise in turn. See #179.

The tests here pin the distinction and the reason `as_record()` carries only one of them.
"""

from __future__ import annotations

import pytest

import _win32stubs  # noqa: F401

from pyjab.common.exceptions import JABException

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


def test_a_refused_visible_count_raises_rather_than_reporting_zero():
    """A refused call is not an answer of zero, and this is where that matters most.

    It is the same distinction issue #73 is about: a canvas-drawn panel genuinely has no
    children, and a failed read has no children either, and those must not look alike.
    """
    from unittest.mock import patch

    from tests._fakejab import bind, node

    element, _bridge = bind(node("panel", name="p"))
    with patch.object(JABElement, "bridge", create=True,
                      new=type("B", (), {"getVisibleChildrenCount": lambda *a: 0})()):
        with pytest.raises(JABException):
            element.visible_children_count
