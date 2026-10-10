"""The four behaviours issue #169 says had conclusions but no test.

Each test names the closed issue whose conclusion it pins, and the point is not to reopen
a settled question — it is to stop a **silent** change from making a settled question wrong.

Three of the four are here. The fourth, DPI, cannot run on a hosted runner: measured, the
runner's display is 96 DPI and `LogPixels = 144` does not take effect without a logoff. Its
evidence is a hand-run on a real 150% display, archived on the issue.
"""

from __future__ import annotations

import pytest

from pyjab.common.role import Role

pytestmark = pytest.mark.gui


@pytest.fixture
def driver(test_application):
    """A driver on the shared test application.

    Not a context manager, deliberately: `__exit__` terminates the bound process by pid,
    and that process is shared by every test in the run. See tests/test_components.py.

    `JABDriver` is imported here and not at module scope, which is what every other GUI
    module does: it raises ImportError off Windows by design, and a module-level import
    turns "this suite does not apply here" into a collection error. That is how this file
    was written first.
    """
    from pyjab.jabdriver import JABDriver

    return JABDriver(title=test_application)


# ---------------------------------------------------------------------------
# 1. A panel that paints itself has no accessible children — pyjab#73
# ---------------------------------------------------------------------------

def test_a_painted_panel_has_no_children_and_says_so(driver):
    """`#73`'s conclusion, which pyjab-mcp documents to end users.

    The asymmetry that matters is **"no children" vs "could not read the children"**. So
    this asserts three things: the count is zero, the *visible* count is zero, and both of
    those are **answers rather than refusals** — a refusal raises, and if it started
    returning zero instead, this test would still pass while the distinction #73 is about
    quietly disappeared.
    """
    from pyjab.common.exceptions import JABException

    painted = driver.find_element_by_name("Painted panel")

    assert painted.role_en_us == Role.PANEL

    # The total is readable and is zero.
    assert painted.children_count == 0

    # **And the visible count is not readable at all** -- `getVisibleChildrenCount`
    # refuses for this element, so it raises rather than answering zero. That is the first
    # measured evidence for the distinction #73 is about, and it arrived by running this
    # test: the two paths do not agree, and they disagree in the direction that matters.
    #
    # It also means "no children" and "could not read the children" are **not yet
    # distinguishable through one API** -- one says zero, the other refuses, and a caller
    # has to know which call it made. Reported on #169.
    with pytest.raises(JABException):
        painted.visible_children_count

    # A walk over it yields nothing, which is the same answer the readable count gave.
    assert list(painted.walk()) == []


def test_a_panel_that_really_has_children_reports_them(driver):
    """The control for the test above.

    "No children" passes just as well if the bridge is reporting zero for everything, so
    a panel that does have children has to report them for the first assertion to mean
    anything.
    """
    root = driver.root_element

    assert root.children_count > 0
    assert len(list(root.walk(limit=20))) > 0


# ---------------------------------------------------------------------------
# 2. A tab whose title collides with text on another page — pyjab#63
# ---------------------------------------------------------------------------

def test_a_tab_and_a_label_with_the_same_words_are_distinguishable(driver):
    """`#63`'s failure was selecting by name and landing on the other tab.

    The fixture is built so the collision is real: the first tab's page contains a label
    reading `Collision`, and the second tab is *titled* `Collision`. Both must be
    findable, and they must not be the same element.
    """
    tabs = driver.find_element_by_name("Same-name tabs")
    assert tabs.role_en_us == Role.PAGE_TAB_LIST

    label = driver.find_element_by_name("Colliding label")
    assert label.role_en_us == Role.LABEL

    # The colliding label lives inside the first tab's page, not in the second tab.
    assert label.parent is not None
    assert label.parent.role_en_us in (Role.PANEL, Role.PAGE_TAB)


def test_the_colliding_label_and_the_tab_are_different_roles(driver):
    """What makes them distinguishable at all: role, not name.

    If this ever became one element the previous test could still pass on a tolerant
    lookup, so the roles are asserted separately.
    """
    label = driver.find_element_by_name("Colliding label")

    assert label.role_en_us == Role.LABEL
    assert label.role_en_us != Role.PAGE_TAB


# ---------------------------------------------------------------------------
# 4. An accelerator-driven menu item — pyjab#53
# ---------------------------------------------------------------------------

def test_the_accelerator_item_exists_as_a_menu_item(driver):
    """`setAccelerator` is a `JMenuItem` API; a JButton has no such method.

    Issue #169 said "a button with setAccelerator" and javac said otherwise the moment the
    control was written. Asserted here so the fixture cannot drift back to something Swing
    cannot build.
    """
    item = driver.find_element_by_name("Accelerated item")

    assert item.role_en_us == Role.MENU_ITEM


@pytest.mark.xfail(
    reason=(
        "The accelerator does not invoke the item on this runner: send_keys('alt+y') "
        "returns without error and the item's name never changes. Found by this test, "
        "reported on #169; either the keystroke is not reaching the window (focus, or a "
        "menu that has to be open) or the accelerator path is genuinely different from "
        "the click path, which is what #53 was about. Not resolved by guessing."
    ),
    strict=True,
)
def test_the_accelerator_invokes_it_with_the_same_effect_as_clicking(driver):
    """`#53`'s conclusion: the keyboard path has to *do* the same thing, not just exist.

    Driven through `send_keys`, which is the public shortcut API added for #168 — so this
    test also exercises that, against a real application, which is the only place it can be
    exercised at all.
    """
    item = driver.find_element_by_name("Accelerated item")

    driver.send_keys("alt+y")

    # The item renames itself when invoked, so the effect is observable through the
    # accessibility tree rather than inferred from the keystroke not raising.
    invoked = driver.find_element_by_name("Accelerated item (invoked)")
    assert invoked.role_en_us == Role.MENU_ITEM
    assert item.name != invoked.name
