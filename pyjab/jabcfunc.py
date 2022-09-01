from ctypes import CDLL, POINTER, c_int, c_long, c_short, c_void_p, c_wchar
from ctypes.wintypes import BOOL, HWND
from pyjab.jabdatastr import (
    AccessBridgeVersionInfo,
    AccessibleActions,
    AccessibleActionsToDo,
    AccessibleContextInfo,
    AccessibleHyperlinkInfo,
    AccessibleHypertextInfo,
    AccessibleIcons,
    AccessibleKeyBindings,
    AccessibleRelationSetInfo,
    AccessibleTableCellInfo,
    AccessibleTableInfo,
    AccessibleTextAttributesInfo,
    AccessibleTextInfo,
    AccessibleTextItemsInfo,
    AccessibleTextRectInfo,
    AccessibleTextSelectionInfo,
    VisibleChildrenInfo,
)
from pyjab.common.logger import Logger
from pyjab.common.types import (
    JOBJECT64,
    AccessibleContext,
    AccessibleHyperlink,
    AccessibleHypertext,
    AccessibleSelection,
    AccessibleTable,
    AccessibleText,
    AccessibleValue,
    jint,
)


class JABCFunc(object):
    def __init__(self, bridge: CDLL) -> None:
        self.logger = Logger("pyjab")
        self.bridge = bridge

    @staticmethod
    def check_error(result, func, args):
        if not result:
            raise RuntimeError(f"Result {result}")
        return result

    def reset_func(self, restype, name, *argtypes, **kwargs):
        try:
            func = getattr(self.bridge, name)
        except AttributeError:
            self.logger.error(
                f"JAB function '{name}' not found in Java Access Bridge DLL"
            )
            return
        func.restype = restype
        func.argtypes = argtypes
        if kwargs.get("check_error"):
            func.check_error = self.check_error

    def reset_funcs(self):
        """Appropriately set the return and argument types of all the access bridge dll functions"""
        self.reset_func(None, "Windows_run")

        # Window routines
        self.reset_func(BOOL, "isJavaWindow", HWND, check_error=True)
        self.reset_func(
            BOOL,
            "getAccessibleContextFromHWND",
            HWND,
            POINTER(c_long),
            POINTER(AccessibleContext),
            check_error=True,
        )
        self.reset_func(
            HWND,
            "getHWNDFromAccessibleContext",
            c_long,
            AccessibleContext,
            check_error=True,
        )

        # Event handling routines
        self.reset_func(None, "setJavaShutdownFP", c_void_p)
        self.reset_func(None, "setFocusGainedFP", c_void_p)
        self.reset_func(None, "setFocusFocusLostFP", c_void_p)
        self.reset_func(None, "setCaretUpdateFP", c_void_p)
        self.reset_func(None, "setMouseClickedFP", c_void_p)
        self.reset_func(None, "setMouseEnteredFP", c_void_p)
        self.reset_func(None, "setMouseExitedFP", c_void_p)
        self.reset_func(None, "setMousePressedFP", c_void_p)
        self.reset_func(None, "setMouseReleasedFP", c_void_p)
        self.reset_func(None, "setMenuCanceledFP", c_void_p)
        self.reset_func(None, "setMenuDeselectedFP", c_void_p)
        self.reset_func(None, "setMenuSelectedFP", c_void_p)
        self.reset_func(None, "setPopupMenuCanceledFP", c_void_p)
        self.reset_func(None, "setPopupMenuWillBecomeInvisibleFP", c_void_p)
        self.reset_func(None, "setPopupMenuWillBecomeVisibleFP", c_void_p)
        self.reset_func(None, "setPropertyNameChangeFP", c_void_p)
        self.reset_func(None, "setPropertyDescriptionChangeFP", c_void_p)
        self.reset_func(None, "setPropertyStateChangeFP", c_void_p)
        self.reset_func(None, "setPropertyValueChangeFP", c_void_p)
        self.reset_func(None, "setPropertySelectionChangeFP", c_void_p)
        self.reset_func(None, "setPropertyTextChangeFP", c_void_p)
        self.reset_func(None, "setPropertyCaretChangeFP", c_void_p)
        self.reset_func(None, "setPropertyVisibleDataChangeFP", c_void_p)
        self.reset_func(None, "setPropertyChildChangeFP", c_void_p)
        self.reset_func(None, "setPropertyActiveDescendentChangeFP", c_void_p)
        self.reset_func(None, "setPropertyTableModelChangeFP", c_void_p)

        # General routines
        self.reset_func(None, "releaseJavaObject", c_long, JOBJECT64)
        self.reset_func(
            BOOL,
            "getVersionInfo",
            c_long,
            POINTER(AccessBridgeVersionInfo),
            check_error=True,
        )

        # Accessible Context routines
        self.reset_func(
            BOOL,
            "getAccessibleContextAt",
            c_long,
            AccessibleContext,
            jint,
            jint,
            POINTER(AccessibleContext),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleContextWithFocus",
            HWND,
            POINTER(c_long),
            POINTER(AccessibleContext),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleContextInfo",
            c_long,
            AccessibleContext,
            POINTER(AccessibleContextInfo),
            check_error=True,
        )
        self.reset_func(
            AccessibleContext,
            "getAccessibleChildFromContext",
            c_long,
            AccessibleContext,
            jint,
            check_error=True,
        )
        self.reset_func(
            AccessibleContext,
            "getAccessibleParentFromContext",
            c_long,
            AccessibleContext,
            check_error=True,
        )

        # Accessible Text routines
        self.reset_func(
            BOOL,
            "getAccessibleTextInfo",
            c_long,
            AccessibleText,
            POINTER(AccessibleTextInfo),
            jint,
            jint,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTextItems",
            c_long,
            AccessibleText,
            POINTER(AccessibleTextItemsInfo),
            jint,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTextSelectionInfo",
            c_long,
            AccessibleText,
            POINTER(AccessibleTextSelectionInfo),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTextAttributes",
            c_long,
            AccessibleText,
            jint,
            POINTER(AccessibleTextAttributesInfo),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTextRect",
            c_long,
            AccessibleText,
            POINTER(AccessibleTextRectInfo),
            jint,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTextLineBounds",
            c_long,
            AccessibleText,
            jint,
            POINTER(jint),
            POINTER(jint),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTextRange",
            c_long,
            AccessibleText,
            jint,
            jint,
            POINTER(c_wchar),
            c_short,
            check_error=True,
        )

        # AccessibleTable routines
        self.reset_func(
            BOOL,
            "getAccessibleTableInfo",
            c_long,
            AccessibleContext,
            POINTER(AccessibleTableInfo),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTableCellInfo",
            c_long,
            AccessibleTable,
            jint,
            jint,
            POINTER(AccessibleTableCellInfo),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTableRowHeader",
            c_long,
            AccessibleContext,
            POINTER(AccessibleTableInfo),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTableColumnHeader",
            c_long,
            AccessibleContext,
            POINTER(AccessibleTableInfo),
            check_error=True,
        )
        self.reset_func(
            AccessibleContext,
            "getAccessibleTableRowDescription",
            c_long,
            AccessibleContext,
            jint,
            check_error=True,
        )
        self.reset_func(
            AccessibleContext,
            "getAccessibleTableColumnDescription",
            c_long,
            AccessibleContext,
            jint,
            check_error=True,
        )
        self.reset_func(
            jint,
            "getAccessibleTableRowSelectionCount",
            c_long,
            AccessibleTable,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "isAccessibleTableRowSelected",
            c_long,
            AccessibleTable,
            jint,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTableRowSelections",
            c_long,
            AccessibleTable,
            jint,
            POINTER(jint),
            check_error=True,
        )
        self.reset_func(
            jint,
            "getAccessibleTableColumnSelectionCount",
            c_long,
            AccessibleTable,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "isAccessibleTableColumnSelected",
            c_long,
            AccessibleTable,
            jint,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleTableColumnSelections",
            c_long,
            AccessibleTable,
            jint,
            POINTER(jint),
            check_error=True,
        )
        self.reset_func(
            jint,
            "getAccessibleTableRow",
            c_long,
            AccessibleTable,
            jint,
            check_error=True,
        )
        self.reset_func(
            jint,
            "getAccessibleTableColumn",
            c_long,
            AccessibleTable,
            jint,
            check_error=True,
        )
        self.reset_func(
            jint,
            "getAccessibleTableIndex",
            c_long,
            AccessibleTable,
            jint,
            jint,
            check_error=True,
        )

        # AccessibleRelationSet routines
        self.reset_func(
            BOOL,
            "getAccessibleRelationSet",
            c_long,
            AccessibleContext,
            POINTER(AccessibleRelationSetInfo),
            check_error=True,
        )

        # AccessibleHypertext routines
        self.reset_func(
            BOOL,
            "getAccessibleHypertext",
            c_long,
            AccessibleContext,
            POINTER(AccessibleHypertextInfo),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "activateAccessibleHyperlink",
            c_long,
            AccessibleContext,
            AccessibleHyperlink,
            check_error=True,
        )
        self.reset_func(
            jint,
            "getAccessibleHyperlinkCount",
            c_long,
            AccessibleHypertext,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleHypertextExt",
            c_long,
            AccessibleContext,
            jint,
            POINTER(AccessibleHypertextInfo),
            check_error=True,
        )
        self.reset_func(
            jint,
            "getAccessibleHypertextLinkIndex",
            c_long,
            AccessibleHypertext,
            jint,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getAccessibleHyperlink",
            c_long,
            AccessibleHypertext,
            jint,
            POINTER(AccessibleHyperlinkInfo),
            check_error=True,
        )

        # AccessibleKeyBindings routines
        self.reset_func(
            BOOL,
            "getAccessibleKeyBindings",
            c_long,
            AccessibleContext,
            POINTER(AccessibleKeyBindings),
            check_error=True,
        )

        # AccessibleIcons
        self.reset_func(
            BOOL,
            "getAccessibleIcons",
            c_long,
            AccessibleContext,
            POINTER(AccessibleIcons),
            check_error=True,
        )

        # AccessibleActions
        self.reset_func(
            BOOL,
            "getAccessibleActions",
            c_long,
            AccessibleContext,
            POINTER(AccessibleActions),
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "doAccessibleActions",
            c_long,
            AccessibleContext,
            POINTER(AccessibleActionsToDo),
            POINTER(jint),
            check_error=True,
        )

        # Additional
        self.reset_func(
            BOOL, "isSameObject", c_long, JOBJECT64, JOBJECT64, check_error=True
        )
        self.reset_func(
            BOOL,
            "setTextContents",
            c_long,
            AccessibleContext,
            POINTER(c_wchar),
            check_error=True,
        )
        self.reset_func(
            AccessibleContext,
            "getParentWithRole",
            c_long,
            AccessibleContext,
            POINTER(c_wchar),
            check_error=True,
        )
        self.reset_func(
            AccessibleContext,
            "getParentWithRoleElseRoot",
            c_long,
            AccessibleContext,
            POINTER(c_wchar),
            check_error=True,
        )
        self.reset_func(
            AccessibleContext,
            "getTopLevelObject",
            c_long,
            AccessibleContext,
            check_error=True,
        )
        self.reset_func(
            c_int,
            "getObjectDepth",
            c_long,
            AccessibleContext,
            check_error=True,
        )
        self.reset_func(
            AccessibleContext,
            "getActiveDescendent",
            c_long,
            AccessibleContext,
            check_error=True,
        )

        # AccessibleValue routines
        self.reset_func(
            BOOL,
            "getCurrentAccessibleValueFromContext",
            c_long,
            AccessibleValue,
            POINTER(c_wchar),
            c_short,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getMaximumAccessibleValueFromContext",
            c_long,
            AccessibleValue,
            POINTER(c_wchar),
            c_short,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getMinimumAccessibleValueFromContext",
            c_long,
            AccessibleValue,
            POINTER(c_wchar),
            c_short,
            check_error=True,
        )

        # AccessibleSelection routines
        self.reset_func(
            None, "addAccessibleSelectionFromContext", c_long, AccessibleSelection, c_int
        )
        self.reset_func(
            None, "clearAccessibleSelectionFromContext", c_long, AccessibleSelection
        )
        self.reset_func(
            JOBJECT64, "getAccessibleSelectionFromContext", c_long, AccessibleSelection, c_int, error_check=True
        )
        self.reset_func(
            c_int, "getAccessibleSelectionCountFromContext", c_long, AccessibleSelection,error_check=True
        )
        self.reset_func(
            BOOL, "isAccessibleChildSelectedFromContext", c_long, AccessibleSelection,c_int,error_check=True
        )
        self.reset_func(
            None, "removeAccessibleSelectionFromContext", c_long, AccessibleSelection,c_int
        )
        self.reset_func(
            None, "selectAllAccessibleSelectionFromContext", c_long, AccessibleSelection
        )

        # Additional for Teton
        self.reset_func(
            BOOL, "getVirtualAccessibleName", c_long, AccessibleContext, POINTER(c_wchar), c_int, error_check=True
        )
        self.reset_func(
            BOOL, "requestFocus", c_long, AccessibleContext, error_check=True
        )
        self.reset_func(
            BOOL, "selectTextRange", c_long, AccessibleContext, c_int, c_int, check_error=True
        )
        self.reset_func(
            BOOL,
            "getTextAttributesInRange",
            c_long,
            AccessibleContext,
            c_int,
            c_int,
            POINTER(AccessibleTextAttributesInfo),
            POINTER(c_short),
            check_error=True,
        )
        self.reset_func(
            c_int,
            "getVisibleChildrenCount",
            c_long,
            AccessibleContext,
            check_error=True,
        )
        self.reset_func(
            BOOL,
            "getVisibleChildren",
            c_long,
            AccessibleContext,
            c_int,
            POINTER(VisibleChildrenInfo),
            check_error=True,
        )
        self.reset_func(
            BOOL, "setCaretPosition", c_long, AccessibleContext, c_int, check_error=True
        )
        self.reset_func(
            BOOL,
            "getCaretLocation",
            c_long,
            AccessibleContext,
            POINTER(AccessibleTextRectInfo),
            jint,
            check_error=True,
        )
        self.reset_func(c_int, "getEventsWaiting", check_error=True)        
        
