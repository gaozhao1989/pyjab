"""The ``errorcheck`` flag in ``SIGNATURES``: a mechanism, deliberately unarmed.

``JABFixedFunc._fix_bridge_function`` used to assign ``func.errorcheck``, which is not a
ctypes attribute -- ctypes spells it ``errcheck`` -- so the assignment set an inert Python
attribute and no hook was ever installed. Every row marked ``True`` was therefore silent
(#195). The first step of that issue fixes the spelling and sets every row to ``False``:
the mechanism now works and is deliberately unarmed, so this release changes nothing
observable.

That makes behavioural tests useless here. The portable suite never loads a bridge DLL, so
no real ``_FuncPtr`` and no real ``errcheck`` hook is ever reached; and because no row is
armed, there is nothing to observe downstream either. What *can* be asserted is the
mechanism itself, against a stand-in bridge, plus the invariant that keeps the release a
no-op.

Why the invariant is a test and not a comment: arming a row is a per-row change with a
non-local blast radius. It makes the caller's own ``if not result:`` check unreachable and
stops ``except JABException`` blocks catching, so a row flipped to ``True`` in passing has
to fail something rather than ship.
"""

from __future__ import annotations

from ctypes import c_int

import pytest

from pyjab.jabfixedfunc import JABFixedFunc
from pyjab.jabfixedfunc import SIGNATURES


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
    bridge = _FakeBridge("getVersionInfo")
    func = bridge.getVersionInfo

    JABFixedFunc(bridge)._fix_bridge_function(c_int, "getVersionInfo",
                                              errorcheck=False)

    assert func.errcheck is None


def test_omitting_the_flag_also_leaves_the_hook_off():
    """``errorcheck`` is opt-in; the default is the current behaviour."""
    bridge = _FakeBridge("getVersionInfo")
    func = bridge.getVersionInfo

    JABFixedFunc(bridge)._fix_bridge_function(c_int, "getVersionInfo")

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
# Nothing is armed
# ---------------------------------------------------------------------------

def test_no_signature_row_is_flagged():
    """The table itself: arming a row by accident fails here."""
    armed = [name for name, _restype, _argtypes, errorcheck in SIGNATURES
             if errorcheck]

    unexpected = sorted(set(armed) - ARMED)
    assert unexpected == [], (
        "these rows install the errcheck hook without a measurement behind them "
        "(#195): " + ", ".join(unexpected)
    )


#: The symbols a real run measured as returning truthy, so arming them cannot turn an
#: ordinary call into a ``RuntimeError``. See AGENTS.md 2.7 and issue #195.
ARMED = {
    "getAccessibleTextInfo",
    "getAccessibleTextRange",
    "getAccessibleTableCellInfo",
    "getVisibleChildren",
    "getTopLevelObject",
    "setTextContents",
    "getVersionInfo",
}

#: Reached from all twelve ``except JABException`` blocks -- including two search loops that
#: today ``continue`` past a bad item. Armed, a falsy read would end the search and the caller
#: would get an exception instead of the partial result it used to get. Deliberately unarmed.
NEVER_ARMED = {"getAccessibleContextInfo"}


def test_only_the_measured_symbols_are_flagged():
    """``False`` rather than any falsy value, so the column stays a bool.

    Every row is either one of the seven a measurement cleared, or ``False``. A row flipped
    without a measurement fails here.
    """
    for name, _restype, _argtypes, errorcheck in SIGNATURES:
        expected = name in ARMED
        assert errorcheck is expected, (
            f"{name} is flagged {errorcheck!r}, expected {expected!r}"
        )


def test_the_symbol_on_every_except_path_is_never_armed():
    """The decision that is easiest to undo by accident.

    ``getAccessibleContextInfo`` is read by every property through ``_acc_info``, so it is
    reachable from every ``except JABException`` in the package -- two of which are search
    loops that would give up rather than skip. Nothing measured clears it.
    """
    for name, _restype, _argtypes, errorcheck in SIGNATURES:
        if name in NEVER_ARMED:
            assert errorcheck is False, f"{name} must never be armed"


def test_applying_the_table_installs_no_hook_on_any_symbol():
    """The invariant asserted through the code that acts on it.

    ``test_no_signature_row_is_flagged`` reads the table; this runs it against a
    bridge exporting every symbol. Both are needed, because a row could be armed
    by a change to ``_fix_bridge_functions`` rather than to the table.
    """
    names = [name for name, _restype, _argtypes, _errorcheck in SIGNATURES]
    bridge = _FakeBridge(*names)

    JABFixedFunc(bridge)._fix_bridge_functions()

    armed = sorted(name for name, func in bridge._funcs.items()
                   if func.errcheck is not None)

    # Exactly the measured seven, and nothing else -- not "none", which was the old
    # invariant, and not "at least these", which would let a row be armed in passing.
    assert armed == sorted(ARMED), (
        f"hooks were installed on {armed}; expected {sorted(ARMED)}"
    )
