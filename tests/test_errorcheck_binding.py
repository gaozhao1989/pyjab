"""The ``errorcheck`` flag in ``SIGNATURES``: a mechanism, armed on five measured rows.

``JABFixedFunc._fix_bridge_function`` used to assign ``func.errorcheck``, which is not a
ctypes attribute -- ctypes spells it ``errcheck`` -- so the assignment set an inert Python
attribute and no hook was ever installed. Every row marked ``True`` was therefore silent
(#195). The spelling is fixed, and the table now arms the five symbols a real run measured
returning truthy at pyjab's own call sites **and** that no ``except JABException`` handler is
reachable from (``windows-gui.yml`` task ``jab-return-values``, run 38071056432, JDK 17):
``getAccessibleTextInfo``, ``getAccessibleTextRange``, ``getAccessibleTableCellInfo``,
``setTextContents`` and ``getVersionInfo``.

Behavioural tests were thought useless here, because the portable suite never loads a bridge
DLL. **That is half wrong.** A bridge DLL cannot be loaded, but a real ctypes function pointer
can be built with ``CFUNCTYPE``, and ctypes applies ``errcheck`` to one exactly as it does to a
symbol fetched off a DLL -- so the hook *is* reachable, and so are the call sites it fires in.
That is what the last section of this module uses. What is left to a stand-in is only the
bridge object that hands the pointers out.

The invariants that keep the decision from being undone in passing are asserted too: **a row is
armed only if a measurement cleared it**, and **the three symbols that handlers have to keep
catching are never armed** -- ``getAccessibleContextInfo``, and ``getVisibleChildren`` /
``getTopLevelObject``, which the run measured truthy on the live path only.

Why the invariants are tests and not comments: arming a row is a per-row change with a
non-local blast radius. It makes the caller's own ``if not result:`` check unreachable and it
turns a falsy result into ``RuntimeError`` from inside the call, so ``except JABException``
blocks stop catching. Only a dispatched run on a real JVM can measure a symbol, so the table
is the part this suite can hold still.
"""

from __future__ import annotations

from ctypes import CFUNCTYPE
from ctypes import c_int

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

import pyjab.jabfixedfunc as jabfixedfunc
from pyjab.common.types import JOBJECT64
from pyjab.jabfixedfunc import ERRCHECK_HINTS
from pyjab.jabfixedfunc import JABFixedFunc
from pyjab.jabfixedfunc import SIGNATURES


#: The five symbols a real run measured as returning truthy through pyjab's own call sites
#: **and** that no ``except JABException`` handler is reachable from. This is the whole of the
#: clearance -- see AGENTS.md 2.7 and issue #195.
ARMED = {
    "getAccessibleTextInfo",
    "getAccessibleTextRange",
    "getAccessibleTableCellInfo",
    "setTextContents",
    "getVersionInfo",
}

#: Measured truthy by the same run, and still ``False``, because the run only cleared the live
#: path and both of these are reached by handlers that have to keep catching:
#:
#: * ``getVisibleChildren`` -- the ``visible=True`` walk calls it on every element, and a
#:   childless panel answers falsy (the measurement tool's own second control). The two
#:   xpath union loops ``continue`` past a falsy result today; the hook's ``RuntimeError``
#:   they would not catch.
#: * ``getTopLevelObject`` -- JAB documents ``(AccessibleContext)0`` as its error answer and
#:   ``_get_top_level_object`` checks for it by hand. ``_xpath_search_root`` calls it fresh on
#:   every absolute locator, which is inside five handlers.
DECLINED = {"getTopLevelObject", "getVisibleChildren"}

#: Read by every property through ``_acc_info``, so it is reachable from every
#: ``except JABException`` in the package -- two of which are search loops that would give up
#: rather than skip. Nothing measured clears it.
NEVER_ARMED = {"getAccessibleContextInfo"}


class _FakeCFunc(object):
    """The part of a ctypes function pointer these tests act on."""

    def __init__(self):
        self.restype = None
        self.argtypes = ()
        self.errcheck = None


class _FakeBridge(object):
    """A bridge stand-in exporting whichever symbols it is built with."""

    def __init__(self, *names):
        self._funcs = {name: _FakeCFunc() for name in names}

    def __getattr__(self, name):
        try:
            return self._funcs[name]
        except KeyError:
            raise AttributeError(name)


# ---------------------------------------------------------------------------
# The spelling, which is the whole defect
# ---------------------------------------------------------------------------

def test_a_flagged_symbol_gets_the_errcheck_hook():
    """Asserted on the name ctypes reads, not the one the code used to write.

    ``.errorcheck`` is an ordinary Python attribute, so the wrong assignment
    succeeds silently -- which is how the defect survived. The hook only exists
    if ctypes' own ``errcheck`` slot holds it.
    """
    bridge = _FakeBridge("getVersionInfo")
    func = bridge.getVersionInfo

    JABFixedFunc(bridge)._fix_bridge_function(c_int, "getVersionInfo",
                                              errorcheck=True)

    assert func.errcheck is JABFixedFunc._check_error
    assert "errorcheck" not in vars(func), (
        "the misspelling is back: ctypes ignores an ``errorcheck`` attribute, so "
        "the hook would never be installed"
    )


def test_an_unflagged_symbol_gets_no_hook():
    bridge = _FakeBridge("getAccessibleContextInfo")
    func = bridge.getAccessibleContextInfo

    JABFixedFunc(bridge)._fix_bridge_function(c_int, "getAccessibleContextInfo",
                                              errorcheck=False)

    assert func.errcheck is None


def test_omitting_the_flag_also_leaves_the_hook_off():
    """``errorcheck`` is opt-in; a row that omits it installs nothing."""
    bridge = _FakeBridge("getAccessibleContextInfo")
    func = bridge.getAccessibleContextInfo

    JABFixedFunc(bridge)._fix_bridge_function(c_int, "getAccessibleContextInfo")

    assert func.errcheck is None


# ---------------------------------------------------------------------------
# The hook's own contract
# ---------------------------------------------------------------------------

def test_the_hook_raises_on_zero():
    with pytest.raises(RuntimeError, match="Result 0"):
        JABFixedFunc._check_error(0, None, None)


def test_the_hook_returns_a_truthy_result_unchanged():
    assert JABFixedFunc._check_error(1, None, None) == 1


def test_the_hook_does_not_cover_the_minus_one_sentinel():
    """The convention the hook does and does not cover.

    ``-1`` is truthy, so it passes through untouched -- and JAB uses it as an
    error answer for some calls (``getObjectDepth``'s docstring says so, and
    ``jabelement.py`` checks for it by hand). Arming a row is therefore not a
    substitute for knowing what that particular call returns on failure, which
    is exactly what the per-row measurement in #195 has to establish.
    """
    assert JABFixedFunc._check_error(-1, None, None) == -1


# ---------------------------------------------------------------------------
# The armed set
# ---------------------------------------------------------------------------

def test_only_the_measured_symbols_are_flagged():
    """``True`` exactly where a measurement put it, and ``False`` everywhere else.

    ``False`` rather than any falsy value, so the column stays a bool.
    """
    for name, _restype, _argtypes, errorcheck in SIGNATURES:
        expected = name in ARMED
        assert errorcheck is expected, (
            f"{name} is flagged {errorcheck!r}, expected {expected!r}"
        )


def test_a_row_armed_without_a_measurement_fails():
    """The table itself: arming a row by accident fails here.

    This is the invariant that keeps the decision from being extended in passing -- it fails
    on an extra ``True``, which is the shape a careless edit takes.
    """
    armed = [name for name, _restype, _argtypes, errorcheck in SIGNATURES
             if errorcheck]

    unexpected = sorted(set(armed) - ARMED)
    assert unexpected == [], (
        "these rows install the errcheck hook without a measurement behind them "
        "(#195): " + ", ".join(unexpected)
    )


def test_the_symbols_reached_by_an_except_handler_stay_unarmed():
    """The decisions that are easiest to undo by accident.

    ``getAccessibleContextInfo`` is read by every property through ``_acc_info``, so it is
    reachable from every ``except JABException`` in the package. ``getVisibleChildren`` and
    ``getTopLevelObject`` were measured truthy as well, and are still unarmed because the
    handlers that catch a failure from them have to keep catching it -- see ``DECLINED``.
    """
    for name, _restype, _argtypes, errorcheck in SIGNATURES:
        if name in NEVER_ARMED or name in DECLINED:
            assert errorcheck is False, f"{name} must stay unarmed"


def test_applying_the_table_installs_the_hook_on_exactly_the_measured_five():
    """The invariant asserted through the code that acts on it.

    ``test_only_the_measured_symbols_are_flagged`` reads the table; this runs it against a
    bridge exporting every symbol. Both are needed, because a row could be armed by a change
    to ``_fix_bridge_functions`` rather than to the table.
    """
    names = [name for name, _restype, _argtypes, _errorcheck in SIGNATURES]
    bridge = _FakeBridge(*names)

    JABFixedFunc(bridge)._fix_bridge_functions()

    armed = sorted(name for name, func in bridge._funcs.items()
                   if func.errcheck is not None)

    # Exactly the measured five, and nothing else -- not "none", which was the old
    # invariant, and not "at least these", which would let a row be armed in passing.
    assert armed == sorted(ARMED), (
        f"hooks were installed on {armed}; expected {sorted(ARMED)}"
    )


# ---------------------------------------------------------------------------
# The call sites arming made single-mechanism (#217)
# ---------------------------------------------------------------------------
#
# Arming a row made the hand-written check at its call site unreachable: ctypes raises
# before the check is evaluated. The checks were removed, and these tests hold the
# arrangement still in *both* directions, because either half alone can be satisfied while
# the invariant is broken:
#
# * armed -> the call site must raise, naming the symbol in the message;
# * disarmed -> the call site must NOT raise. That is the half that says the check is gone
#   rather than merely unreached: write one back and this fails with JABException.
#
# Together they are "one mechanism per call": disarm the row while the check is absent and
# the armed test goes red, which is the failure #217 is about.
#
# The bridge symbols are real ctypes function pointers, so the real errcheck hook runs.
# ctypes applies ``errcheck`` to a ``CFUNCTYPE`` instance exactly as it does to a symbol
# fetched off a DLL, and sets ``__name__`` on one the way ``CDLL.__getitem__`` does.

JABElement = _win32stubs.import_jabelement()
JABDriver = _win32stubs.import_jabdriver()

#: A VM id of 1 -- the convention is a plain int everywhere (AGENTS.md 2.4).
_VMID = 1


class _ScriptedBridge(object):
    """A bridge exporting every symbol, each a real ctypes function pointer.

    The symbol named by *failing* returns 0; every other returns 1. Nothing here models
    a JVM -- only the return value and the hook ctypes puts on it.
    """

    def __init__(self, failing: str) -> None:
        self._failing = failing
        self._funcs = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self._funcs:
            func = CFUNCTYPE(c_int)(
                lambda *args: 0 if name == self._failing else 1
            )
            func.__name__ = name
            self._funcs[name] = func
        return self._funcs[name]


def _element(bridge):
    return JABElement(bridge=bridge, hwnd=1234, vmid=_VMID,
                      accessible_context=JOBJECT64(1))


def _driver(bridge):
    """A JABDriver with only the bridge bound.

    ``JABDriver.__init__`` loads the bridge DLL, starts a service and can write
    ``~/.accessibility.properties`` (AGENTS.md 2.3). ``get_version_info`` needs none of
    that -- a vmid and a bridge -- so the instance is built without it.
    """
    driver = JABDriver.__new__(JABDriver)
    driver._bridge = bridge
    driver._vmid = _VMID
    return driver


#: One call through each armed symbol, as a caller reaches it. ``send_text`` is asked not
#: to wait for the text update: that would read ``self.role`` and the clock, neither of
#: which this test is about.
CALL_SITES = {
    "getAccessibleTextInfo":
        lambda bridge: _element(bridge)._get_accessible_text_info(),
    "getAccessibleTextRange":
        lambda bridge: _element(bridge)._get_accessible_text_range(0, 1, None, 1),
    "getAccessibleTableCellInfo":
        lambda bridge: _element(bridge)._get_accessible_table_cell_info(0, 0),
    "setTextContents":
        lambda bridge: _element(bridge).send_text("x", wait_for_text_update=False),
    "getVersionInfo":
        lambda bridge: _driver(bridge).get_version_info(),
}


def test_every_armed_symbol_has_a_call_site_here():
    """The set this module drives is the armed set, not a copy that can drift."""
    assert set(CALL_SITES) == ARMED


@pytest.mark.parametrize("symbol", sorted(CALL_SITES))
def test_an_armed_call_site_raises_and_names_the_symbol(symbol):
    """Armed, the call site must not return -- and the message must say which call.

    The symbol name is what the removed checks' messages carried, and the hook now
    carries it instead. Disarming the row makes this test fail with no exception at all,
    because there is no longer anything at the call site to raise.
    """
    bridge = _ScriptedBridge(failing=symbol)
    JABFixedFunc(bridge)._fix_bridge_functions()

    with pytest.raises(RuntimeError, match=rf"'{symbol}'"):
        CALL_SITES[symbol](bridge)


@pytest.mark.parametrize("symbol", sorted(CALL_SITES))
def test_a_disarmed_call_site_has_no_hand_written_check(symbol, monkeypatch):
    """The counterfactual, and the half that proves the check is gone rather than dead.

    With the row disarmed there is no hook, so a falsy result comes back to the caller.
    Nothing raises -- which is only true while the call site carries no check. Write one
    back and this fails with ``JABException``, the second mechanism the arming made
    unreachable.
    """
    disarmed = tuple(
        (name, restype, argtypes, False)
        for name, restype, argtypes, _errorcheck in SIGNATURES
    )
    monkeypatch.setattr(jabfixedfunc, "SIGNATURES", disarmed)

    bridge = _ScriptedBridge(failing=symbol)
    JABFixedFunc(bridge)._fix_bridge_functions()
    assert bridge._funcs[symbol].errcheck is None, "the row was still armed"

    CALL_SITES[symbol](bridge)


def test_the_hint_a_removed_check_carried_is_still_in_the_message():
    """``setTextContents`` cost the caller a hint when its check went away (#217).

    Its message was ``Java Access Bridge func 'setTextContents' error, try set parameter
    'simulate' with True``. Arming made the check unreachable, so the hint moved into
    ``ERRCHECK_HINTS``, where the hook that replaced the check can still say it.
    """
    bridge = _ScriptedBridge(failing="setTextContents")
    JABFixedFunc(bridge)._fix_bridge_functions()

    with pytest.raises(RuntimeError, match="simulate"):
        CALL_SITES["setTextContents"](bridge)


def test_the_hook_names_the_symbol_and_appends_its_hint():
    """The hook's own contract, without going through a call site or the hint table."""
    func = _ScriptedBridge(failing="setTextContents").setTextContents
    func._pyjab_error_hint = "try set parameter 'simulate' with True"

    with pytest.raises(RuntimeError) as raised:
        JABFixedFunc._check_error(0, func, ())

    message = str(raised.value)
    assert "'setTextContents'" in message
    assert "simulate" in message


def test_a_hint_belongs_only_to_an_armed_symbol():
    """A hint on a row with no hook is data nothing can ever read."""
    armed = {name for name, _restype, _argtypes, errorcheck in SIGNATURES if errorcheck}

    assert set(ERRCHECK_HINTS) <= armed, (
        "ERRCHECK_HINTS names a symbol that is not armed, so it can never be reached: "
        + ", ".join(sorted(set(ERRCHECK_HINTS) - armed))
    )

