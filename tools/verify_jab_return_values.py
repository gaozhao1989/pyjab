"""Measure what the 14 JAB symbols behind issue #195 return on a real JVM.

``jabfixedfunc.SIGNATURES`` carries an ``errorcheck`` flag per row, and
``_fix_bridge_function`` installs :meth:`JABFixedFunc._check_error` as ctypes' ``errcheck``
when it is set. The hook **raises ``RuntimeError`` on a falsy result**. Every row is
deliberately unarmed, because arming one is not a tidy-up:

* it turns a falsy return into an exception **from inside the call**, so the
  ``if not result:`` checks written at the call sites become unreachable and the
  ``except JABException`` blocks in ``jabelement.py`` / ``jabdriver.py`` stop catching — a
  recoverable lookup miss becomes an uncaught ``RuntimeError``;
* it only covers a falsy ``0``, and several JAB calls answer with a **truthy ``-1``**
  instead, which passes straight through.

So arming is per row and gated on a measurement: **does this symbol return falsy during
ordinary use on a real JVM?** If none of the fourteen does, the rows are safe to arm. If some
do, those are the rows that must not be armed without handling, and the raw value printed
below is what says which.

Each candidate is driven through the code that calls it — the tool finds a widget, invokes
the pyjab method whose body contains the call, and records **the arguments the call actually
arrived with**. It then makes the same call directly, on those arguments, and prints the raw
return, and separately records what the pyjab method did with it, so a ``JABException``
raised at a call site cannot hide the value underneath. That structure is the one
``tools/verify_visible_children_count.py`` used to settle #191.

A symbol is only reported when its call site was really exercised: the bridge is wrapped for
the duration of each pyjab call and the wrapper counts the hits, so "I read the source and it
must have been called" is not accepted as reach. A symbol that was not reached is printed as
``not reached`` with the reason, and the run is ``INCONCLUSIVE`` rather than a partial sweep
reported as a pass. The reasons are told apart: **"no such component in this application"**
(a real answer about the application) reads differently from **"the harness could not drive
it"** (a problem with this tool).

Controls, because an empty result means nothing without them:

* a **direct** ``getAccessibleContextInfo`` on the root element, which must return a truthy
  value -- if that fails then nothing below it is measuring a working bridge;
* the **childless "Painted panel"**, where ``getVisibleChildren``'s own return is expected
  to be falsy -- the case #191 already measured, included so this run says out loud what a
  falsy return looks like on a real call. It is a control, not one of the fourteen: if it
  does **not** come back falsy then this run produced no falsy value at all, and "none of
  the candidates returned falsy" would read the same whether that is because none of them
  does or because this JVM never answers ``0``. So the control failing makes the run
  ``INCONCLUSIVE`` too;
* a note, printed with the summary, that ``-1`` is **truthy** and therefore passes a falsy
  test straight through: the contract several of these symbols document (``-1`` on error)
  would not be caught by arming even where the documented sentinel is real.

**Each symbol is measured in its own process, on a wall-clock budget.** That is not
decoration: the first version of this tool ran the whole sweep in one process and died on
its first dispatch -- it sat for fifty minutes inside a JAB call and the run was lost, with
nothing to say which symbol blocked. A budget the *parent* enforces is the only kind that
works, because only the parent can kill a call parked inside the DLL. So the parent
compiles, launches and waits for the window with Win32 alone, then spawns one child per
symbol (``--symbol``, which is internal) and reads one JSON row back. A child that does not
report is printed as ``not reached: the harness could not drive it`` with the budget it
missed, and the run is ``INCONCLUSIVE`` -- which is a fact worth having, where a hang was
not. The children detach rather than use ``JABDriver`` as a context manager: ``__exit__``
SIGTERMs the bound pid, and the application belongs to the parent.

Windows, a JDK and an interactive desktop. Dispatched, never run locally:

    gh workflow run windows-gui.yml -f task=jab-return-values
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_SRC = REPO_ROOT / "tests" / "java"
JAVA_CLASSES = REPO_ROOT / "tests" / "java-classes"
APP_CLASS = "PyjabTestApp"
WINDOW_TITLE = "PyjabTestApp"

#: The JAB header's documented error answer for the calls that have one. Named rather than
#: written inline because seeing it in the output would mean something quite different from
#: seeing ``0``: it is truthy, so a falsy test never notices it.
DOCUMENTED_ERROR = -1

#: Where each symbol is reached from, and what the code around the call does with the
#: result. This is the "check what the call sites around it expect" half of the decision:
#: ``checks`` means the site reads the return itself (so arming would make that check
#: unreachable), ``ignores`` means it reads nothing and would start raising on a falsy
#: return. #195 counts seven of the former and eight of the latter.
CALL_SITES: Dict[str, Tuple[str, str]] = {
    "getAccessibleContextInfo": ("jabelement.py:632", "checks"),
    "getAccessibleTextInfo": ("jabelement.py:664", "checks"),
    "getAccessibleTextRange": ("jabelement.py:680", "checks"),
    "getAccessibleTableCellInfo": ("jabelement.py:810", "checks"),
    "getVisibleChildren": ("jabelement.py:988", "checks"),
    "getTopLevelObject": ("jabelement.py:597, jabdriver.py:301", "checks"),
    "setTextContents": ("jabelement.py:1618", "checks"),
    "getAccessibleChildFromContext": ("jabelement.py:376", "ignores"),
    "getVersionInfo": ("jabdriver.py:374", "ignores"),
    "getAccessibleContextFromHWND": ("jabdriver.py:354", "ignores"),
    "getHWNDFromAccessibleContext": ("jabdriver.py:304", "ignores"),
    "requestFocus": ("jabelement.py:530", "ignores"),
    "getAccessibleActions": ("jabelement.py:1005", "ignores"),
    "doAccessibleActions": ("jabelement.py:1036", "ignores"),
}

#: The order the report prints in. Drivable first, so a run that dies part way through has
#: the most informative lines in front of it.
SYMBOLS = (
    "getAccessibleContextInfo",
    "getAccessibleTextInfo",
    "getAccessibleTextRange",
    "getAccessibleTableCellInfo",
    "getVisibleChildren",
    "getTopLevelObject",
    "setTextContents",
    "getAccessibleChildFromContext",
    "getVersionInfo",
    "getAccessibleContextFromHWND",
    "getHWNDFromAccessibleContext",
    "requestFocus",
    "getAccessibleActions",
    "doAccessibleActions",
)

#: The widget names the application defines. Read from tests/java/PyjabTestApp.java.
LABEL_NAME = "A Label"
TEXT_FIELD_NAME = "1122233455"
TABLE_NAME = "Sports table"
BUTTON_NAME = "Middle button"
BUTTON_DISABLER_NAME = "Disable middle button"
BUTTON_ENABLER_NAME = "Enable middle button"
MAIN_PANEL_NAME = "Main panel"
#: Issue #191's childless self-painting panel: the positive control for a falsy return.
PAINTED_NAME = "Painted panel"

#: What the text field holds at startup.
TEXT_FIELD_TEXT = "1122233455"


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------

def describe(value, raw_type: Optional[str] = None) -> str:
    """The raw value and its type, in one string, without letting a repr raise.

    ``raw_type`` is passed when the value came back from a child process by name: the object
    itself does not cross that boundary, and its type is what keeps ``1`` and ``True``
    distinguishable in the report.
    """
    name = raw_type or type(value).__name__
    try:
        rendered = repr(value)
    except Exception as error:                            # noqa: BLE001 - reported
        rendered = f"<unreprable: {type(error).__name__}: {error}>"
    return f"{rendered} ({name})"


def is_falsy(value) -> bool:
    """Whether ``_check_error`` would raise on this value.

    The hook tests ``if not result:``, and that is the whole question -- so this asks the
    same question of the same object. A value whose truth cannot be taken (a bare ctypes
    instance, say) is reported as falsy rather than guessing, and the printing shows it.
    """
    try:
        return not value
    except Exception:                                     # noqa: BLE001 - a ctypes instance
        return True


class Verdict(object):
    """One direct call, and what the pyjab path did with the same call site.

    ``arguments`` is the reach: it names the widget whose action carried the call, so a
    reader can tell "this really ran" from "this was expected to run".

    ``candidate`` is False for the one probe that is a control rather than a row: the
    childless panel. Its value is evidence about what a falsy return looks like, but it is
    not one of the fourteen symbols #195 is deciding about, and letting it into the summary
    would make "getVisibleChildren returned falsy" mean two different things.
    """

    def __init__(self, symbol: str, arguments: str, candidate: bool = True) -> None:
        self.symbol = symbol
        self.arguments = arguments
        self.candidate = candidate
        self.raw = None
        #: The type of ``raw`` when it arrived from a child process by name. The object
        #: itself does not cross that boundary, so the report prints this instead.
        self.raw_type: Optional[str] = None
        self.error: Optional[str] = None
        self.outcome: Optional[str] = None

    @property
    def falsy(self) -> bool:
        return self.error is None and is_falsy(self.raw)

    @property
    def measured(self) -> bool:
        return self.error is None

    def raw_line(self) -> str:
        if self.error is not None:
            return f"raw {self.symbol} -> raised {self.error}"
        label = "falsy?" if self.falsy else "nonzero?"
        return f"raw {self.symbol} -> {describe(self.raw, self.raw_type)}  {label}"


class Reach:
    """Whether one pyjab call site can be driven, and how.

    ``reached`` False is deliberately two different things, kept apart in the text:

    * ``"no such component in this application"`` -- the application has nothing that
      carries this call, which is a fact about the application;
    * anything else -- this tool could not drive it, which is a fact about the harness.
    """

    def __init__(self, reached: bool, note: str,
                 no_component: bool = False) -> None:
        self.reached = reached
        self.note = note
        self.no_component = no_component


def raw_measure(bridge, symbol: str, call) -> Tuple[object, Optional[str]]:
    """Call ``call`` -- which makes the raw call -- and report only what came back.

    Separated from any pyjab wrapper on purpose: a wrapper's ``JABException`` would replace
    the value being measured with an exception, which is exactly the masking this tool
    exists to avoid. The traceback location is kept because the first two dispatches each
    died on a bug *in this file* that the bare message could not name -- one word in a field
    name, and a ``KeyError`` from the wrong mapping -- and a run costs twenty minutes.
    """
    try:
        return call(), None
    except Exception as error:                            # noqa: BLE001 - reported
        where = traceback.extract_tb(error.__traceback__)[-1]
        return None, (f"{type(error).__name__}: {error} "
                      f"(at {Path(where.filename).name}:{where.lineno} in "
                      f"{where.name})")


def outcome(call) -> str:
    """What a pyjab method returned or raised, in one line, without propagating."""
    try:
        return f"returned {call()!r}"
    except Exception as error:                            # noqa: BLE001 - reported
        return f"raised {type(error).__name__}: {error}"


class Recorder(object):
    """A bridge wrapper that counts calls to one symbol and delegates everything else.

    Installed only for the duration of one pyjab call, so "the call site ran" is observed
    rather than inferred from reading the source. When it reports zero hits, the raw value
    below it describes a call this run never reached -- which is what makes the
    ``not reached`` path honest.
    """

    def __init__(self, bridge, target: str) -> None:
        self._bridge = bridge
        self.target = target
        self.hits = 0

    def __getattr__(self, name):
        attribute = getattr(self._bridge, name)
        if name != self.target or not callable(attribute):
            return attribute

        def counted(*args, **kwargs):
            self.hits += 1
            return attribute(*args, **kwargs)

        return counted


# ---------------------------------------------------------------------------
# Driving the application, one symbol at a time
# ---------------------------------------------------------------------------

def find(driver, *path):
    """Find each name in turn, returning the last element and releasing the earlier ones.

    ``find_element_by_name`` from the driver returns an element the caller owns, so holding
    a chain would leak one Java object per link. Releasing the intermediate ones immediately
    is what the ownership rule in AGENTS.md 2.1a asks for.
    """
    element = driver
    for name in path:
        nxt = element.find_element_by_name(name)
        if element is not driver:
            element.release_jabelement()
        element = nxt
    return element


def hold(element, ctx):
    """Keep an element alive until :func:`measure_symbol` has finished with it.

    **The raw call runs after the drive, on the element the drive found, so the reference
    has to outlive the property call.** Releasing inside the drive -- the natural place,
    and what the first version of this did -- hands the raw call a handle that has already
    been released, and JAB answers a released handle with an error: every symbol would have
    measured falsy, and the run would have argued for arming all fourteen.

    Releasing the intermediates of a chain *is* right, and :func:`find` does that; what is
    owned for longer is the one element the raw call needs.
    """
    ctx.setdefault("held", []).append(element)
    return element


def release_held(ctx) -> None:
    """Release every element a drive kept, once, in reverse order."""
    for element in reversed(ctx.get("held") or []):
        try:
            element.release_jabelement()
        except Exception:                                 # noqa: BLE001 - best effort
            pass
    ctx["held"] = []


def drive_get_accessible_context_info(driver, ctx) -> Reach:
    """Every property funnels through ``_acc_info``; drive one and capture its arguments."""
    label = hold(find(driver, LABEL_NAME), ctx)
    ctx["element"] = label
    ctx["outcome"] = outcome(lambda: label.name)
    return Reach(True, f"read .name of {LABEL_NAME!r}")


def drive_get_accessible_text_info(driver, ctx) -> Reach:
    """The text field is the component with accessible text; read it."""
    field = hold(find(driver, TEXT_FIELD_NAME), ctx)
    ctx["text_element"] = field
    ctx["outcome"] = outcome(lambda: field.text)
    return Reach(True, f"read .text of {TEXT_FIELD_NAME!r}")


def drive_get_accessible_text_range(driver, ctx) -> Reach:
    """Same read: ``.text`` fetches the info and then the range."""
    field = hold(find(driver, TEXT_FIELD_NAME), ctx)
    ctx["text_element"] = field
    ctx["outcome"] = outcome(lambda: field.text)
    return Reach(True, f"read .text of {TEXT_FIELD_NAME!r} (which fetches the range)")


def drive_get_accessible_table_cell_info(driver, ctx) -> Reach:
    """``get_cell`` is the only caller, and the application's table has cells."""
    table = hold(find(driver, TABLE_NAME), ctx)
    cell = table.get_cell(0, 0)
    try:
        ctx["table"] = table
        ctx["outcome"] = f"get_cell(0, 0) returned name={cell.name!r}"
        return Reach(True, f"called get_cell(0, 0) on {TABLE_NAME!r}")
    finally:
        cell.release_jabelement()


def drive_get_visible_children(driver, ctx) -> Reach:
    """``get_visible_children`` is the public caller; the main panel has children to see."""
    panel = hold(find(driver, MAIN_PANEL_NAME), ctx)
    children = panel.get_visible_children()
    try:
        ctx["element"] = panel
        ctx["outcome"] = f"get_visible_children() returned {len(children)} child(ren)"
        return Reach(True, f"called get_visible_children() on {MAIN_PANEL_NAME!r}")
    finally:
        for child in children:
            child.release_jabelement()


def drive_get_top_level_object(driver, ctx) -> Reach:
    """``_get_top_level_object`` is the element-side caller; it is what ``walk`` uses.

    The driver-side caller (jabdriver.py:301) is a different branch of the same symbol and
    is exercised separately, in :func:`drive_get_hwnd_from_accessible_context`.
    """
    label = hold(find(driver, LABEL_NAME), ctx)
    ctx["element"] = label
    top = label._get_top_level_object()
    try:
        ctx["outcome"] = f"_get_top_level_object() returned {top!r}"
        return Reach(True, f"called _get_top_level_object() on {LABEL_NAME!r}")
    finally:
        # This reference came from _get_top_level_object, which handed it to this caller.
        label.bridge.releaseJavaObject(label.vmid, top)


def drive_set_text_contents(driver, ctx) -> Reach:
    """``send_text(simulate=False)`` is the only caller, and the field is writable.

    A value the field does not already hold, so the write is observable, and then the
    original back -- ``send_text`` waits for the property to change, and a write of what is
    already there would make that wait the thing being measured. Both calls go through the
    call site; the second is the one whose return is probed, and it leaves the field as it
    was found for the probes that come after.
    """
    field = hold(find(driver, TEXT_FIELD_NAME), ctx)
    ctx["text_element"] = field
    ctx["outcome"] = outcome(lambda: field.send_text(TEXT_FIELD_TEXT + "_measurement"))
    ctx["outcome"] += "; " + outcome(lambda: field.send_text(TEXT_FIELD_TEXT))
    return Reach(True, f"called send_text twice on {TEXT_FIELD_NAME!r}, leaving "
                       f"{TEXT_FIELD_TEXT!r} in the field")


def drive_get_accessible_child_from_context(driver, ctx) -> Reach:
    """There is no method with this name: it is how a walk enumerates children.

    The reach has to be shown, not assumed -- a lookup by name walks the tree, and if the
    walk could not step into a child the lookup would have raised at the root. So this
    queries a control that exists *only* as a child, after another control has changed its
    state, and requires the state to be readable.
    """
    try:
        driver.find_element_by_name(BUTTON_DISABLER_NAME).click()
    except Exception as error:                            # noqa: BLE001 - reported
        return Reach(False, f"could not click {BUTTON_DISABLER_NAME!r} to change the "
                            f"button's state: {type(error).__name__}: {error}",
                     no_component=True)

    try:
        middle = hold(driver.find_element_by_name(BUTTON_NAME), ctx)
    except Exception as error:                            # noqa: BLE001 - reported
        return Reach(False, f"could not find {BUTTON_NAME!r} after disabling it, so no "
                            f"child was walked into: {type(error).__name__}: {error}",
                     no_component=True)

    ctx["element"] = middle
    # Wait for the state change the click caused: the click returns before the Swing
    # listener has necessarily run through the event queue, and reading it immediately
    # would report a race as a reach failure.
    deadline = time.monotonic() + 5.0
    while middle.is_enabled() and time.monotonic() < deadline:
        time.sleep(0.1)
    changed = middle.is_enabled()
    # Put the button back, so the action probes later in the sweep click it in its normal
    # state rather than a disabled one -- a disabled Swing button answers a click with a
    # denial, which is a different measurement from the one those probes are taking.
    try:
        driver.find_element_by_name(BUTTON_ENABLER_NAME).click()
    except Exception:                                     # noqa: BLE001 - best effort
        pass
    ctx["outcome"] = (
        f"find_element_by_name({BUTTON_NAME!r}) found the control, and "
        f"is_enabled() was {changed!r} after {BUTTON_DISABLER_NAME!r} was clicked; "
        f"{BUTTON_ENABLER_NAME!r} was then clicked to restore it"
    )
    return Reach(True, f"walked into a child by name, reaching {BUTTON_NAME!r} "
                       f"through getAccessibleChildFromContext")


def drive_get_version_info(driver, ctx) -> Reach:
    """``get_version_info`` is the only caller, and this driver is bound to the window."""
    try:
        info = driver.get_version_info()
    except Exception as error:                            # noqa: BLE001 - reported
        return Reach(False, f"driver.get_version_info() raised "
                            f"{type(error).__name__}: {error}")
    ctx["outcome"] = f"get_version_info() returned VMVersion={info['VMVersion']!r}"
    return Reach(True, "called driver.get_version_info()")


def drive_get_accessible_context_from_hwnd(driver, ctx) -> Reach:
    """``getAccessibleContextFromHWND`` is how a driver attaches, and attaching is public.

    ``JABDriver.__init__`` reaches the call through ``_get_accessible_context_from_hwnd``,
    which is private -- and the documentation checker has a test that a tool must not reach
    into private API (``tests/test_documented_api.py::test_every_tool_is_clean``). Binding a
    driver by **window handle** is the public way to make the same call.

    The handle has to be a real one: a driver bound to a title leaves ``driver.hwnd`` set
    but *bound*, and handing that handle to a second driver does make the call -- the first
    dispatch of this tool claimed the symbol was reached while the recorder counted nothing,
    which is exactly the "reached" claim this tool exists to refuse. So the window handle is
    resolved first, through pyjab's own public lookup, and the reach check then has to see
    the call.

    The extra driver is detached straight away: ``detach()`` releases the reference it took
    and clears its pid, so it can neither leak a Java object nor SIGTERM the process this run
    is measuring.
    """
    try:
        hwnd = driver.get_java_window_hwnd(driver.title)
        if not hwnd:
            return Reach(False, f"no Java window handle for {driver.title!r} to bind to",
                         no_component=True)
        attached = _attach_by_hwnd(hwnd)
    except Exception as error:                            # noqa: BLE001 - reported
        return Reach(False, f"binding a JABDriver by hwnd raised "
                            f"{type(error).__name__}: {error}")
    try:
        ctx["outcome"] = (f"JABDriver(hwnd={hwnd!r}) attached, resolving vmid="
                          f"{attached.vmid!r}")
        return Reach(True, f"constructed a JABDriver from the window handle {hwnd!r}, "
                           f"which is how the call site is reached")
    finally:
        attached.detach()


def _attach_by_hwnd(hwnd):
    """A driver bound by window handle: the public path to the call site.

    Not a context manager: ``__exit__`` SIGTERMs the bound pid, and this is the same
    process the first driver owns. The caller detaches it instead.
    """
    from pyjab.jabdriver import JABDriver

    return JABDriver(hwnd=hwnd, timeout=10)


def drive_get_hwnd_from_accessible_context(driver, ctx) -> Reach:
    """Reached by binding a second driver from the vmid and context instead of a title.

    The rebound driver is detached before the raw call runs, because ``detach()`` is what
    releases the reference it took and detaching also clears the pid, which is what stops a
    later ``__exit__`` from SIGTERMing the process being measured. The raw call therefore
    uses the first driver's own window and context -- a different reference to the same
    window, which is what the symbol's answer depends on.
    """
    try:
        rebound = _rebind_from_vmid_context(driver)
    except Exception as error:                            # noqa: BLE001 - reported
        return Reach(False, f"binding a driver from the vmid and context raised "
                            f"{type(error).__name__}: {error}")

    try:
        ctx["outcome"] = (f"JABDriver(vmid=..., accessible_context=...) bound "
                          f"hwnd={rebound.hwnd!r}")
        return Reach(True, "constructed a JABDriver from the vmid and context, which is "
                           "the only caller")
    finally:
        rebound.detach()


def drive_request_focus(driver, ctx) -> Reach:
    """``clear(simulate=True)`` is one of the three callers of ``_request_focus``.

    It is driven rather than reached through the public method: ``clear`` with
    ``simulate=True`` also presses End and one Backspace per character into whatever has
    the keyboard focus, and a measurement tool should not type into somebody's window. The
    element is located by the same walk the real call starts from, and the private method
    is then called in the place the code calls it.

    Either way the reach is real: if the element had not been walked into, the lookup
    would have raised before any of this ran.
    """
    field = hold(find(driver, TEXT_FIELD_NAME), ctx)
    ctx["element"] = field
    foreground = field.win32_utils.set_window_foreground(hwnd=field.hwnd)
    ctx["outcome"] = outcome(lambda: field._request_focus())
    return Reach(True, f"called _request_focus() on {TEXT_FIELD_NAME!r}, the call "
                       f"clear(simulate=True) makes after bringing the window "
                       f"forward (foreground={foreground!r}; the backspace loop was "
                       f"skipped deliberately)")


def drive_get_accessible_actions(driver, ctx) -> Reach:
    """``_do_accessible_action`` is the only caller; ``click()`` is how it is reached."""
    button = hold(find(driver, BUTTON_NAME), ctx)
    ctx["outcome"] = outcome(lambda: button.click())
    return Reach(True, f"called click() on {BUTTON_NAME!r}")


def drive_do_accessible_actions(driver, ctx) -> Reach:
    """Same call site: ``click()`` fills the action in and performs it."""
    button = hold(find(driver, BUTTON_NAME), ctx)
    ctx["outcome"] = outcome(lambda: button.click())
    return Reach(True, f"called click() on {BUTTON_NAME!r}")


def _rebind_from_vmid_context(driver):
    """A driver built the way ``jabdriver.py:301`` requires: from vmid and context.

    No context manager: ``__exit__`` terminates the bound process by pid, and this is the
    same process the first driver owns. ``detach()`` releases the reference instead.
    """
    from pyjab.jabdriver import JABDriver

    return JABDriver(vmid=driver.vmid, accessible_context=driver.accessible_context,
                     timeout=10)


DRIVERS = {
    "getAccessibleContextInfo": drive_get_accessible_context_info,
    "getAccessibleTextInfo": drive_get_accessible_text_info,
    "getAccessibleTextRange": drive_get_accessible_text_range,
    "getAccessibleTableCellInfo": drive_get_accessible_table_cell_info,
    "getVisibleChildren": drive_get_visible_children,
    "getTopLevelObject": drive_get_top_level_object,
    "setTextContents": drive_set_text_contents,
    "getAccessibleChildFromContext": drive_get_accessible_child_from_context,
    "getVersionInfo": drive_get_version_info,
    "getAccessibleContextFromHWND": drive_get_accessible_context_from_hwnd,
    "getHWNDFromAccessibleContext": drive_get_hwnd_from_accessible_context,
    "requestFocus": drive_request_focus,
    "getAccessibleActions": drive_get_accessible_actions,
    "doAccessibleActions": drive_do_accessible_actions,
}


# ---------------------------------------------------------------------------
# The raw calls, on the arguments the call site really arrived with
# ---------------------------------------------------------------------------

def raw_get_accessible_context_info(bridge, ctx):
    from ctypes import byref

    from pyjab.accessibleinfo import AccessibleContextInfo

    element = ctx["element"]
    info = AccessibleContextInfo()
    return bridge.getAccessibleContextInfo(element.vmid, element.accessible_context,
                                           byref(info))


def raw_get_accessible_text_info(bridge, ctx):
    from ctypes import byref

    from pyjab.accessibleinfo import AccessibleTextInfo

    element = ctx["text_element"]
    info = AccessibleTextInfo()
    return bridge.getAccessibleTextInfo(element.vmid, element.accessible_context,
                                        byref(info), 0, 0)


def raw_get_accessible_text_range(bridge, ctx):
    from ctypes import create_string_buffer

    element = ctx["text_element"]
    info = _text_info(element)
    if info is None or info.charCount == 0:
        raise RuntimeError("the text field reports no characters, so there is no range "
                           "to ask for")
    start = 0
    end = info.charCount - 1
    length = end + 1 - start
    buffer = create_string_buffer((length + 1) * 2)
    return bridge.getAccessibleTextRange(element.vmid, element.accessible_context,
                                         start, end, buffer, length)


def _text_info(element):
    from ctypes import byref

    from pyjab.accessibleinfo import AccessibleTextInfo

    info = AccessibleTextInfo()
    result = element.bridge.getAccessibleTextInfo(
        element.vmid, element.accessible_context, byref(info), 0, 0)
    return info if result else None


def raw_get_accessible_table_cell_info(bridge, ctx):
    from ctypes import byref

    from pyjab.accessibleinfo import AccessibleTableCellInfo

    table = ctx["table"]
    info = AccessibleTableCellInfo()
    return bridge.getAccessibleTableCellInfo(table.vmid, table.accessible_context,
                                             0, 0, byref(info))


def raw_get_visible_children_count(bridge, ctx):
    element = ctx["element"]
    return bridge.getVisibleChildrenCount(element.vmid, element.accessible_context)


def raw_get_visible_children(bridge, ctx):
    from ctypes import byref

    from pyjab.accessibleinfo import VisibleChildrenInfo

    element = ctx["element"]
    info = VisibleChildrenInfo()
    result = bridge.getVisibleChildren(element.vmid, element.accessible_context, 0,
                                       byref(info))
    # getVisibleChildren hands out a reference per child. This call is not a pyjab method,
    # so nothing else will release them. ``result`` is already an int by the time this
    # runs, so releasing first changes nothing that is printed.
    for index in range(info.returnedChildrenCount):
        if is_falsy(info.children[index]):
            continue
        try:
            bridge.releaseJavaObject(element.vmid, info.children[index])
        except Exception:                                 # noqa: BLE001 - best effort
            pass
    return result


def raw_get_top_level_object(bridge, ctx):
    element = ctx["element"]
    top = bridge.getTopLevelObject(element.vmid, element.accessible_context)
    # getTopLevelObject hands out a reference, and this call is not a pyjab method, so
    # nothing downstream will release it.
    if not is_falsy(top):
        bridge.releaseJavaObject(element.vmid, top)
    return top


def raw_set_text_contents(bridge, ctx):
    element = ctx["text_element"]
    return bridge.setTextContents(element.vmid, element.accessible_context,
                                  TEXT_FIELD_TEXT)


def raw_get_accessible_child_from_context(bridge, ctx):
    element = ctx["element"]
    child = bridge.getAccessibleChildFromContext(element.vmid,
                                                 element.accessible_context, 0)
    # The returned handle is printed, not used: releasing it here keeps the count exact,
    # and no property is read from it afterwards. (Two calls on one component would give
    # two references and two releases -- AGENTS.md 2.1a.)
    if not is_falsy(child):
        bridge.releaseJavaObject(element.vmid, child)
    return child


def raw_get_version_info(bridge, ctx):
    from ctypes import byref

    from pyjab.accessibleinfo import AccessBridgeVersionInfo

    driver = ctx["driver"]
    info = AccessBridgeVersionInfo()
    return bridge.getVersionInfo(driver.vmid, byref(info))


def raw_get_accessible_context_from_hwnd(bridge, ctx):
    from ctypes import byref, c_long

    from pyjab.common.types import JOBJECT64

    driver = ctx["driver"]
    vmid = c_long()
    context = JOBJECT64()
    return bridge.getAccessibleContextFromHWND(driver.hwnd, byref(vmid), byref(context))


def raw_get_hwnd_from_accessible_context(bridge, ctx):
    driver = ctx["driver"]
    return bridge.getHWNDFromAccessibleContext(driver.vmid, driver.accessible_context)


def raw_request_focus(bridge, ctx):
    element = ctx["element"]
    return bridge.requestFocus(element.vmid, element.accessible_context)


def raw_get_accessible_actions(bridge, ctx):
    from ctypes import byref

    from pyjab.accessibleinfo import AccessibleActions

    # The element the two action symbols share: click() finds it and the drive does not
    # record it, so the harness publishes it under one name for both.
    element = ctx["actions_element"]
    actions = AccessibleActions()
    return bridge.getAccessibleActions(element.vmid, element.accessible_context,
                                       byref(actions))


def raw_do_accessible_actions(bridge, ctx):
    from ctypes import byref, c_int

    from pyjab.accessibleinfo import AccessibleActionsToDo

    element = ctx["actions_element"]
    todo = AccessibleActionsToDo()
    todo.actionsCount = 1
    todo.actions[0].name = "click"
    failure = c_int()
    return bridge.doAccessibleActions(element.vmid, element.accessible_context,
                                      byref(todo), byref(failure))


RAW = {
    "getAccessibleContextInfo": raw_get_accessible_context_info,
    "getAccessibleTextInfo": raw_get_accessible_text_info,
    "getAccessibleTextRange": raw_get_accessible_text_range,
    "getAccessibleTableCellInfo": raw_get_accessible_table_cell_info,
    "getVisibleChildren": raw_get_visible_children,
    "getTopLevelObject": raw_get_top_level_object,
    "setTextContents": raw_set_text_contents,
    "getAccessibleChildFromContext": raw_get_accessible_child_from_context,
    "getVersionInfo": raw_get_version_info,
    "getAccessibleContextFromHWND": raw_get_accessible_context_from_hwnd,
    "getHWNDFromAccessibleContext": raw_get_hwnd_from_accessible_context,
    "requestFocus": raw_request_focus,
    "getAccessibleActions": raw_get_accessible_actions,
    "doAccessibleActions": raw_do_accessible_actions,
}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _unique(values):
    """Order-preserving dedupe, because ``getVisibleChildren`` is probed twice."""
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def falsy_summary(verdicts) -> str:
    """The one line the issue is asking for: which **candidate** symbols came back falsy.

    A symbol with no measurement at all is *not* listed here -- it is listed as
    ``INCONCLUSIVE`` instead, because "not falsy" and "never asked" must not read the same.

    The childless panel's probe is excluded: it is a control, and ``getVisibleChildren``
    returned falsy there on purpose. ``getVisibleChildren`` is also probed on the main
    panel, where it is expected truthy, so the symbol may appear here on evidence from that
    probe -- and :func:`report` prints the two separately.
    """
    falsy = _unique(verdict.symbol for verdict in verdicts
                    if verdict.candidate and verdict.measured and verdict.falsy)
    if not falsy:
        return "no candidate symbol returned falsy in this run"
    return "returned falsy in this run: " + ", ".join(falsy)


def finding(verdicts) -> str:
    """What the measurement means for arming the rows.

    Only the candidates count: the childless panel's falsy ``getVisibleChildren`` is the
    control saying "a falsy return is reachable", not a row this issue has to decide about.
    """
    falsy = [verdict for verdict in verdicts
             if verdict.candidate and verdict.measured and verdict.falsy]
    unmeasured = [verdict for verdict in verdicts if not verdict.measured]
    if unmeasured:
        return ("INCONCLUSIVE - " + "; ".join(
            f"{verdict.symbol}: {verdict.error}" for verdict in unmeasured))
    if falsy:
        sites = ", ".join(
            f"{symbol} ({CALL_SITES[symbol][0]}, which {CALL_SITES[symbol][1]} the "
            f"result)" for symbol in _unique(verdict.symbol for verdict in falsy))
        return (f"arming these rows would raise in ordinary use: {sites}. Arm the rest; "
                f"handle these first")
    return ("every candidate returned a nonzero value, so arming these rows changes "
            "nothing on this JVM in these paths")


def control_note(verdicts) -> str:
    """What the childless-panel control found, in one line.

    ``getVisibleChildren`` on an element with no children is the one place in this sweep
    where a falsy return is *expected*, and #191 measured that the bridge answers ``0``
    there. If it did not come back falsy, then this run never produced a falsy value at
    all, and "none of the candidates returned falsy" reads the same whether that is because
    none of them does or because this JVM never says ``0`` -- so the control failing has to
    stop the run rather than be a footnote.
    """
    controls = [verdict for verdict in verdicts if not verdict.candidate]
    if not controls:
        return "no falsy-return control was measured"
    for found in controls:
        if found.error is not None:
            return f"the falsy-return control could not be measured: {found.error}"
        if not found.falsy:
            return (f"FAIL the childless panel's getVisibleChildren returned "
                    f"{describe(found.raw)}, not falsy: this run never produced a falsy "
                    f"value, so 'no candidate returned falsy' is not evidence")
    return (f"ok  the childless panel's getVisibleChildren returned "
            f"{describe(controls[0].raw)}, falsy as #191 measured")


def control_failed(verdicts) -> bool:
    """Whether the falsy-return control did not do its job."""
    return control_note(verdicts).startswith("FAIL") or \
        control_note(verdicts).startswith("no falsy-return control")


def note_on_documented_error() -> str:
    """The truthy-``-1`` note, printed with the result rather than kept in a comment."""
    return (f"NOTE: {DOCUMENTED_ERROR} is truthy, so a row armed with the errcheck hook "
            f"would pass the documented error value straight through. A symbol whose "
            f"failure answer is {DOCUMENTED_ERROR} (getObjectDepth, for one) is not made "
            f"safe by arming it.")


class Rows(object):
    """A verdict per symbol, plus the ones that were never reached."""

    def __init__(self) -> None:
        self.verdicts = []
        self.unreached = []

    def record(self, verdict: Verdict) -> None:
        self.verdicts.append(verdict)

    def skip(self, symbol: str, reason: str) -> None:
        self.unreached.append((symbol, reason))


def report(rows: Rows, control: Optional[Tuple[str, str]]) -> int:
    """Print everything measured, and return the process exit code.

    Exit 0 only when every published symbol was reached **and** its direct call came back.
    Anything else is 2, INCONCLUSIVE: a partial sweep is not evidence for arming a row.
    """
    print()
    print("=" * 78)
    print("one line per symbol: raw return, its type, truthiness, and the code path")
    print("=" * 78)

    for verdict in rows.verdicts:
        site, expectation = CALL_SITES[verdict.symbol]
        print(f"\n{verdict.symbol}   ({site}; the call site {expectation} the result)")
        print(f"  reached by : {verdict.arguments}")
        print(f"  {verdict.raw_line()}")
        if verdict.outcome is not None:
            print(f"  pyjab path : {verdict.outcome}")

    for symbol, reason in rows.unreached:
        site, expectation = CALL_SITES[symbol]
        print(f"\n{symbol}   ({site}; the call site {expectation} the result)")
        print(f"  not reached: {reason}")
        print(f"  raw {symbol} -> not reached: no call arrived to take arguments from")

    print()
    print("=" * 78)
    print("the control, without which a falsy result means nothing")
    print("=" * 78)
    if control is None:
        print("  FAIL the direct control call was not made at all")
        print("\nINCONCLUSIVE: the harness did not even reach the bridge")
        return 2
    note, call_result = control
    print(f"  {note}")
    print(f"  {call_result}")

    print()
    print("=" * 78)
    print("summary")
    print("=" * 78)
    print(f"  {control_note(rows.verdicts)}")
    print(f"  {falsy_summary(rows.verdicts)}")
    if rows.unreached:
        for symbol, reason in rows.unreached:
            print(f"  not reached: {symbol} -> {reason}")
    print(f"  FINDING: {finding(rows.verdicts)}")
    print(f"  {note_on_documented_error()}")

    print()
    if rows.unreached:
        print("INCONCLUSIVE: " + "; ".join(
            f"{symbol} -> {reason}" for symbol, reason in rows.unreached))
        return 2
    missing = [verdict.symbol for verdict in rows.verdicts if not verdict.measured]
    if missing:
        print("INCONCLUSIVE: the direct call for "
              + ", ".join(missing) + " did not return, so those rows are unmeasured")
        return 2
    if control_failed(rows.verdicts):
        print("INCONCLUSIVE: " + control_note(rows.verdicts))
        return 2
    print(f"PASSED: every candidate symbol was reached and every direct call returned -- "
          f"{falsy_summary(rows.verdicts)}")
    return 0


# ---------------------------------------------------------------------------
# Launching, and the sweep itself
# ---------------------------------------------------------------------------

class _wrapped(object):
    """Restore the real bridge whichever way the body leaves."""

    def __init__(self, driver, symbol: str) -> None:
        self.driver = driver
        self.symbol = symbol
        self.real = driver.bridge
        self.recorder = Recorder(self.real, symbol)

    def __enter__(self):
        self.driver.bridge = self.recorder
        if getattr(self.driver, "root_element", None) is not None:
            self.driver.root_element.bridge = self.recorder
        return self.recorder

    def __exit__(self, exc_type, exc_value, traceback):
        self.driver.bridge = self.real
        if getattr(self.driver, "root_element", None) is not None:
            self.driver.root_element.bridge = self.real
        return False


def probe_painted_panel(driver) -> Verdict:
    """The positive control for a falsy return: the childless panel from #191.

    Its own ``getVisibleChildren`` is expected to be ``0``. If it is not, then this run
    never produced a falsy value at all, and "no candidate returned falsy" cannot be read as
    evidence -- :func:`control_note` is what turns that into ``INCONCLUSIVE``.
    """
    verdict = Verdict("getVisibleChildren", f"the childless {PAINTED_NAME!r} (#191)",
                      candidate=False)
    ctx = {"driver": driver}
    try:
        element = driver.find_element_by_name(PAINTED_NAME)
    except Exception as error:                            # noqa: BLE001 - reported
        verdict.error = (f"no such component in this application: {PAINTED_NAME!r} was "
                         f"not found: {type(error).__name__}: {error}")
        return verdict
    try:
        hold(element, ctx)
        ctx["element"] = element
        verdict.raw, verdict.error = raw_measure(
            driver.bridge, "getVisibleChildren",
            lambda: raw_get_visible_children(driver.bridge, ctx))
        count, count_error = raw_measure(
            driver.bridge, "getVisibleChildrenCount",
            lambda: raw_get_visible_children_count(driver.bridge, ctx))
        verdict.outcome = (f"getVisibleChildrenCount returned {describe(count)}"
                           if count_error is None
                           else f"getVisibleChildrenCount raised {count_error}")
        verdict.outcome += ("; the pyjab property was not called on this element because "
                            "it raises on exactly this value")
    finally:
        release_held(ctx)
    return verdict


# ---------------------------------------------------------------------------
# One symbol per process, on a budget
# ---------------------------------------------------------------------------

def verdict_from_wire(data) -> Verdict:
    """Turn a child's JSON row back into a Verdict.

    ``raw`` goes over the wire as text: it can be a JAB handle whose type is only
    meaningful in the process that obtained it, and the report prints it as a value rather
    than doing arithmetic on it.
    """
    found = Verdict(data["symbol"], data.get("arguments") or data.get("reached_by") or "",
                    candidate=data.get("candidate", True))
    if data.get("raw_error") is not None:
        found.error = data["raw_error"]
    elif data.get("raw") is not None:
        found.raw = data["raw"]
        found.raw_type = data.get("raw_type")
    else:
        found.error = "the child returned no value and no error, which is a bug in it"
    found.outcome = data.get("outcome")
    return found


def child_payload(verdict: Verdict) -> dict:
    """A Verdict as JSON, with the value rendered rather than serialised raw.

    A ctypes handle does not survive ``json.dumps``, and its ``repr`` is what the report
    prints anyway -- so the wire carries the text and the reader gets the same line.
    """
    if verdict.error is not None:
        raw = None
    elif isinstance(verdict.raw, (bool, int)):
        raw = verdict.raw
    else:
        raw = repr(verdict.raw)
    return {
        "symbol": verdict.symbol,
        "arguments": verdict.arguments,
        "candidate": verdict.candidate,
        "raw": raw,
        "raw_type": type(verdict.raw).__name__ if verdict.error is None else None,
        "raw_error": verdict.error,
        "outcome": verdict.outcome,
    }


def measure_one_in_this_process(driver, symbol: str) -> Verdict:
    """Run one symbol's drive and raw call, exactly as the in-process version did."""
    ctx = {"driver": driver}
    drive = DRIVERS[symbol]
    verdict = Verdict(symbol, "")

    with _wrapped(driver, symbol) as recorder:
        try:
            reach = drive(driver, ctx)
        except Exception as error:                        # noqa: BLE001 - reported
            verdict.error = (f"no such component in this application: a lookup raised "
                             f"{type(error).__name__}: {error}")
            release_held(ctx)
            return verdict

    try:
        verdict.arguments = reach.note
        if not reach.reached:
            reason = reach.note
            if not reach.no_component:
                reason = f"the harness could not drive it: {reason}"
            verdict.error = reason
            return verdict

        if recorder.hits < 1:
            verdict.error = (f"the harness drove {reach.note}, but the bridge was never "
                             f"asked for {symbol}; that is a gap in this tool")
            return verdict

        # The two action symbols are performed by click(), which finds its own element and
        # does not hand it to the drive. Both take the same one here, so the raw call asks
        # about the control the pyjab path just acted on rather than reusing a released
        # handle.
        if symbol in ("doAccessibleActions", "getAccessibleActions"):
            ctx["actions_element"] = hold(driver.find_element_by_name(BUTTON_NAME), ctx)

        verdict.raw, verdict.error = raw_measure(
            driver.bridge, symbol, lambda: RAW[symbol](driver.bridge, ctx))
        verdict.outcome = ctx.get("outcome")

        # visible_children_count is not one of the fourteen rows, but it is the number #191
        # measured, and printing it beside getVisibleChildren's own return is what keeps
        # "no visible children" and "the call was refused" from looking identical here.
        if symbol == "getVisibleChildren":
            count, count_error = raw_measure(
                driver.bridge, "getVisibleChildrenCount",
                lambda: raw_get_visible_children_count(driver.bridge, ctx))
            extra = (f"getVisibleChildrenCount returned {describe(count)}"
                     if count_error is None
                     else f"getVisibleChildrenCount raised {count_error}")
            verdict.outcome = f"{verdict.outcome}; {extra}"
        return verdict
    finally:
        release_held(ctx)


def control_in_this_process(driver) -> dict:
    """The direct ``getAccessibleContextInfo`` control, as JSON."""
    note, rendered = direct_control(driver)
    return {"note": note, "rendered": rendered,
            "ok": rendered.startswith("ok")}


# ---------------------------------------------------------------------------
# Launching, and the sweep itself
# ---------------------------------------------------------------------------

def compile_test_app() -> bool:
    javac = shutil.which("javac")
    if not javac:
        print("javac is not on the PATH. Run this from a JDK, not a JRE.")
        return False
    JAVA_CLASSES.mkdir(parents=True, exist_ok=True)
    sources = sorted(str(p) for p in JAVA_SRC.glob("*.java"))
    result = subprocess.run([javac, "-d", str(JAVA_CLASSES), *sources],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("compiling the test application failed:")
        print(result.stdout, result.stderr)
        return False
    return True


def launch() -> Optional[subprocess.Popen]:
    """Start the application with plain subprocess, so no pyjab call is involved.

    The same reason ``tools/verify_visible_children_count.py`` gives: this measures what
    the bridge returns for a window pyjab attached to, and letting pyjab launch it would
    put its own code in the path being measured.
    """
    java = shutil.which("java")
    if not java:
        print("java is not on the PATH.")
        return None
    proc = subprocess.Popen(
        [java, "-cp", str(JAVA_CLASSES), APP_CLASS, f"--title={WINDOW_TITLE}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"  launched {APP_CLASS} (pid {proc.pid}) with plain subprocess, no pyjab")
    return proc


def wait_for_window(timeout: float = 60.0):
    """Wait for the window using Win32 only, so the control does not need JAB."""
    from pyjab.common.win32utils import Win32Utils

    win32 = Win32Utils()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = win32.get_hwnds_by_title(f"*{WINDOW_TITLE}*")
        if matches:
            return matches
        time.sleep(0.5)
    return []


def direct_control(driver) -> Tuple[str, str]:
    """A direct call that must return truthy, proving the bridge is reachable at all.

    Deliberately *not* one of the fourteen candidates: this is the bridge working, not a
    row under test.

    The role it reports is read from the structure the call filled in, so the line says
    something about the window that was bound rather than only that a number came back. The
    field is ``role_en_US`` -- the structure's own spelling, which ``JABElement`` also uses;
    the first dispatch of this tool spelled it ``role_EN_US`` and the control child died on
    the ``AttributeError`` before one symbol had been measured.
    """
    from ctypes import byref

    from pyjab.accessibleinfo import AccessibleContextInfo
    from pyjab.jabelement import JABElement

    element = JABElement(bridge=driver.bridge, hwnd=driver.hwnd, vmid=driver.vmid,
                         accessible_context=driver.accessible_context)
    info = AccessibleContextInfo()
    try:
        result = driver.bridge.getAccessibleContextInfo(
            element.vmid, element.accessible_context, byref(info))
    except Exception as error:                            # noqa: BLE001 - reported
        return ("direct getAccessibleContextInfo on the root element raised",
                f"FAIL {type(error).__name__}: {error}")
    state = "ok  " if not is_falsy(result) else "FAIL"
    return (f"direct getAccessibleContextInfo on the root element (role "
            f"{info.role_en_US!r})",
            f"{state} {describe(result)}  "
            f"{'falsy?' if is_falsy(result) else 'nonzero?'}")


def child_main(args) -> int:
    """One symbol, in its own process, so a JAB call that never returns costs one line.

    The budget is enforced by the **parent**, which is the only place that can kill a call
    sitting inside the DLL. That is the whole reason the sweep is split this way: an
    in-process run that hangs loses every symbol measured before it, and says nothing about
    which one blocked.
    """
    from pyjab.jabdriver import JABDriver

    driver = JABDriver(title=args.title, timeout=args.timeout)
    try:
        if args.control:
            payload = {"control": control_in_this_process(driver)}
        elif args.painted:
            payload = {"verdict": child_payload(probe_painted_panel(driver))}
        else:
            payload = {"verdict": child_payload(
                measure_one_in_this_process(driver, args.symbol))}
    finally:
        # Not a context manager: __exit__ SIGTERMs the pid, and the application belongs to
        # the parent. detach() releases the reference this process took instead.
        driver.detach()
    print(json.dumps(payload))
    return 0


def parent_main(args) -> int:
    if not args.no_launch:
        if not compile_test_app():
            return 2

    proc = None
    rows = Rows()
    control = None
    try:
        if not args.no_launch:
            proc = launch()
            if proc is None:
                return 2

        print("\nthe control: is there a window to measure at all?")
        print("-" * 50)
        windows = wait_for_window()
        if not windows:
            print("  INCONCLUSIVE no window appeared, so a result below would mean")
            print("               nothing. Not evidence either way.")
            return 2
        print(f"  ok   found {len(windows)} window(s) without asking JAB anything")
        time.sleep(args.settle)

        print("\nthe control: is the bridge readable from a child at all?")
        print("-" * 54)
        control_payload = run_child(args, control=True)
        if control_payload is not None and "control" in control_payload:
            control = (control_payload["control"]["note"],
                       control_payload["control"]["rendered"])
        if control is None:
            print("  INCONCLUSIVE the control child did not report; nothing below it can "
                  "be read.")
            return report(rows, None)

        for symbol in SYMBOLS:
            print(f"  measuring {symbol} ...", flush=True)
            payload = run_child(args, symbol=symbol)
            if payload is None or "verdict" not in payload:
                rows.skip(symbol, f"the harness could not drive it: no report came back "
                                  f"within the {args.symbol_timeout}s budget, so a JAB "
                                  f"call inside it did not return")
                continue
            verdict = verdict_from_wire(payload["verdict"])
            if verdict.error is None and verdict.raw is None:
                rows.skip(symbol, "the child reported neither a value nor an error")
                continue
            rows.record(verdict)

        payload = run_child(args, control=True, painted=True)
        if payload is None or "verdict" not in payload:
            rows.skip("getVisibleChildren",
                      "the falsy-return control did not report within the budget")
        else:
            painted = verdict_from_wire(payload["verdict"])
            painted.candidate = False
            painted.arguments = f"the childless {PAINTED_NAME!r} (#191)"
            rows.record(painted)
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    return report(rows, control)


def run_child(args, symbol: Optional[str] = None,
              control: bool = False, painted: bool = False):
    """Measure one thing in a fresh process and return its JSON, or None on a timeout."""
    argv = [sys.executable, str(Path(__file__).resolve()),
            "--child", "--title", args.title, "--timeout", str(args.timeout),
            "--symbol-timeout", str(args.symbol_timeout),
            "--settle", str(args.settle)]
    budget = args.symbol_timeout
    if control:
        argv += ["--control"]
        budget = max(budget, args.timeout * 3)
    else:
        argv += ["--symbol", symbol]
        if painted:
            argv += ["--painted"]
    try:
        finished = subprocess.run(argv, capture_output=True, text=True, timeout=budget)
    except subprocess.TimeoutExpired:
        print(f"    no report within {budget}s -- a JAB call in that child did not "
              f"return", flush=True)
        return None
    for line in reversed(finished.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    print(f"    the child produced no JSON row (exit {finished.returncode}): "
          f"{(finished.stderr or '').strip()[-400:]}", flush=True)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true",
                        help="the application is already running")
    parser.add_argument("--timeout", type=int, default=30,
                        help="How long JABDriver waits to bind to the window, in seconds "
                             "(default 30); the window itself is waited for for 60")
    parser.add_argument("--symbol-timeout", type=int, default=180,
                        help="Wall-clock budget for one child process, in seconds "
                             "(default 180)")
    parser.add_argument("--settle", type=float, default=3.0,
                        help="Seconds to let the window settle before the first attach")
    parser.add_argument("--title", default=WINDOW_TITLE,
                        help="Window title to bind to (default PyjabTestApp)")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--control", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--painted", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--symbol", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if platform.system() != "Windows":
        print("This needs Windows: it asks the Java Access Bridge about a live window.",
              file=sys.stderr)
        return 2

    if args.child:
        if args.painted:
            args.symbol = "getVisibleChildren"
        try:
            return child_main(args)
        except Exception as error:                        # noqa: BLE001 - reported
            # A crash in the child must still leave one JSON row behind. Twice now the
            # tool's own bug arrived at the parent as "no JSON row", which reads like a
            # broken bridge rather than like a line in this file -- the attribute typo cost
            # a whole dispatch to find.
            where = traceback.extract_tb(error.__traceback__)[-1]
            print(json.dumps({"verdict": {
                "symbol": args.symbol or "control",
                "arguments": "the child crashed before it could drive anything",
                "candidate": True,
                "raw": None,
                "raw_type": None,
                "raw_error": (f"the harness could not drive it: {type(error).__name__}: "
                              f"{error} (at {Path(where.filename).name}:{where.lineno} in "
                              f"{where.name})"),
                "outcome": None,
            }}))
            return 1
    return parent_main(args)


if __name__ == "__main__":
    sys.exit(main())
