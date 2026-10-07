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
    ("getAccessibleContextFromHWND", BOOL, (HWND, POINTER(c_long), POINTER(JOBJECT64)), True),
    ("getHWNDFromAccessibleContext", HWND, (c_long, JOBJECT64), True),
    ("getAccessibleContextAt", BOOL, (c_long, JOBJECT64, c_int, c_int, POINTER(JOBJECT64)), True),
    # No errorcheck, deliberately.  The caller treats a falsy result as "nothing
    # has focus", which is an ordinary answer about a window rather than a
    # failure of the call.  With errorcheck=True the hook raises RuntimeError
    # from inside the call and that branch can never run -- which is what
    # happened: get_focused_element() raised on a window with nothing focused,
    # having documented that it returns None.  See the note on _check_error.
    ("getAccessibleContextWithFocus", BOOL, (HWND, POINTER(c_long), POINTER(JOBJECT64)), False),
    ("getAccessibleContextInfo", BOOL, (c_long, JOBJECT64, POINTER(AccessibleContextInfo)), True),
    ("getAccessibleChildFromContext", JOBJECT64, (c_long, JOBJECT64, c_int), True),
    ("getAccessibleParentFromContext", JOBJECT64, (c_long, JOBJECT64), False),
    ("getParentWithRole", JOBJECT64, (c_long, JOBJECT64, POINTER(c_wchar)), False),
    ("getAccessibleRelationSet", BOOL, (c_long, JOBJECT64, POINTER(AccessibleRelationSetInfo)), True),
    ("getAccessibleTextInfo", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextInfo), c_int, c_int), True),
    ("getAccessibleTextItems", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextItemsInfo), c_int), True),
    ("getAccessibleTextSelectionInfo", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextSelectionInfo)), True),
    ("getAccessibleTextAttributes", BOOL, (
            c_long,
            JOBJECT64,
            c_int,
            POINTER(AccessibleTextAttributesInfo),
        ), True),
    ("getAccessibleTextRect", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextRectInfo), c_int), True),
    ("getAccessibleTextLineBounds", BOOL, (c_long, JOBJECT64, c_int, POINTER(c_int), POINTER(c_int)), True),
    ("getAccessibleTextRange", BOOL, (c_long, JOBJECT64, c_int, c_int, POINTER(c_char), c_short), True),
    ("getCurrentAccessibleValueFromContext", BOOL, (c_long, JOBJECT64, POINTER(c_wchar), c_short), True),
    ("selectTextRange", BOOL, (c_long, JOBJECT64, c_int, c_int), True),
    ("getTextAttributesInRange", BOOL, (
            c_long,
            JOBJECT64,
            c_int,
            c_int,
            POINTER(AccessibleTextAttributesInfo),
            POINTER(c_short),
        ), True),
    ("getTopLevelObject", JOBJECT64, (c_long, JOBJECT64), True),
    ("getObjectDepth", c_int, (c_long, JOBJECT64), False),
    ("getActiveDescendent", JOBJECT64, (c_long, JOBJECT64), False),
    ("requestFocus", BOOL, (c_long, JOBJECT64), True),
    ("setCaretPosition", BOOL, (c_long, JOBJECT64, c_int), True),
    ("getCaretLocation", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTextRectInfo), c_int), True),
    ("getAccessibleActions", BOOL, (c_long, JOBJECT64, POINTER(AccessibleActions)), True),
    ("doAccessibleActions", BOOL, (
            c_long,
            JOBJECT64,
            POINTER(AccessibleActionsToDo),
            POINTER(c_int),
        ), True),
    ("getAccessibleTableInfo", BOOL, (c_long, JOBJECT64, POINTER(AccessibleTableInfo)), False),
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
    ("getAccessibleKeyBindings", BOOL, (c_long, JOBJECT64, POINTER(AccessibleKeyBindings)), True),
    ("setTextContents", BOOL, (c_long, JOBJECT64, POINTER(c_wchar)), True),
    ("clearAccessibleSelectionFromContext", None, (c_long, JOBJECT64), False),
    ("addAccessibleSelectionFromContext", None, (c_long, JOBJECT64, c_int), False),
    ("getAccessibleSelectionFromContext", JOBJECT64, (c_long, JOBJECT64, c_int), False),
    ("getVisibleChildrenCount", c_int, (c_long, JOBJECT64), False),
    ("getVisibleChildren", BOOL, (c_long, JOBJECT64, c_int, POINTER(VisibleChildrenInfo)), True),
)


class JABFixedFunc(object):
    """Declares the JAB signatures on a loaded bridge DLL."""

    def __init__(self, bridge: CDLL) -> None:
        self.log = Logger("pyjab")
        self.bridge = bridge

    @staticmethod
    def _check_error(result, func, args):
        """errorcheck hook: turn a falsy result into a loud failure.

        Careful: this makes any ``if not result:`` written downstream dead code,
        because the exception arrives first.  Pick one mechanism per call --
        either this, or no errorcheck and a check of the result.  See AGENTS.md
        section 2.7 for the branches that were written and never run.
        """
        if not result:
            raise RuntimeError(f"Result {result}")
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
            func.errorcheck = self._check_error

    def _fix_bridge_functions(self):
        """Declare every signature in :data:`SIGNATURES` on the bridge DLL."""
        for name, restype, argtypes, errorcheck in SIGNATURES:
            self._fix_bridge_function(restype, name, *argtypes, errorcheck=errorcheck)
