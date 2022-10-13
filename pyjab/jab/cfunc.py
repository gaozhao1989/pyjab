from ctypes import (
    CDLL,
    POINTER,
    _NamedFuncPointer,
    WinError,
    c_int,
    c_long,
    c_short,
    c_void_p,
    c_wchar,
)
from ctypes.wintypes import BOOL, HWND
from pyjab.jab.structure import (
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
from pyjab.jab.type import (
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


class CFunc(object):
    def __init__(self, bridge: CDLL) -> None:
        self.logger = Logger("pyjab")
        self.bridge = bridge

    @staticmethod
    def errcheck(result, func, args):
        if not result:
            raise WinError(
                f"JAB function {func} with arguments {args} in result {result}"
            )
        return result

    def fix_func(self, restype, name, *argtypes, **kwargs):
        try:
            func: _NamedFuncPointer = getattr(self.bridge, name)
        except AttributeError:
            self.logger.error(
                f"JAB function {name} not found in Java Access Bridge DLL"
            )
            return
        func.restype = restype
        func.argtypes = argtypes
        if kwargs.get("errcheck"):
            func.errcheck = self.errcheck

    def fix_funcs(self):
        """Appropriately set the return and argument types of all the access bridge dll functions"""
        self.fix_func(None, "Windows_run")

        # Window routines
        self.fix_func(BOOL, "isJavaWindow", HWND, errcheck=True)
        self.fix_func(
            BOOL,
            "getAccessibleContextFromHWND",
            HWND,
            POINTER(c_long),
            POINTER(AccessibleContext),
            errcheck=True,
        )
        self.fix_func(
            HWND,
            "getHWNDFromAccessibleContext",
            c_long,
            AccessibleContext,
            errcheck=True,
        )

        # Event handling routines
        self.fix_func(None, "setJavaShutdownFP", c_void_p)
        self.fix_func(None, "setFocusGainedFP", c_void_p)
        self.fix_func(None, "setFocusFocusLostFP", c_void_p)
        self.fix_func(None, "setCaretUpdateFP", c_void_p)
        self.fix_func(None, "setMouseClickedFP", c_void_p)
        self.fix_func(None, "setMouseEnteredFP", c_void_p)
        self.fix_func(None, "setMouseExitedFP", c_void_p)
        self.fix_func(None, "setMousePressedFP", c_void_p)
        self.fix_func(None, "setMouseReleasedFP", c_void_p)
        self.fix_func(None, "setMenuCanceledFP", c_void_p)
        self.fix_func(None, "setMenuDeselectedFP", c_void_p)
        self.fix_func(None, "setMenuSelectedFP", c_void_p)
        self.fix_func(None, "setPopupMenuCanceledFP", c_void_p)
        self.fix_func(None, "setPopupMenuWillBecomeInvisibleFP", c_void_p)
        self.fix_func(None, "setPopupMenuWillBecomeVisibleFP", c_void_p)
        self.fix_func(None, "setPropertyNameChangeFP", c_void_p)
        self.fix_func(None, "setPropertyDescriptionChangeFP", c_void_p)
        self.fix_func(None, "setPropertyStateChangeFP", c_void_p)
        self.fix_func(None, "setPropertyValueChangeFP", c_void_p)
        self.fix_func(None, "setPropertySelectionChangeFP", c_void_p)
        self.fix_func(None, "setPropertyTextChangeFP", c_void_p)
        self.fix_func(None, "setPropertyCaretChangeFP", c_void_p)
        self.fix_func(None, "setPropertyVisibleDataChangeFP", c_void_p)
        self.fix_func(None, "setPropertyChildChangeFP", c_void_p)
        self.fix_func(None, "setPropertyActiveDescendentChangeFP", c_void_p)
        self.fix_func(None, "setPropertyTableModelChangeFP", c_void_p)

        # General routines
        self.fix_func(None, "releaseJavaObject", c_long, JOBJECT64)
        self.fix_func(
            BOOL,
            "getVersionInfo",
            c_long,
            POINTER(AccessBridgeVersionInfo),
            errcheck=True,
        )

        # Accessible Context routines
        self.fix_func(
            BOOL,
            "getAccessibleContextAt",
            c_long,
            AccessibleContext,
            jint,
            jint,
            POINTER(AccessibleContext),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleContextWithFocus",
            HWND,
            POINTER(c_long),
            POINTER(AccessibleContext),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleContextInfo",
            c_long,
            AccessibleContext,
            POINTER(AccessibleContextInfo),
            errcheck=True,
        )
        self.fix_func(
            AccessibleContext,
            "getAccessibleChildFromContext",
            c_long,
            AccessibleContext,
            jint,
            errcheck=True,
        )
        self.fix_func(
            AccessibleContext,
            "getAccessibleParentFromContext",
            c_long,
            AccessibleContext,
            errcheck=True,
        )

        # Accessible Text routines
        self.fix_func(
            BOOL,
            "getAccessibleTextInfo",
            c_long,
            AccessibleText,
            POINTER(AccessibleTextInfo),
            jint,
            jint,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTextItems",
            c_long,
            AccessibleText,
            POINTER(AccessibleTextItemsInfo),
            jint,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTextSelectionInfo",
            c_long,
            AccessibleText,
            POINTER(AccessibleTextSelectionInfo),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTextAttributes",
            c_long,
            AccessibleText,
            jint,
            POINTER(AccessibleTextAttributesInfo),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTextRect",
            c_long,
            AccessibleText,
            POINTER(AccessibleTextRectInfo),
            jint,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTextLineBounds",
            c_long,
            AccessibleText,
            jint,
            POINTER(jint),
            POINTER(jint),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTextRange",
            c_long,
            AccessibleText,
            jint,
            jint,
            POINTER(c_wchar),
            c_short,
            errcheck=True,
        )

        # AccessibleTable routines
        self.fix_func(
            BOOL,
            "getAccessibleTableInfo",
            c_long,
            AccessibleContext,
            POINTER(AccessibleTableInfo),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTableCellInfo",
            c_long,
            AccessibleTable,
            jint,
            jint,
            POINTER(AccessibleTableCellInfo),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTableRowHeader",
            c_long,
            AccessibleContext,
            POINTER(AccessibleTableInfo),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTableColumnHeader",
            c_long,
            AccessibleContext,
            POINTER(AccessibleTableInfo),
            errcheck=True,
        )
        self.fix_func(
            AccessibleContext,
            "getAccessibleTableRowDescription",
            c_long,
            AccessibleContext,
            jint,
            errcheck=True,
        )
        self.fix_func(
            AccessibleContext,
            "getAccessibleTableColumnDescription",
            c_long,
            AccessibleContext,
            jint,
            errcheck=True,
        )
        self.fix_func(
            jint,
            "getAccessibleTableRowSelectionCount",
            c_long,
            AccessibleTable,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "isAccessibleTableRowSelected",
            c_long,
            AccessibleTable,
            jint,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTableRowSelections",
            c_long,
            AccessibleTable,
            jint,
            POINTER(jint),
            errcheck=True,
        )
        self.fix_func(
            jint,
            "getAccessibleTableColumnSelectionCount",
            c_long,
            AccessibleTable,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "isAccessibleTableColumnSelected",
            c_long,
            AccessibleTable,
            jint,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleTableColumnSelections",
            c_long,
            AccessibleTable,
            jint,
            POINTER(jint),
            errcheck=True,
        )
        self.fix_func(
            jint,
            "getAccessibleTableRow",
            c_long,
            AccessibleTable,
            jint,
            errcheck=True,
        )
        self.fix_func(
            jint,
            "getAccessibleTableColumn",
            c_long,
            AccessibleTable,
            jint,
            errcheck=True,
        )
        self.fix_func(
            jint,
            "getAccessibleTableIndex",
            c_long,
            AccessibleTable,
            jint,
            jint,
            errcheck=True,
        )

        # AccessibleRelationSet routines
        self.fix_func(
            BOOL,
            "getAccessibleRelationSet",
            c_long,
            AccessibleContext,
            POINTER(AccessibleRelationSetInfo),
            errcheck=True,
        )

        # AccessibleHypertext routines
        self.fix_func(
            BOOL,
            "getAccessibleHypertext",
            c_long,
            AccessibleContext,
            POINTER(AccessibleHypertextInfo),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "activateAccessibleHyperlink",
            c_long,
            AccessibleContext,
            AccessibleHyperlink,
            errcheck=True,
        )
        self.fix_func(
            jint,
            "getAccessibleHyperlinkCount",
            c_long,
            AccessibleHypertext,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleHypertextExt",
            c_long,
            AccessibleContext,
            jint,
            POINTER(AccessibleHypertextInfo),
            errcheck=True,
        )
        self.fix_func(
            jint,
            "getAccessibleHypertextLinkIndex",
            c_long,
            AccessibleHypertext,
            jint,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getAccessibleHyperlink",
            c_long,
            AccessibleHypertext,
            jint,
            POINTER(AccessibleHyperlinkInfo),
            errcheck=True,
        )

        # AccessibleKeyBindings routines
        self.fix_func(
            BOOL,
            "getAccessibleKeyBindings",
            c_long,
            AccessibleContext,
            POINTER(AccessibleKeyBindings),
            errcheck=True,
        )

        # AccessibleIcons
        self.fix_func(
            BOOL,
            "getAccessibleIcons",
            c_long,
            AccessibleContext,
            POINTER(AccessibleIcons),
            errcheck=True,
        )

        # AccessibleActions
        self.fix_func(
            BOOL,
            "getAccessibleActions",
            c_long,
            AccessibleContext,
            POINTER(AccessibleActions),
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "doAccessibleActions",
            c_long,
            AccessibleContext,
            POINTER(AccessibleActionsToDo),
            POINTER(jint),
            errcheck=True,
        )

        # Additional
        self.fix_func(
            BOOL, "isSameObject", c_long, JOBJECT64, JOBJECT64, errcheck=True
        )
        self.fix_func(
            BOOL,
            "setTextContents",
            c_long,
            AccessibleContext,
            POINTER(c_wchar),
            errcheck=True,
        )
        self.fix_func(
            AccessibleContext,
            "getParentWithRole",
            c_long,
            AccessibleContext,
            POINTER(c_wchar),
            errcheck=True,
        )
        self.fix_func(
            AccessibleContext,
            "getParentWithRoleElseRoot",
            c_long,
            AccessibleContext,
            POINTER(c_wchar),
            errcheck=True,
        )
        self.fix_func(
            AccessibleContext,
            "getTopLevelObject",
            c_long,
            AccessibleContext,
            errcheck=True,
        )
        self.fix_func(
            c_int,
            "getObjectDepth",
            c_long,
            AccessibleContext,
            errcheck=True,
        )
        self.fix_func(
            AccessibleContext,
            "getActiveDescendent",
            c_long,
            AccessibleContext,
            errcheck=True,
        )

        # AccessibleValue routines
        self.fix_func(
            BOOL,
            "getCurrentAccessibleValueFromContext",
            c_long,
            AccessibleValue,
            POINTER(c_wchar),
            c_short,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getMaximumAccessibleValueFromContext",
            c_long,
            AccessibleValue,
            POINTER(c_wchar),
            c_short,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getMinimumAccessibleValueFromContext",
            c_long,
            AccessibleValue,
            POINTER(c_wchar),
            c_short,
            errcheck=True,
        )

        # AccessibleSelection routines
        self.fix_func(
            None,
            "addAccessibleSelectionFromContext",
            c_long,
            AccessibleSelection,
            c_int,
        )
        self.fix_func(
            None, "clearAccessibleSelectionFromContext", c_long, AccessibleSelection
        )
        self.fix_func(
            JOBJECT64,
            "getAccessibleSelectionFromContext",
            c_long,
            AccessibleSelection,
            c_int,
            error_check=True,
        )
        self.fix_func(
            c_int,
            "getAccessibleSelectionCountFromContext",
            c_long,
            AccessibleSelection,
            error_check=True,
        )
        self.fix_func(
            BOOL,
            "isAccessibleChildSelectedFromContext",
            c_long,
            AccessibleSelection,
            c_int,
            error_check=True,
        )
        self.fix_func(
            None,
            "removeAccessibleSelectionFromContext",
            c_long,
            AccessibleSelection,
            c_int,
        )
        self.fix_func(
            None, "selectAllAccessibleSelectionFromContext", c_long, AccessibleSelection
        )

        # Additional for Teton
        self.fix_func(
            BOOL,
            "getVirtualAccessibleName",
            c_long,
            AccessibleContext,
            POINTER(c_wchar),
            c_int,
            error_check=True,
        )
        self.fix_func(
            BOOL, "requestFocus", c_long, AccessibleContext, error_check=True
        )
        self.fix_func(
            BOOL,
            "selectTextRange",
            c_long,
            AccessibleContext,
            c_int,
            c_int,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getTextAttributesInRange",
            c_long,
            AccessibleContext,
            c_int,
            c_int,
            POINTER(AccessibleTextAttributesInfo),
            POINTER(c_short),
            errcheck=True,
        )
        self.fix_func(
            c_int,
            "getVisibleChildrenCount",
            c_long,
            AccessibleContext,
            errcheck=True,
        )
        self.fix_func(
            BOOL,
            "getVisibleChildren",
            c_long,
            AccessibleContext,
            c_int,
            POINTER(VisibleChildrenInfo),
            errcheck=True,
        )
        self.fix_func(
            BOOL, "setCaretPosition", c_long, AccessibleContext, c_int, errcheck=True
        )
        self.fix_func(
            BOOL,
            "getCaretLocation",
            c_long,
            AccessibleContext,
            POINTER(AccessibleTextRectInfo),
            jint,
            errcheck=True,
        )
        self.fix_func(c_int, "getEventsWaiting", errcheck=True)
