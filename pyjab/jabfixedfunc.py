"""ctypes signatures for the Java Access Bridge C API.

Java Access Bridge is a DLL the JDK installs, and ctypes needs to be told the
result and argument type of every function it calls.  Without that, ctypes
assumes a C ``int`` for integer arguments -- so a 64-bit object handle passed as
a Python ``int`` quietly loses its top half -- and assumes an ``int`` result.

What follows is the interface rather than a design: the symbol names are the
ones ``WinAccessBridge.DEF`` exports, and the types are the ones
``AccessBridgeCalls.h`` and the structures in :mod:`pyjab.accessibleinfo`
declare.  Nobody chooses them, and a mistake here produces a wrong answer rather
than an exception, so ``tools/check_jab_symbols.py`` compares the names below
against a DEF file taken from a real JDK.
"""

from ctypes import CDLL
from ctypes import POINTER
from ctypes import c_char
from ctypes import c_int
from ctypes import c_long
from ctypes import c_short
from ctypes import c_void_p
from ctypes import c_wchar
from ctypes.wintypes import BOOL
from ctypes.wintypes import HWND
from pyjab.accessibleinfo import AccessBridgeVersionInfo
from pyjab.accessibleinfo import AccessibleActions
from pyjab.accessibleinfo import AccessibleActionsToDo
from pyjab.accessibleinfo import AccessibleContextInfo
from pyjab.accessibleinfo import AccessibleKeyBindings
from pyjab.accessibleinfo import AccessibleRelationSetInfo
from pyjab.accessibleinfo import AccessibleTableCellInfo
from pyjab.accessibleinfo import AccessibleTableInfo
from pyjab.accessibleinfo import AccessibleTextAttributesInfo
from pyjab.accessibleinfo import AccessibleTextInfo
from pyjab.accessibleinfo import AccessibleTextItemsInfo
from pyjab.accessibleinfo import AccessibleTextRectInfo
from pyjab.accessibleinfo import AccessibleTextSelectionInfo
from pyjab.accessibleinfo import VisibleChildrenInfo
from pyjab.common.logger import Logger
from pyjab.common.types import JOBJECT64


#: The Java Access Bridge functions pyjab calls.
#:
#: Each entry is ``(symbol, result type, argument types, errorcheck)``.  The
#: order is the one this table has always had -- the event callbacks first, then
#: the lookups -- and is kept only so it reads in groups; ctypes does not care.
#:
#: **Five rows carry ``True``, and a measurement is the only reason any of them
#: does.**  ``getVersionInfo``, ``getAccessibleTextInfo``, ``getAccessibleTextRange``,
#: ``getAccessibleTableCellInfo`` and ``setTextContents`` were measured by the
#: ``windows-gui.yml`` task ``jab-return-values`` (run 38071056432, JDK 17) and every
#: one read ``1``.  None of the five is reached from an ``except JABException``
#: handler, so the hook cannot turn a caught failure into an uncaught one.
#:
#: **Every other row carries ``False``**, and three of those are decisions rather
#: than defaults.  ``getVisibleChildren`` and ``getTopLevelObject`` were measured
#: truthy by that run too, and are still left unarmed, because the run only reached
#: them on a live path:
#:
#: * ``getVisibleChildren`` is called on **every** element by the ``visible=True``
#:   walk, and the project's own record (the measurement tool's second control, in
#:   the unreleased changelog) is that a **childless panel comes back falsy**.  The
#:   clearing run drove it on the root window, so the falsy case was never measured.
#:   A falsy result there is caught by the two search loops at ``jabelement.py:2096``
#:   and ``:2521``, which ``continue``; armed it would be ``RuntimeError`` and the
#:   search would end instead of skipping the item -- the defect that keeps
#:   ``getAccessibleContextInfo`` unarmed, reached the same way.
#: * ``getTopLevelObject`` documents ``(AccessibleContext)0`` as its error answer and
#:   ``_get_top_level_object`` checks for it by hand, and ``_xpath_search_root`` calls
#:   it fresh -- nothing is cached, and no readable context is proven a few lines up
#:   -- on every absolute locator.  It is reachable from five handlers
#:   (``jabelement.py:2096``, ``:2521``, ``jabdriver.py:461``, ``:715``,
#:   ``inspector.py:175``).  One truthy measurement on a live element does not clear
#:   the failing path.
#:
#: ``getAccessibleContextInfo`` is the third deliberate ``False``: ``_acc_info`` reads
#: it for every property, which puts it on the path of every ``except JABException``
#: handler in the package.  All three keep their hand-written ``if not result:``
#: check live.
#:
#: The five armed rows keep **no** check of their own: it was removed in #217, because
#: a check that cannot run reads as working code.  What those checks used to say -- the
#: symbol that failed, and ``setTextContents``'s ``simulate`` hint -- is carried by the
#: hook's message instead; see :data:`ERRCHECK_HINTS`.
#:
#: Arming is not free.  The hook makes the caller's own ``if not result:`` check
#: unreachable, and it turns a falsy result into ``RuntimeError`` **from inside the
#: call**, so the ``except JABException`` blocks in ``jabelement.py``,
#: ``jabdriver.py`` and ``inspector.py`` stop catching.  It also covers only a
#: falsy ``0``: ``-1`` is truthy and is how some calls report an error.  Flip one
#: row to ``True`` only with a measurement behind it -- of the failing path, not only
#: of the path that worked.
#:
#: ``tests/test_errorcheck_binding.py`` asserts the mechanism, the armed set, and
#: that ``getAccessibleContextInfo`` is not in it.
SIGNATURES = (
    ("Windows_run", None, (), False),
    ("setFocusGainedFP", None, (c_void_p,), False),
    ("setPropertyNameChangeFP", None, (c_void_p,), False),
    ("setPropertyDescriptionChangeFP", None, (c_void_p,), False),
    ("setPropertyValueChangeFP", None, (c_void_p,), False),
    ("setPropertyStateChangeFP", None, (c_void_p,), False),
    ("setPropertyCaretChangeFP", None, (c_void_p,), False),
    ("setPropertyActiveDescendentChangeFP", None, (c_void_p,), False),
    ("releaseJavaObject", None, (c_long, JOBJECT64), False),
    ("getVersionInfo", BOOL, (c_long, POINTER(AccessBridgeVersionInfo)), True),
    ("isJavaWindow", BOOL, (HWND,), False),
    ("isSameObject", BOOL, (c_long, JOBJECT64, JOBJECT64), False),
    ("getAccessibleContextFromHWND", BOOL, (HWND, POINTER(c_long), POINTER(JOBJECT64)), False),
    ("getHWNDFromAccessibleContext", HWND, (c_long, JOBJECT64), False),
    ("getAccessibleContextAt", BOOL, (c_long, JOBJECT64, c_int, c_int, POINTER(JOBJECT64)), False),
    # Deliberately unarmed.  The caller treats a falsy result as "nothing
    # has focus", which is an ordinary answer about a window rather than a
    # failure of the call.  Arming this row would install the hook, the
    # RuntimeError would arrive from inside the call, and that branch could
    # never run -- while get_focused_element() documents that it returns None.
    # See the note on _check_error.
    ("getAccessibleContextWithFocus", BOOL, (HWND, POINTER(c_long), POINTER(JOBJECT64)), False),
    ("getAccessibleContextInfo", BOOL, (c_long, JOBJECT64, POINTER(AccessibleContextInfo)), False),
    ("getAccessibleChildFromContext", JOBJECT64, (c_long, JOBJECT64, c_int), False),
    ("getAccessibleParentFromContext", JOBJECT64, (c_long, JOBJECT64), False),
    ("getParentWithRole", JOBJECT64, (c_long, JOBJECT64, POINTER(c_wchar)), False),
    ("getAccessibleRelationSet", BOOL, (c_long, JOBJECT64, POINTER(AccessibleRelationSetInfo)), False),
    # Armed: measured 1 under jab-return-values.  Reached only from
    # JABElement.text, and no except JABException block sits on that path.
    ("getAccessibleTextInfo", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextInfo), c_int, c_int), True),
    ("getAccessibleTextItems", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextItemsInfo), c_int), False),
    ("getAccessibleTextSelectionInfo", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextSelectionInfo)), False),
    ("getAccessibleTextAttributes", BOOL, (
            c_long,
            JOBJECT64,
            c_int,
            POINTER(AccessibleTextAttributesInfo),
        ), False),
    ("getAccessibleTextRect", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextRectInfo), c_int), False),
    ("getAccessibleTextLineBounds", BOOL, (c_long, JOBJECT64, c_int, POINTER(c_int), POINTER(c_int)), False),
    # Armed: measured 1 under jab-return-values, and reached from JABElement.text
    # -- the same path as getAccessibleTextInfo above.
    ("getAccessibleTextRange", BOOL, (c_long, JOBJECT64, c_int, c_int, POINTER(c_char), c_short), True),
    ("getCurrentAccessibleValueFromContext", BOOL, (c_long, JOBJECT64, POINTER(c_wchar), c_short), False),
    ("selectTextRange", BOOL, (c_long, JOBJECT64, c_int, c_int), False),
    ("getTextAttributesInRange", BOOL, (
            c_long,
            JOBJECT64,
            c_int,
            c_int,
            POINTER(AccessibleTextAttributesInfo),
            POINTER(c_short),
        ), False),
    # Measured a non-null JOBJECT64 (jab-return-values), and deliberately **left
    # unarmed**: JAB documents (AccessibleContext)0 as this call's error answer, and
    # _get_top_level_object checks for it by hand.  _xpath_search_root calls it fresh
    # -- nothing cached, no readable context proven just above -- on every absolute
    # locator, which puts it inside the xpath union loops in find_element_by_xpath /
    # find_elements_by_xpath, _search_from_root, wait_until_element_exist and
    # step_report.  Those blocks catch JABException and continue or report; the
    # RuntimeError this hook raises they would not catch, so a failed lookup would
    # become an uncaught one.  One truthy measurement on a live element does not clear
    # the failing path.
    ("getTopLevelObject", JOBJECT64, (c_long, JOBJECT64), False),
    ("getObjectDepth", c_int, (c_long, JOBJECT64), False),
    ("getActiveDescendent", JOBJECT64, (c_long, JOBJECT64), False),
    ("requestFocus", BOOL, (c_long, JOBJECT64), False),
    ("setCaretPosition", BOOL, (c_long, JOBJECT64, c_int), False),
    ("getCaretLocation", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextRectInfo), c_int), False),
    ("getAccessibleActions", BOOL, (c_long, JOBJECT64, POINTER(AccessibleActions)), False),
    ("doAccessibleActions", BOOL, (
            c_long,
            JOBJECT64,
            POINTER(AccessibleActionsToDo),
            POINTER(c_int),
        ), False),
    ("getAccessibleTableInfo", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTableInfo)), False),
    # Armed: measured 1 under jab-return-values.  Reached only from get_cell,
    # which no except JABException block wraps.
    ("getAccessibleTableCellInfo", BOOL, (
            c_long,
            JOBJECT64,
            c_int,
            c_int,
            POINTER(AccessibleTableCellInfo),
        ), True),
    ("getAccessibleTableRowHeader", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTableInfo)), False),
    ("getAccessibleTableColumnHeader", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTableInfo)), False),
    # These two were called from JABElement without ever being declared here, so
    # ctypes had no argument types to work from and converted the 64-bit
    # accessible_table handle to a C int.  The call still returns a number, which
    # is why it went unnoticed -- it was quietly asking about the wrong object
    # whenever the handle did not fit in 32 bits.
    ("getAccessibleTableRowSelectionCount", c_int, (c_long, JOBJECT64), False),
    ("getAccessibleTableColumnSelectionCount", c_int, (c_long, JOBJECT64), False),
    ("getAccessibleTableRowDescription", JOBJECT64, (c_long, JOBJECT64, c_int), False),
    ("getAccessibleTableColumnDescription", JOBJECT64, (c_long, JOBJECT64, c_int), False),
    ("getAccessibleTableRow", c_int, (c_long, JOBJECT64, c_int), False),
    ("getAccessibleTableColumn", c_int, (c_long, JOBJECT64, c_int), False),
    ("getAccessibleTableIndex", c_int, (c_long, JOBJECT64, c_int, c_int), False),
    # Reading a table's selection.  JAB fills the array and the count comes from
    # getAccessibleTable{Row,Column}SelectionCount above: pass the count you asked
    # for, get the indices back.  Deliberately unarmed, because a falsy return is
    # how JAB says it could not answer, and the wrappers turn that into a
    # JABException carrying the symbol name.
    ("getAccessibleTableRowSelections", BOOL, (
        c_long,
        JOBJECT64,
        c_int,
        POINTER(c_int),
    ), False),
    ("getAccessibleTableColumnSelections", BOOL, (
        c_long,
        JOBJECT64,
        c_int,
        POINTER(c_int),
    ), False),
    # Deliberately unarmed -- the same reasoning as getAccessibleContextWithFocus.
    # False means "this row is not selected", which is an ordinary answer about a
    # table rather than a failed call.  Arming it would raise RuntimeError on every
    # unselected row, so "is row 3 selected?" could only ever be answered yes.
    ("isAccessibleTableRowSelected", BOOL, (c_long, JOBJECT64, c_int), False),
    ("isAccessibleTableColumnSelected", BOOL, (c_long, JOBJECT64, c_int), False),
    # Unarmed for the same reason a third time: False means "this cell is not
    # selected", which is an ordinary answer about a table rather than a failed
    # call.  This is the predicate that makes addAccessibleSelection's toggle
    # usable -- for a JTable it is isCellSelected(row, column), which is the same
    # question changeSelection asks itself, so select_row can stop after the
    # first cell instead of toggling the row back off.  See JABElement.select_row.
    ("isAccessibleChildSelectedFromContext", BOOL, (c_long, JOBJECT64, c_int), False),
    ("getAccessibleKeyBindings", BOOL, (c_long, JOBJECT64, POINTER(AccessibleKeyBindings)), False),
    # Armed: measured 1 under jab-return-values.  Reached only from send_text;
    # spin's except JABException wraps the role lookup above that call, not it.
    ("setTextContents", BOOL, (c_long, JOBJECT64, POINTER(c_wchar)), True),
    ("clearAccessibleSelectionFromContext", None, (c_long, JOBJECT64), False),
    ("addAccessibleSelectionFromContext", None, (c_long, JOBJECT64, c_int), False),
    ("getAccessibleSelectionFromContext", JOBJECT64, (c_long, JOBJECT64, c_int), False),
    # Deliberately unarmed: 0 means "nothing is selected", which is the answer for
    # every freshly-opened list and every table.  Arming it would make
    # get_selected_elements() raise on exactly the case it is most often asked
    # about -- the trap AGENTS.md section 2.7 describes, in its purest form.
    ("getAccessibleSelectionCountFromContext", c_int, (c_long, JOBJECT64), False),
    ("removeAccessibleSelectionFromContext", None, (c_long, JOBJECT64, c_int), False),
    ("selectAllAccessibleSelectionFromContext", None, (c_long, JOBJECT64), False),
    ("getVisibleChildrenCount", c_int, (c_long, JOBJECT64), False),
    # Measured 1 (jab-return-values), on the root window, and deliberately **left
    # unarmed**.  Every element is passed through this call by the visible=True walk,
    # and a childless panel answers falsy -- the measurement tool's own second control
    # says so, which is why the clearing run's single truthy read does not cover it.
    # A falsy result is caught today by the two search loops in find_element_by_xpath /
    # find_elements_by_xpath, which continue; the hook's RuntimeError they would not
    # catch, so the search would end instead of skipping the item.
    ("getVisibleChildren", BOOL, (c_long, JOBJECT64, c_int, POINTER(VisibleChildrenInfo)), False),
)

#: Guidance the hook appends to its message, keyed by symbol.
#:
#: The hook exists because arming a row made the caller's own ``if not result:`` check
#: unreachable -- so the message it raises is now the only place a caller is told what
#: went wrong, and anything the hand-written check used to say has to be said here
#: instead (#217).  Every armed row gets the symbol name from ``func.__name__``; this
#: table is for guidance that is specific to one call, and is deliberately sparse
#: rather than a second copy of the armed set.
ERRCHECK_HINTS = {
    "setTextContents": "try set parameter 'simulate' with True",
}


class JABFixedFunc(object):
    """Declares the JAB signatures on a loaded bridge DLL."""

    def __init__(self, bridge: CDLL) -> None:
        self.log = Logger("pyjab")
        self.bridge = bridge

    @staticmethod
    def _check_error(result, func, args):
        """ctypes ``errcheck`` hook: turn a falsy result into a loud failure.

        Installed on the five symbols whose :data:`SIGNATURES` row carries
        ``True`` -- the ones a run measured returning truthy at pyjab's own call
        sites *and* that no ``except JABException`` handler is reachable from
        (``windows-gui.yml`` task ``jab-return-values``, run 38071056432).  Every
        other row stays ``False``: arming is decided per row, against both halves
        of that evidence (#195).  ``errcheck`` is the name ctypes reads -- spelled
        ``errorcheck`` the assignment set an inert Python attribute and no hook was
        ever installed, which is the defect this spelling fixes.

        Careful when arming a row: this makes any ``if not result:`` written
        downstream dead code, because the exception arrives first.  Pick one
        mechanism per call -- either this, or no hook and a check of the result.

        It also does not cover everything.  It raises on a falsy ``0``, while
        some JAB calls answer with a truthy ``-1`` instead (``getObjectDepth``,
        checked by hand in ``jabelement.py``), so arming a row is not a
        substitute for knowing what that call returns on failure.

        The message carries the symbol name, taken from the function pointer ctypes
        populated it on, plus whatever :data:`ERRCHECK_HINTS` holds for it.  That is
        where the information the removed call-site checks used to carry now lives:
        the check they replaced could never run, so its message could not either.
        """
        if not result:
            name = getattr(func, "__name__", None)
            hint = getattr(func, "_pyjab_error_hint", None)
            where = f" from '{name}'" if name else ""
            advice = f"; {hint}" if hint else ""
            raise RuntimeError(f"Result {result}{where}{advice}")
        return result

    def _fix_bridge_function(self, restype, name, *argtypes, **kwargs):
        """Declare one symbol, if the DLL exports it."""
        try:
            func = getattr(self.bridge, name)
        except AttributeError:
            self.log.error(f"{name} not found in Java Access Bridge DLL")
            return
        func.restype = restype
        func.argtypes = argtypes
        if kwargs.get("errorcheck"):
            func.errcheck = self._check_error
            hint = ERRCHECK_HINTS.get(name)
            if hint:
                func._pyjab_error_hint = hint

    def _fix_bridge_functions(self):
        """Declare every signature in :data:`SIGNATURES` on the bridge DLL."""
        for name, restype, argtypes, errorcheck in SIGNATURES:
            self._fix_bridge_function(restype, name, *argtypes, errorcheck=errorcheck)
