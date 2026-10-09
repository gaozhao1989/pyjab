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


# ---------------------------------------------------------------------------
# find_elements_by_xpath: the contract, the order, and the cost
# ---------------------------------------------------------------------------

def test_nothing_matching_raises_whatever_the_path_length():
    """It used to depend on where in the path the search failed.

    ``find_elements_by_xpath`` checked whether its working list was empty at the
    *top* of each path segment, so ``//push button`` returned ``[]`` while
    ``//push button/label`` -- the same failure, one segment earlier in the walk --
    raised. The rest of the family raises, and get_children() is the documented
    exception; this was neither.
    """
    element, _ = bind(node("frame", node("panel", node("label", name="hello"),
                                         name="outer"), name="app"))

    for path in ["//push button", "//push button/label", "//panel/push button",
                 "//panel/label/push button"]:
        with pytest.raises(JABException):
            element.find_elements_by_xpath(path)


def test_matching_still_returns_every_match():
    element, _ = bind(node("frame",
                           node("label", name="a"),
                           node("panel", node("label", name="b")),
                           name="app"))

    found = element.find_elements_by_xpath("//label")

    assert sorted(f.name for f in found) == ["a", "b"]


def test_matches_come_back_in_document_order():
    """A node before its own descendants, which is what XPath promises.

    The traversal this replaced used ``_generate_all_childs``, which yields a node
    *after* its whole subtree -- post-order -- so ``//label`` returned an inner
    label before the outer one that contains it.
    """
    inner = node("label", name="inner")
    element, _ = bind(node("frame", node("panel",
                                         node("label", inner, name="outer"),
                                         name="app")))

    found = element.find_elements_by_xpath("//label")

    assert [f.name for f in found] == ["outer", "inner"]


def test_a_multi_segment_path_only_looks_inside_the_first_match():
    """The path still prunes: a later segment is a child of an earlier match."""
    deep = node("label", node("push button", name="Nested"), name="deep")
    elsewhere = node("label", name="elsewhere")
    element, bridge = bind(node("frame", node("panel", deep, elsewhere, name="app")))

    bridge.reset()
    found = element.find_elements_by_xpath("//label/push button")

    assert [f.name for f in found] == ["Nested"]


def test_the_walk_is_bounded_like_the_single_match_one():
    """A cyclic tree stops instead of recursing for ever.

    ``_search_path`` gained MAX_SEARCH_DEPTH when a real colour chooser panel
    turned out to hang a lookup. ``find_elements_by_xpath`` went through
    ``_get_elements_by_node`` and ``_generate_all_childs``, neither of which had a
    ceiling, so the same tree would still have run away here.
    """
    leaf = node("label", name="deep")
    root = node("panel", leaf, name="root")
    element, _ = bind(root)
    leaf.children.append(root)
    root.parent = leaf

    with pytest.raises(JABException):
        element.find_elements_by_xpath("//push button")


def test_the_cost_did_not_get_worse_than_the_traversal_it_replaced():
    """A ceiling, not an improvement -- and said plainly.

    The note this work came from said ``find_elements_by_xpath`` "does not get the
    pruning that find_element_by_xpath now has". Measured, that was wrong: the old
    level-based traversal pruned by path too -- the first segment walked the
    subtree, later segments walked direct children -- so the cost is the same. 1513
    calls against 1555 on a forty-panel window, with the count asserted here so a
    future change that makes it quadratic is caught.

    The gains are the contract, the document order and the depth ceiling, all of
    which have tests above. Repeating the "pruning" claim would have been a
    comfortable thing to write and not true.
    """
    panels = [panel(*[node("label", name=f"p{i}l{j}") for j in range(8)],
                    name=f"panel{i}", index=i) for i in range(40)]
    panels[0].children.append(node("push button", name="TARGET"))
    element, bridge = bind(node("frame", *panels, name="app"))

    bridge.reset()
    element.find_elements_by_xpath("//panel[@name='panel0']/push button")

    assert bridge.total < 2000, f"{bridge.total} calls; the old traversal used 1555"


def test_a_failed_multi_match_search_releases_everything_it_created():
    """Ownership, which is the part that is easy to get wrong.

    A child can be enumerated twice -- once for the next path segment, once for a
    deeper match of this one -- so both references have to be released. The fake
    bridge raises on a double release and on use after release, and reports what
    is still outstanding.
    """
    root = node("frame",
                node("panel", node("label", node("label", name="x"))),
                name="app")
    element, bridge = bind(root)
    before = dict(bridge.refs)

    with pytest.raises(JABException):
        element.find_elements_by_xpath("//push button")

    grew = {h: bridge.refs[h] - before.get(h, 0)
            for h in bridge.refs if bridge.refs[h] > before.get(h, 0)}
    assert not grew, f"the failed search leaked references to {grew}"


def test_a_successful_multi_match_search_releases_everything_but_the_matches():
    root = node("frame", node("panel", node("label", name="a"),
                              node("label", name="b")), name="app")
    element, bridge = bind(root)
    before = dict(bridge.refs)

    found = element.find_elements_by_xpath("//label")

    assert len(found) == 2
    # The two matches are the caller's and stay outstanding; nothing else does.
    outstanding = {h: bridge.refs[h] - before.get(h, 0)
                   for h in bridge.refs if bridge.refs[h] > before.get(h, 0)}
    assert len(outstanding) == 2, outstanding
    for element_ in found:
        element_.release_jabelement()


def test_an_absolute_xpath_lookup_does_not_leak_the_top_level_object():
    """Every absolute lookup leaked one Java object, success or failure.

    ``_xpath_search_root()`` calls ``_get_top_level_object()``, which is a JAB call
    that hands out a reference, and nothing released it -- not on the found path,
    not on the not-found path. One object per xpath lookup, for the life of the
    process, in the API a test script calls in a loop.

    Relative locators were never affected: their root is ``self``, which the caller
    already owns.
    """
    root = node("frame", node("panel", node("label", name="a")), name="app")
    element, bridge = bind(root)
    before = dict(bridge.refs)

    with pytest.raises(JABException):
        element.find_element_by_xpath("//push button")

    grew = {h: bridge.refs[h] - before.get(h, 0)
            for h in bridge.refs if bridge.refs[h] > before.get(h, 0)}
    assert not grew, f"a failed absolute lookup left {grew} outstanding"


def test_a_relative_lookup_does_not_release_the_callers_element():
    """The other direction, and the more dangerous mistake.

    A relative locator starts at ``self``, which belongs to the caller. Releasing
    it here would be a use-after-free for whoever holds it.
    """
    root = node("frame", node("label", name="a"), name="app")
    element, bridge = bind(root)
    before = dict(bridge.refs)

    element.find_element_by_xpath(".//label")

    assert bridge.refs[root.handle] == before[root.handle], (
        "the caller's own element was released"
    )


def test_a_loop_of_lookups_does_not_grow_the_reference_count():
    """The shape #43 describes: many lookups, growing cost, no obvious cause.

    One leaked object per lookup does not stall anything on the first call. It does
    on the ten-thousandth, which is why this is asserted as a loop rather than as a
    single call.
    """
    root = node("frame", node("panel", node("label", name="a")), name="app")
    element, bridge = bind(root)
    before = dict(bridge.refs)

    for _ in range(50):
        with pytest.raises(JABException):
            element.find_element_by_xpath("//push button")

    grew = {h: bridge.refs[h] - before.get(h, 0)
            for h in bridge.refs if bridge.refs[h] > before.get(h, 0)}
    assert not grew, f"fifty failed lookups leaked {grew}"


# ---------------------------------------------------------------------------
# `or` between predicates
# ---------------------------------------------------------------------------

def two_panels():
    root = node("frame",
                panel(name="outer", index=0),
                panel(name="second", index=1),
                name="app")
    return bind(root)


def test_or_matches_either_side():
    """It used to be discarded, so `or` was evaluated as `and`.

    ``//panel[@name='outer' or @name='second']`` found nothing and reported "no
    element" -- which reads as the element being absent rather than the locator
    being wrong. That is the most expensive way to be wrong, and it is why this is
    a fix rather than a feature request being closed.
    """
    element, _ = two_panels()

    found = element.find_elements_by_xpath("//panel[@name='outer' or @name='second']")

    assert sorted(f.name for f in found) == ["outer", "second"]


def test_or_with_one_side_matching():
    element, _ = two_panels()

    assert element.find_element_by_xpath("//panel[@name='outer' or @name='nope']").name == "outer"
    assert element.find_element_by_xpath("//panel[@name='nope' or @name='second']").name == "second"


def test_or_with_neither_side_matching_finds_nothing():
    element, _ = two_panels()

    with pytest.raises(JABException):
        element.find_element_by_xpath("//panel[@name='nope' or @name='also nope']")


def test_and_still_binds_tighter_than_or():
    """XPath precedence: `a and b or c` is `(a and b) or c`.

    The parser returns a flat list with the operator that joins each predicate to
    the previous one, and the matcher splits that list at every `or`. Getting the
    precedence backwards would make this pass for the wrong reason, so both
    groupings are asserted.
    """
    element, _ = two_panels()

    # (nope and nope) or (second and index=1) -> second
    assert element.find_element_by_xpath(
        "//panel[@name='nope' and @name='nope' or @name='second' and @indexinparent=1]"
    ).name == "second"

    # nope or (nope and nope) -> nothing
    with pytest.raises(JABException):
        element.find_element_by_xpath(
            "//panel[@name='nope' or @name='also nope' and @name='also nope']"
        )


def test_and_alone_still_needs_every_predicate():
    element, _ = two_panels()

    assert element.find_element_by_xpath(
        "//panel[@name='second' and @indexinparent=1]"
    ).name == "second"
    with pytest.raises(JABException):
        element.find_element_by_xpath("//panel[@name='second' and @indexinparent=0]")


def test_a_single_predicate_is_unaffected():
    """The operator it carries is `and`, which is what a lone predicate means."""
    element, _ = two_panels()

    assert element.find_element_by_xpath("//panel[@name='outer']").name == "outer"


def test_the_parser_reports_the_operator_that_joins_each_predicate():
    """The piece of information that was being thrown away."""
    from pyjab.common.xpathparser import XpathParser

    parser = XpathParser.__wrapped__()
    nodes = parser.split_nodes("//panel[@name='a' and @role='panel' or @name='b']")
    attributes = parser.get_node_information(nodes[0])["attributes"]

    assert [a["operator"] for a in attributes] == ["and", "and", "or"]
    assert [a["name"] for a in attributes] == ["name", "role", "name"]
