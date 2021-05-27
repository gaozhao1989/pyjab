from ctypes import CDLL
from ctypes import c_char
from ctypes import c_int
from ctypes import c_long
from ctypes import c_short
from ctypes import c_void_p
from ctypes import c_wchar
from ctypes import POINTER
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
from pyjab.common.logger import Logger
from pyjab.common.types import JOBJECT64


class JABFixedFunc(object):
    def __init__(self, bridge: CDLL) -> None:
        self.log = Logger(self.__class__.__name__)
        self.bridge = bridge

    def _check_error(self, result, func, args):
        if not result:
            raise RuntimeError("Result {result}".format(result=result))
        return result

    def _fix_bridge_function(self, restype, name, *argtypes, **kwargs):
        try:
            func = getattr(self.bridge, name)
        except AttributeError:
            self.log.error(
                "{name} not found in Java Access Bridge DLL".format(name=name)
            )
            return
        func.restype = restype
        func.argtypes = argtypes
        if kwargs.get("errorcheck"):
            func.errorcheck = self._check_error

    def _fix_bridge_functions(self):
        """Appropriately set the return and argument types of all the access bridge dll functions"""
        self._fix_bridge_function(None, "Windows_run")
        self._fix_bridge_function(None, "setFocusGainedFP", c_void_p)
        self._fix_bridge_function(None, "setPropertyNameChangeFP", c_void_p)
        self._fix_bridge_function(None, "setPropertyDescriptionChangeFP", c_void_p)
        self._fix_bridge_function(None, "setPropertyValueChangeFP", c_void_p)
        self._fix_bridge_function(None, "setPropertyStateChangeFP", c_void_p)
        self._fix_bridge_function(None, "setPropertyCaretChangeFP", c_void_p)
        self._fix_bridge_function(None, "setPropertyActiveDescendentChangeFP", c_void_p)
        self._fix_bridge_function(None, "releaseJavaObject", c_long, JOBJECT64)
        self._fix_bridge_function(
            BOOL,
            "getVersionInfo",
            c_long,
            POINTER(AccessBridgeVersionInfo),
            errorcheck=True,
        )
        self._fix_bridge_function(BOOL, "isJavaWindow", HWND)
        self._fix_bridge_function(BOOL, "isSameObject", c_long, JOBJECT64, JOBJECT64)
        self._fix_bridge_function(
            BOOL,
            "getAccessibleContextFromHWND",
            HWND,
            POINTER(c_long),
            POINTER(JOBJECT64),
            errorcheck=True,
        )
        self._fix_bridge_function(
            HWND, "getHWNDFromAccessibleContext", c_long, JOBJECT64, errorcheck=True
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleContextAt",
            c_long,
            JOBJECT64,
            c_int,
            c_int,
            POINTER(JOBJECT64),
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleContextWithFocus",
            HWND,
            POINTER(c_long),
            POINTER(JOBJECT64),
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleContextInfo",
            c_long,
            JOBJECT64,
            POINTER(AccessibleContextInfo),
            errorcheck=True,
        )
        self._fix_bridge_function(
            JOBJECT64,
            "getAccessibleChildFromContext",
            c_long,
            JOBJECT64,
            c_int,
            errorcheck=True,
        )
        self._fix_bridge_function(
            JOBJECT64, "getAccessibleParentFromContext", c_long, JOBJECT64
        )
        self._fix_bridge_function(
            JOBJECT64, "getParentWithRole", c_long, JOBJECT64, POINTER(c_wchar)
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleRelationSet",
            c_long,
            JOBJECT64,
            POINTER(AccessibleRelationSetInfo),
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTextInfo",
            c_long,
            JOBJECT64,
            POINTER(AccessibleTextInfo),
            c_int,
            c_int,
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTextItems",
            c_long,
            JOBJECT64,
            POINTER(AccessibleTextItemsInfo),
            c_int,
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTextSelectionInfo",
            c_long,
            JOBJECT64,
            POINTER(AccessibleTextSelectionInfo),
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTextAttributes",
            c_long,
            JOBJECT64,
            c_int,
            POINTER(AccessibleTextAttributesInfo),
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTextRect",
            c_long,
            JOBJECT64,
            POINTER(AccessibleTextRectInfo),
            c_int,
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTextLineBounds",
            c_long,
            JOBJECT64,
            c_int,
            POINTER(c_int),
            POINTER(c_int),
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTextRange",
            c_long,
            JOBJECT64,
            c_int,
            c_int,
            POINTER(c_char),
            c_short,
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getCurrentAccessibleValueFromContext",
            c_long,
            JOBJECT64,
            POINTER(c_wchar),
            c_short,
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL, "selectTextRange", c_long, JOBJECT64, c_int, c_int, errorcheck=True
        )
        self._fix_bridge_function(
            BOOL,
            "getTextAttributesInRange",
            c_long,
            JOBJECT64,
            c_int,
            c_int,
            POINTER(AccessibleTextAttributesInfo),
            POINTER(c_short),
            errorcheck=True,
        )
        self._fix_bridge_function(
            JOBJECT64, "getTopLevelObject", c_long, JOBJECT64, errorcheck=True
        )
        self._fix_bridge_function(c_int, "getObjectDepth", c_long, JOBJECT64)
        self._fix_bridge_function(JOBJECT64, "getActiveDescendent", c_long, JOBJECT64)
        self._fix_bridge_function(
            BOOL, "requestFocus", c_long, JOBJECT64, errorcheck=True
        )
        self._fix_bridge_function(
            BOOL, "setCaretPosition", c_long, JOBJECT64, c_int, errorcheck=True
        )
        self._fix_bridge_function(
            BOOL,
            "getCaretLocation",
            c_long,
            JOBJECT64,
            POINTER(AccessibleTextRectInfo),
            c_int,
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleActions",
            c_long,
            JOBJECT64,
            POINTER(AccessibleActions),
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "doAccessibleActions",
            c_long,
            JOBJECT64,
            POINTER(AccessibleActionsToDo),
            POINTER(c_int),
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTableInfo",
            c_long,
            JOBJECT64,
            POINTER(AccessibleTableInfo),
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTableCellInfo",
            c_long,
            JOBJECT64,
            c_int,
            c_int,
            POINTER(AccessibleTableCellInfo),
            errorcheck=True,
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTableRowHeader",
            c_long,
            JOBJECT64,
            POINTER(AccessibleTableInfo),
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleTableColumnHeader",
            c_long,
            JOBJECT64,
            POINTER(AccessibleTableInfo),
        )
        self._fix_bridge_function(
            JOBJECT64, "getAccessibleTableRowDescription", c_long, JOBJECT64, c_int
        )
        self._fix_bridge_function(
            JOBJECT64, "getAccessibleTableColumnDescription", c_long, JOBJECT64, c_int
        )
        self._fix_bridge_function(
            c_int, "getAccessibleTableRow", c_long, JOBJECT64, c_int
        )
        self._fix_bridge_function(
            c_int, "getAccessibleTableColumn", c_long, JOBJECT64, c_int
        )
        self._fix_bridge_function(
            c_int, "getAccessibleTableIndex", c_long, JOBJECT64, c_int, c_int
        )
        self._fix_bridge_function(
            BOOL,
            "getAccessibleKeyBindings",
            c_long,
            JOBJECT64,
            POINTER(AccessibleKeyBindings),
            errorcheck=True,
        )
