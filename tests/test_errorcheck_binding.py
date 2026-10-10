"""The ``errorcheck`` flag in ``SIGNATURES``: a mechanism, armed on five measured rows.

``JABFixedFunc._fix_bridge_function`` used to assign ``func.errorcheck``, which is not a
ctypes attribute -- ctypes spells it ``errcheck`` -- so the assignment set an inert Python
attribute and no hook was ever installed. Every row marked ``True`` was therefore silent
(#195). The spelling is fixed, and the table now arms the five symbols a real run measured
returning truthy at pyjab's own call sites **and** that no ``except JABException`` handler is
reachable from (``windows-gui.yml`` task ``jab-return-values``, run 38071056432, JDK 17):
``getAccessibleTextInfo``, ``getAccessibleTextRange``, ``getAccessibleTableCellInfo``,
``setTextContents`` and ``getVersionInfo``.

Behavioural tests are still useless here. The portable suite never loads a bridge DLL, so no
real ``_FuncPtr`` and no real ``errcheck`` hook is ever reached. What *can* be asserted is the
mechanism itself, against a stand-in bridge, plus the invariants that keep the decision from
being undone in passing: **a row is armed only if a measurement cleared it**, and **the three
symbols that handlers have to keep catching are never armed** -- ``getAccessibleContextInfo``,
and ``getVisibleChildren`` / ``getTopLevelObject``, which the run measured truthy on the live
path only.

Why the invariants are tests and not comments: arming a row is a per-row change with a
non-local blast radius. It makes the caller's own ``if not result:`` check unreachable and it
turns a falsy result into ``RuntimeError`` from inside the call, so ``except JABException``
blocks stop catching. Only a dispatched run on a real JVM can measure a symbol, so the table
is the part this suite can hold still.
"""

from __future__ import annotations

from ctypes import c_int

import pytest

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
