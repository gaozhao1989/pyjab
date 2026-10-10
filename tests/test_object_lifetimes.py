"""Where each JAB reference goes, for the call sites that can be exercised here.

``tools/check_jab_object_sites.py`` is the mechanical half of the audit the project's
notes call P1-2: it fails when a call that hands out a Java object is added or removed
without somebody recording where its reference goes. This file is the other half, for
the sites that can actually be run.

Two leaks have been found in this codebase, and both were found by these two things
rather than by reading:

* ``_xpath_search_root()`` took a reference on every absolute xpath lookup and released
  it nowhere -- one Java object per lookup, in a path every user takes. Covered by
  ``tests/test_xpath_ownership.py``.
* ``init_jab()`` called ``getTopLevelObject`` to turn a vmid and a context into an hwnd
  and never released the result -- one object per driver, so far quieter, and it was
  ``check_jab_object_sites.py`` that surfaced it after a hand inventory of the call sites
  missed that call twice.

Neither is an explanation of issue #43, and neither is offered as one. What they show is
that the rule is broken here in ways reading does not catch.

The driver-side sites cannot be exercised: they run inside ``JABDriver.__init__``, which
starts a Java process and binds a window. Those are called unbound against a stand-in,
which is enough to reach ``init_jab``'s reference handling and is the same trick
``tests/test_screenshots.py`` uses.
"""

from __future__ import annotations

import pytest

import _win32stubs

from tests._fakejab import bind, node, panel

JABDriver = _win32stubs.import_jabdriver()
JABElement = _win32stubs.import_jabelement()


class StandInDriver:
    """Enough of a JABDriver for ``init_jab``, with the fake bridge behind it.

    Every attribute ``init_jab`` touches, and no ``__init__`` -- which is the point:
    the real one launches a process.
    """

    def __init__(self, bridge, vmid, accessible_context, root_element):
        self.bridge = bridge
        self.vmid = vmid
        self.accessible_context = accessible_context
        self._bridge_dll = ""
        self._timeout = 5
        self.title = "app"
        self.hwnd = None
        self.pid = None
        self.root_element = None

        class _Logger:
            def info(self, *_a, **_k):
                pass

            def warning(self, *_a, **_k):
                pass

        self.logger = _Logger()

        class _Service:
            def load_library(self, _path=""):
                return bridge

        self.serv = _Service()
        self._root_element = root_element

    # The real methods for the other two reference-producing sites, so their reference
    # handling is exercised rather than described.
    _get_accessible_context_from_hwnd = JABDriver._get_accessible_context_from_hwnd
    _focused_context = JABDriver._focused_context
    get_focused_element = JABDriver.get_focused_element

    # The stubs init_jab needs from the real class. _pump_messages is overridden so
    # that no part of the real Windows message pump is reached.
    def _pump_messages(self):
        pass

    def _is_java_window(self, _hwnd):
        return True

    def get_pid_from_hwnd(self):
        return 4242

    def wait_java_window_by_title(self, title, timeout=5):
        raise AssertionError("the vmid path must not wait for a title")

    def _get_accessible_context_from_hwnd(self, _hwnd):
        raise AssertionError("the vmid path must not re-derive the context")


def outstanding(before, bridge):
    return {handle: bridge.refs[handle] - before.get(handle, 0)
            for handle in bridge.refs
            if bridge.refs[handle] > before.get(handle, 0)}


@pytest.fixture
def a_driver_built_from_a_vmid():
    """A stand-in ready to run init_jab down its vmid-and-context branch."""
    element, bridge = bind(node("frame", panel(node("label", name="x")), name="app"))

    # getTopLevelObject hands back the root's handle; the real bridge does the same.
    bridge.getHWNDFromAccessibleContext = lambda vmid, context: 0x1234

    driver = StandInDriver(bridge=bridge, vmid=element.vmid,
                           accessible_context=element.accessible_context,
                           root_element=element)
    return driver, bridge, element


def test_init_jab_releases_the_top_level_object_it_asks_for(
        a_driver_built_from_a_vmid):
    """The second leak. One Java object per driver, on the vmid construction path.

    getTopLevelObject hands out a reference that is used exactly once, to turn the vmid
    and context into an hwnd. Nothing released it, so every driver built this way left
    one behind -- quieter than the per-lookup leak, and invisible to reading, which is
    why the checker found it rather than a person.
    """
    driver, bridge, _element = a_driver_built_from_a_vmid
    before = dict(bridge.refs)

    JABDriver.init_jab(driver)

    assert bridge.calls["getTopLevelObject"] == 1, "the branch under test did not run"
    assert not outstanding(before, bridge), (
        "init_jab left the top-level object it took outstanding"
    )


def test_init_jab_still_resolves_the_hwnd_it_was_asked_for(
        a_driver_built_from_a_vmid):
    """Releasing it must not break the thing it was taken for."""
    driver, _bridge, _element = a_driver_built_from_a_vmid

    JABDriver.init_jab(driver)

    assert driver.hwnd == 0x1234
    assert driver.pid == 4242
    assert driver.root_element is not None


def test_the_release_happens_after_the_hwnd_lookup(
        a_driver_built_from_a_vmid):
    """Order matters: the reference has to be alive while it is being used.

    Releasing before the lookup would be a use-after-free rather than a leak, and the
    fake bridge raises on that -- so this checks the ordering is not merely tidy by
    making the lookup record whether the object was still live when it ran.
    """
    driver, bridge, _element = a_driver_built_from_a_vmid
    seen = {}

    def lookup(vmid, context):
        seen["live"] = bridge.refs[bridge._value(context)] > 0
        return 0x1234

    bridge.getHWNDFromAccessibleContext = lookup

    JABDriver.init_jab(driver)

    assert seen["live"] is True, "the context was released before it was used"


def test_a_child_the_search_does_not_keep_is_the_callers(
        a_driver_built_from_a_vmid):
    """The other end of the rule, at the site that hands out the most references.

    _generate_childs_from_element yields children, and get_children() documents that the
    caller owns them. Checked here as well as in the traversal tests because it is the
    site with the most chances to be wrong: one reference per child per call.
    """
    _driver, bridge, element = a_driver_built_from_a_vmid
    before = dict(bridge.refs)

    children = element.get_children()

    assert len(outstanding(before, bridge)) == len(children), (
        "get_children should leave exactly one outstanding reference per child"
    )
    for child in children:
        child.release_jabelement()
    assert not outstanding(before, bridge)


# ---------------------------------------------------------------------------
# The other two sites that hand out a reference
# ---------------------------------------------------------------------------
#
# tools/check_jab_object_sites.py records seven call sites and says which are exercised
# and which were only read. Two were only read, so the checker's own note said so --
# which is honest and not good enough. Both can be reached with the stand-in above, and
# now are, so the note can say the same thing about all seven.

def test_the_window_context_is_the_callers_reference(
        a_driver_built_from_a_vmid):
    """``_get_accessible_context_from_hwnd`` hands out one reference.

    Its only caller is ``init_jab``, which stores it as the driver's own context and
    holds it for the driver's lifetime. So the assertion is that exactly one reference
    comes back -- not zero, which would mean it was released out from under the driver.
    """
    driver, bridge, _element = a_driver_built_from_a_vmid
    before = dict(bridge.refs)

    _context, vmid = JABDriver._get_accessible_context_from_hwnd(driver, 0x1234)

    assert vmid == bridge.vmid
    assert len(outstanding(before, bridge)) == 1, (
        "the window context should come back as exactly one reference for the caller"
    )


def test_focus_with_nothing_focused_leaves_no_reference(a_driver_built_from_a_vmid):
    """The path that must not leak what it did not take.

    ``getAccessibleContextWithFocus`` reports "nothing focused" with a falsy return --
    an ordinary answer about a window, not a failure. Nothing was handed out on that
    path, so nothing may be left outstanding, and the out-parameters must not be read.
    """
    driver, bridge, _element = a_driver_built_from_a_vmid
    bridge.focus = None
    before = dict(bridge.refs)

    assert JABDriver._focused_context(driver) is None

    assert not outstanding(before, bridge), (
        "an unfocused window left a reference outstanding"
    )


def test_focus_hands_the_caller_one_reference(a_driver_built_from_a_vmid):
    """And when something is focused, it is the caller's -- as get_focused_element's
    contract says."""
    driver, bridge, _element = a_driver_built_from_a_vmid
    bridge.focus = bridge.root
    before = dict(bridge.refs)

    focused = JABDriver._focused_context(driver)

    assert focused is not None
    vmid, _context = focused
    assert vmid == bridge.vmid
    assert len(outstanding(before, bridge)) == 1


def test_get_focused_element_gives_the_caller_a_releaseable_element(
        a_driver_built_from_a_vmid):
    """The end of that path: the element the caller gets is theirs to release."""
    driver, bridge, _element = a_driver_built_from_a_vmid
    bridge.focus = bridge.root
    before = dict(bridge.refs)

    element = JABDriver.get_focused_element(driver)

    assert element is not None
    assert len(outstanding(before, bridge)) == 1
    element.release_jabelement()
    assert not outstanding(before, bridge)
