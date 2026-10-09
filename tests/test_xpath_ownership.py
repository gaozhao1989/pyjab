"""The ownership rule, checked the same way over both search modes.

``_search_path`` walks a path in one of two modes -- return the first match, or collect
every match. They were two functions, ``_search_path`` and ``_search_path_all``, until the
ownership bookkeeping below was written out twice. The rule they share is the one that is
easy to get wrong:

    Anything the search creates is either the caller's answer or the search's to
    release -- exactly one of the two, exactly once.

A node gets enumerated twice whenever it matches an early path segment and the rest of
the path does not fit under it, and Java Access Bridge hands out a fresh reference each
time, so both have to be released. ``tests/_fakejab.py`` counts them and raises on a
double release or a use after the last one.

This file is a battery rather than a set of named cases. It exists to be run unchanged
across a refactor of the traversal: the same table of trees and locators, asserting the
same matches and the same absence of outstanding references, so that merging two
implementations into one cannot quietly change either.

The table covers both modes, because the leak that was found in this code was in the
first-match path and a refactor of the pair has to answer for the other one too.
"""

from __future__ import annotations

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

from pyjab.common.exceptions import JABException, XpathParserException
from tests._fakejab import bind, node, panel, table

JABElement = _win32stubs.import_jabelement()


@pytest.fixture(autouse=True)
def no_real_pump(monkeypatch):
    """The message pump is Windows API; the fake bridge does not need it."""
    from pyjab.common.win32utils import Win32Utils

    with monkeypatch.context() as context:
        context.setattr(Win32Utils.__wrapped__, "pump_messages", lambda self: None)
        yield


def a_window():
    """A tree with the shapes the locators below need, and some that never match.

    Deliberately includes repeated roles at several depths and a panel whose subtree
    fails a later step, which is the case that enumerates a node twice.
    """
    return node(
        "frame",
        panel(
            node("label", name="Name:"),
            node("text", name=""),
            node("push button", name="OK"),
            panel(
                node("push button", name="Cancel"),
                node("push button", name="Help"),
                name="Buttons",
            ),
            name="Form",
        ),
        panel(
            node("label", name="Status"),
            name="Footer",
        ),
        table(2, 2, name="Grid"),
        name="app",
    )


#: Every locator this file exercises, with what each mode answers. A number is how many
#: elements come back; ``"raise"`` is a ``JABException`` for matching nothing and
#: ``"parse"`` an ``XpathParserException`` for a role that does not exist. Written as one
#: table so the same inputs can be replayed against a different implementation of the
#: traversal, which is what makes this a battery rather than a set of cases.
#:
#: The counts are not guesses and are worth reading as the contract of this XPath subset:
#: **the first step matches at any depth, and every step after it is a direct child.**
#: So ``//panel[@name='Form']//push button`` finds one, not three -- the second step is a
#: child of the panel, and only OK is -- and ``//panel[@name='Form']//push
#: button[@name='Help']`` finds none, because Help is a grandchild.
#:
#: ``/..`` counts are lower than the number of starting points because repeated ancestors
#: are returned once: three buttons have two parents between them.
LOCATORS = [
    ("//push button", 1, 3),
    ("//label", 1, 6),                       # two direct, four as table cells
    ("//panel[@name='Form']", 1, 1),
    ("//panel[@name='Form']//push button", 1, 1),
    ("//panel[@name='Form']/push button", 1, 1),
    ("//panel[@name='Form']/panel/push button", 1, 2),
    ("//panel[@name='Form']//push button[1]", 1, 1),
    ("//panel[@name='Form']//push button[2]", "raise", "raise"),
    ("//panel[@name='Form']//push button[9]", "raise", "raise"),
    ("//panel[@name='Form']//push button[@name='Help']", "raise", "raise"),
    ("//frame", "raise", "raise"),           # the root is not its own descendant
    ("//nosuchrole", "parse", "parse"),
    ("//panel[@name='Nothing']//push button", "raise", "raise"),
    (".//push button", 1, 3),
    ("//table//label", 1, 4),                # the table's own cells
    ("//push button/..", 1, 2),
    ("//push button/../..", 1, 2),
    ("//push button/../../..", 1, 1),        # up to the window, and no further
    ("//label | //push button", 1, 9),
]


def ids(rows):
    return [row[0] for row in rows]


def outstanding_since(before, bridge):
    """The references created and not released since *before* was taken."""
    return {handle: bridge.refs[handle] - before.get(handle, 0)
            for handle in bridge.refs
            if bridge.refs[handle] > before.get(handle, 0)}


def run(mode, locator):
    """Search a freshly bound window, returning the result or the exception raised.

    A fresh tree each time, because the point is what one search leaves behind.
    """
    element, bridge = bind(a_window())
    before = dict(bridge.refs)
    try:
        return getattr(element, mode)(locator), bridge, before
    except (JABException, XpathParserException) as exc:
        return exc, bridge, before


@pytest.mark.parametrize("locator, single, every", LOCATORS, ids=ids(LOCATORS))
def test_find_element_by_xpath_releases_everything_it_does_not_return(
        locator, single, every):
    """One answer comes back; nothing else stays outstanding."""
    result, bridge, before = run("find_element_by_xpath", locator)

    if isinstance(result, XpathParserException):
        assert single == "parse", f"{locator} is a parse error but should have matched"
    elif isinstance(result, JABException):
        assert single == "raise", f"{locator} raised but should have matched {single}"
    else:
        assert single == 1, f"{locator} matched but should have raised"
        # Exactly one outstanding reference: the answer the caller now owns.
        assert len(outstanding_since(before, bridge)) == 1, (
            f"{locator} left more than the returned element outstanding"
        )
        result.release_jabelement()

    assert not outstanding_since(before, bridge), (
        f"{locator} left references outstanding after everything was released"
    )


@pytest.mark.parametrize("locator, single, every", LOCATORS, ids=ids(LOCATORS))
def test_find_elements_by_xpath_releases_everything_but_the_matches(
        locator, single, every):
    """Every match comes back; nothing else stays outstanding.

    The mode the single-match search never exercised, and the one a shared walk has to
    keep answering correctly.
    """
    result, bridge, before = run("find_elements_by_xpath", locator)

    if isinstance(result, XpathParserException):
        assert every == "parse", f"{locator} is a parse error but should have matched"
    elif isinstance(result, JABException):
        assert every == "raise", f"{locator} raised but should have matched {every}"
    else:
        assert isinstance(every, int), f"{locator} matched but should have raised"
        assert len(result) == every, (
            f"{locator} matched {len(result)}, expected {every}"
        )
        # Exactly as many outstanding references as matches, and no more.
        assert len(outstanding_since(before, bridge)) == len(result), (
            f"{locator} left references outstanding beyond its {len(result)} matches"
        )
        for one in result:
            one.release_jabelement()

    assert not outstanding_since(before, bridge), (
        f"{locator} left references outstanding after everything was released"
    )


@pytest.mark.parametrize("locator, single, every", LOCATORS, ids=ids(LOCATORS))
def test_the_two_modes_agree_about_what_matches(locator, single, every):
    """The single-match search returns one of the elements the plural one lists.

    Both modes exist because they answer different questions, but they have to be
    answering about the same tree with the same rules -- and after the traversal
    becomes one function they have to keep agreeing.
    """
    if every in ("raise", "parse") or single in ("raise", "parse"):
        return

    every_result, _b1, _before1 = run("find_elements_by_xpath", locator)
    one_result, _b2, _before2 = run("find_element_by_xpath", locator)

    listed = [(item.role_en_us, item.name) for item in every_result]
    assert (one_result.role_en_us, one_result.name) in listed, locator

    for item in every_result:
        item.release_jabelement()
    one_result.release_jabelement()
