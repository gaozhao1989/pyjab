from ctypes import Structure
from ctypes import c_float
from ctypes import c_int
from ctypes import c_wchar
from ctypes import c_bool
from ctypes.wintypes import BOOL
from ctypes.wintypes import WCHAR
from pyjab.config import (
    MAX_ACTIONS_TO_DO,
    MAX_ACTION_INFO,
    MAX_HYPERLINKS,
    MAX_ICON_INFO,
    MAX_KEY_BINDINGS,
    MAX_RELATIONS,
    MAX_RELATION_TARGETS,
    MAX_STRING_SIZE,
    MAX_VISIBLE_CHILDREN,
    SHORT_STRING_SIZE,
)
from pyjab.common.types import JOBJECT64


class AccessBridgeVersionInfo(Structure):
    _fields_ = [
        ("VMVersion", WCHAR * SHORT_STRING_SIZE),
        ("bridgeJavaClassVersion", WCHAR * SHORT_STRING_SIZE),
        ("bridgeJavaDLLVersion", WCHAR * SHORT_STRING_SIZE),
        ("bridgeWinDLLVersion", WCHAR * SHORT_STRING_SIZE),
    ]


class AccessibleContextInfo(Structure):
    _fields_ = [
        ("name", WCHAR * MAX_STRING_SIZE),
        ("description", WCHAR * MAX_STRING_SIZE),
        ("role", WCHAR * SHORT_STRING_SIZE),
        ("role_en_US", WCHAR * SHORT_STRING_SIZE),
        ("states", WCHAR * SHORT_STRING_SIZE),
        ("states_en_US", WCHAR * SHORT_STRING_SIZE),
        ("indexInParent", c_int),
        ("childrenCount", c_int),
        ("x", c_int),
        ("y", c_int),
        ("width", c_int),
        ("height", c_int),
        ("accessibleComponent", BOOL),
        ("accessibleAction", BOOL),
        ("accessibleSelection", BOOL),
        ("accessibleText", BOOL),
        ("accessibleInterfaces", BOOL),
    ]


class AccessibleTextInfo(Structure):
    _fields_ = [
        ("charCount", c_int),
        ("caretIndex", c_int),
        ("indexAtPoint", c_int),
    ]


class AccessibleTextItemsInfo(Structure):
    _fields_ = [
        ("letter", WCHAR),
        ("word", WCHAR * SHORT_STRING_SIZE),
        ("sentence", WCHAR * MAX_STRING_SIZE),
    ]


class AccessibleTextSelectionInfo(Structure):
    _fields_ = [
        ("selectionStartIndex", c_int),
        ("selectionEndIndex", c_int),
        ("selectedText", WCHAR * MAX_STRING_SIZE),
    ]


class AccessibleTextRectInfo(Structure):
    _fields_ = [
        ("x", c_int),
        ("y", c_int),
        ("width", c_int),
        ("height", c_int),
    ]


class AccessibleTextAttributesInfo(Structure):
    _fields_ = [
        ("bold", BOOL),
        ("italic", BOOL),
        ("underline", BOOL),
        ("strikethrough", BOOL),
        ("superscript", BOOL),
        ("subscript", BOOL),
        ("backgroundColor", WCHAR * SHORT_STRING_SIZE),
        ("foregroundColor", WCHAR * SHORT_STRING_SIZE),
        ("fontFamily", WCHAR * SHORT_STRING_SIZE),
        ("fontSize", c_int),
        ("alignment", c_int),
        ("bidiLevel", c_int),
        ("firstLineIndent", c_float),
        ("LeftIndent", c_float),
        ("rightIndent", c_float),
        ("lineSpacing", c_float),
        ("spaceAbove", c_float),
        ("spaceBelow", c_float),
        ("fullAttributesString", WCHAR * MAX_STRING_SIZE),
    ]


class AccessibleTableInfo(Structure):
    _fields_ = [
        ("caption", JOBJECT64),
        ("summary", JOBJECT64),
        ("rowCount", c_int),
        ("columnCount", c_int),
        ("accessibleContext", JOBJECT64),
        ("accessibleTable", JOBJECT64),
    ]


class AccessibleTableCellInfo(Structure):
    _fields_ = [
        ("accessibleContext", JOBJECT64),
        ("index", c_int),
        ("row", c_int),
        ("column", c_int),
        ("rowExtent", c_int),
        ("columnExtent", c_int),
        ("isSelected", c_bool),
    ]


class AccessibleRelationInfo(Structure):
    _fields_ = [
        ("key", WCHAR * SHORT_STRING_SIZE),
        ("targetCount", c_int),
        ("targets", JOBJECT64 * MAX_RELATION_TARGETS),
    ]


class AccessibleRelationSetInfo(Structure):
    _fields_ = [
        ("relationCount", c_int),
        ("relations", AccessibleRelationInfo * MAX_RELATIONS),
    ]


class AccessibleHyperlinkInfo(Structure):
    _fields_ = [
        ("text", WCHAR * SHORT_STRING_SIZE),
        ("startIndex", c_int),
        ("endIndex", c_int),
        ("accessibleHyperlink", JOBJECT64),
    ]


class AccessibleHypertextInfo(Structure):
    _fields_ = [
        ("linkCount", c_int),
        ("links", AccessibleHyperlinkInfo * MAX_HYPERLINKS),
        ("accessibleHypertext", JOBJECT64),
    ]


class AccessibleKeyBindingInfo(Structure):
    _fields_ = [
        ("character", c_wchar),
        ("modifiers", c_int),
    ]


class AccessibleKeyBindings(Structure):
    _fields_ = [
        ("keyBindingsCount", c_int),
        ("keyBindingInfo", AccessibleKeyBindingInfo * MAX_KEY_BINDINGS),
    ]


class AccessibleIconInfo(Structure):
    _fields_ = [
        ("description", WCHAR * SHORT_STRING_SIZE),
        ("height", c_int),
        ("width", c_int),
    ]


class AccessibleIcons(Structure):
    _fields_ = [("iconsCount", c_int), ("iconInfo", AccessibleIconInfo * MAX_ICON_INFO)]


class AccessibleActionInfo(Structure):
    _fields_ = [
        ("name", WCHAR * SHORT_STRING_SIZE),
    ]


class AccessibleActions(Structure):
    _fields_ = [
        ("actionsCount", c_int),
        ("actionInfo", AccessibleActionInfo * MAX_ACTION_INFO),
    ]


class AccessibleActionsToDo(Structure):
    _fields_ = [
        ("actionsCount", c_int),
        ("actions", AccessibleActionInfo * MAX_ACTIONS_TO_DO),
    ]


class VisibleChildenInfo(Structure):
    _fields_ = [
        ("returnedChildrenCount", c_int),
        ("children", AccessibleContextInfo * MAX_VISIBLE_CHILDREN),
    ]
