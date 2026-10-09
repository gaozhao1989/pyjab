"""One contract for ``find_*``, whichever object it is called on.

``JABDriver`` and ``JABElement`` share 27 method names, and the find family made 8 of
them behave differently for the same arguments. Searching for the root window's own
name, role, description or states returned the root from the driver and raised from an
element:

    driver.find_element_by_name("PyjabTestApp")   -> the root element
    element.find_element_by_name("PyjabTestApp")  -> JABException

Both are defensible on their own. Having both is not, and the driver's version is the
one that has to go, for a reason that is not about tidiness: the driver owns its
``root_element`` and hands it out to nobody, while the docstring on every one of these
methods says the caller owns what comes back. A caller could not tell which of the two
it had, and so could not know whether to call ``release_jabelement``.

The plural forms were worse in a quieter way: ``find_elements_by_name(root_name)``
returned ``[root]``, so the root was reported as one of the window's own elements,
which it is not -- a window is not its own descendant.

Removed rather than unified the other way. Making an element search include itself
would change every path traversal, and the root is already reachable as
``driver.root_element``, which says what it is.

These tests pin the agreement. The ones that matter most are the ownership pair: no
find call may ever return the driver's root.
"""

from __future__ import annotations

import pytest

import _win32stubs

from pyjab.common.exceptions import JABException
from tests._fakejab import bind, node, panel

# Through the helpers, not imported directly: both modules raise ImportError at
# module scope off Windows so that user code fails with a sentence rather than a
# traceback, and a test file importing them plainly cannot be collected on macOS.
JABElement = _win32stubs.import_jabelement()
JABDriver = _win32stubs.import_jabdriver()


class _StandInDriver:
    """Just ``root_element``, which is all the find family reads.

    ``JABDriver.__init__`` launches a Java process and binds a window, so the methods
    are called unbound against this instead.
    """

    def __init__(self, root_element) -> None:
        self.root_element = root_element


def a_window():
    """A window named 'app' whose own role, name and description are all findable.

    The description is left empty on purpose: that is the value that made
    ``find_element_by_description("")`` return the root, because the root's own
    description was empty too.
    """
    root = node("frame", panel(node("label", name="Save")), name="app")
    element, bridge = bind(root)
    return element, bridge


#: Each name is (the attribute a locator would match, the value that matches the root).
#: These four are exactly what the driver special-cased. Two of them raise on both
#: sides and two of them match the root's *children* -- the fake window's elements all
#: share an empty description and the same states -- which is why the assertions below
#: compare the two results rather than expecting a particular one.
ROOT_ATTRIBUTES = [
    ("name", "app"),
    ("role", "frame"),
    ("description", ""),
    ("states", ["enabled", "showing"]),
]


class Raised:
    """A result, so that "both raised" can be compared like anything else."""

    def __init__(self, exc):
        self.exc = exc

    def __eq__(self, other):
        return isinstance(other, Raised) and type(self.exc) is type(other.exc)

    def __repr__(self):
        return f"raised {type(self.exc).__name__}"


def outcome(callable_, *args):
    try:
        return callable_(*args)
    except JABException as exc:
        return Raised(exc)


def names_of(result):
    if isinstance(result, Raised):
        return result
    if isinstance(result, list):
        return [(element.role_en_us, element.name) for element in result]
    return (result.role_en_us, result.name)


@pytest.mark.parametrize("attribute, locator", ROOT_ATTRIBUTES)
def test_the_driver_and_the_element_agree(attribute, locator):
    """The whole point: same name, same arguments, same answer.

    Searching for the window's own name or role returned the root from the driver and
    raised from an element. Two reasonable behaviours, and having both is what made the
    ownership question unanswerable.
    """
    element, _bridge = a_window()
    driver = _StandInDriver(element)

    from_driver = outcome(
        getattr(JABDriver, f"find_element_by_{attribute}"), driver, locator
    )
    from_element = outcome(
        getattr(JABElement, f"find_element_by_{attribute}"), element, locator
    )

    assert names_of(from_driver) == names_of(from_element)


@pytest.mark.parametrize("attribute, locator", ROOT_ATTRIBUTES)
def test_the_driver_and_the_element_list_the_same_things(attribute, locator):
    """The plural form, where the difference was quietest.

    ``find_elements_by_name(root_name)`` returned ``[root]`` from the driver while an
    element raised -- so the window was reported as one of its own elements, which it
    is not: a window is not its own descendant.
    """
    element, _bridge = a_window()
    driver = _StandInDriver(element)

    from_driver = outcome(
        getattr(JABDriver, f"find_elements_by_{attribute}"), driver, locator
    )
    from_element = outcome(
        getattr(JABElement, f"find_elements_by_{attribute}"), element, locator
    )

    assert names_of(from_driver) == names_of(from_element)


def test_searching_for_an_empty_description_no_longer_returns_the_root():
    """The case that was reachable without meaning to be.

    ``"" == root.description`` was true, so asking for elements that have no
    description -- a reasonable thing to filter on -- returned the window itself.
    """
    element, _bridge = a_window()
    driver = _StandInDriver(element)

    result = outcome(JABDriver.find_element_by_description, driver, "")

    assert names_of(result) != ("frame", "app")
    assert isinstance(result, JABElement), "the children still match, which is right"


def test_a_child_is_still_found_by_the_driver():
    """The removal must not take the ordinary case with it."""
    element, _bridge = a_window()
    driver = _StandInDriver(element)

    found = JABDriver.find_element_by_name(driver, "Save")

    assert found.name == "Save"


@pytest.mark.parametrize("attribute, locator", ROOT_ATTRIBUTES)
def test_no_find_ever_returns_the_drivers_root(attribute, locator):
    """The ownership property, which is the reason this was changed at all.

    Everything these methods return has to be the caller's to release. The root is
    not: the driver holds it for its lifetime, and releasing it would take a reference
    away from an object still in use.
    """
    element, _bridge = a_window()
    driver = _StandInDriver(element)

    returned = []
    for name in (f"find_element_by_{attribute}", f"find_elements_by_{attribute}"):
        result = outcome(getattr(JABDriver, name), driver, locator)
        if isinstance(result, Raised):
            continue
        returned.extend(result if isinstance(result, list) else [result])

    assert element not in returned, (
        f"find_*_by_{attribute} handed out the driver's own root element"
    )


def test_the_driver_adds_nothing_to_what_the_element_finds():
    """A guard over the whole family, so a new special case becomes a failing test.

    The eight methods that differed were written one at a time and nobody noticed the
    set of them. This compares every shared find method on a probe that matches the
    root, which is the input the special cases reacted to -- so the shape is checked
    rather than the eight cases.

    Behaviour rather than source, because counting occurrences of ``root_element`` in
    the text of a method also counts the ones that merely pass it on.
    """
    element, _bridge = a_window()
    driver = _StandInDriver(element)

    compared = []
    for name in sorted(dir(JABDriver)):
        if not name.startswith(("find_element_by_", "find_elements_by_")):
            continue
        if not hasattr(JABElement, name):
            continue
        attribute = name.split("_by_", 1)[1]
        locator = dict(ROOT_ATTRIBUTES).get(attribute)
        if locator is None:
            continue
        compared.append(name)

        from_driver = outcome(getattr(JABDriver, name), driver, locator)
        from_element = outcome(getattr(JABElement, name), element, locator)
        assert names_of(from_driver) == names_of(from_element), name

    assert len(compared) >= 8, f"only compared {compared}"
