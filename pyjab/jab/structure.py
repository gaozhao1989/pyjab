"""The Java Access Bridge API Important Data Structures."""
from ctypes import Structure
from ctypes.wintypes import BOOL
from ctypes.wintypes import WCHAR
from pyjab.jab.type import (
    JOBJECT64,
    AccessibleContext,
    jboolean,
    jchar,
    jfloat,
    jint,
)

MAX_STRING_SIZE = 1024
SHORT_STRING_SIZE = 256
MAX_KEY_BINDINGS = 8
MAX_RELATION_TARGETS = 25
MAX_RELATIONS = 5
MAX_ACTION_INFO = 256
MAX_ACTIONS_TO_DO = 32
MAX_VISIBLE_CHILDREN = 256
MAX_HYPERLINKS = 64
MAX_ICON_INFO = 8


class AccessBridgeVersionInfo(Structure):
    _fields_ = [
        ("VMversion", WCHAR * SHORT_STRING_SIZE),
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
        ("indexInParent", jint),
        ("childrenCount", jint),
        ("x", jint),
        ("y", jint),
        ("width", jint),
        ("height", jint),
        ("accessibleComponent", BOOL),
        ("accessibleAction", BOOL),
        ("accessibleSelection", BOOL),
        ("accessibleText", BOOL),
        ("accessibleInterfaces", BOOL),
    ]


class AccessibleTextInfo(Structure):
    _fields_ = [
        ("charCount", jint),
        ("caretIndex", jint),
        ("indexAtPoint", jint),
    ]


class AccessibleTextItemsInfo(Structure):
    _fields_ = [
        ("letter", WCHAR),
        ("word", WCHAR * SHORT_STRING_SIZE),
        ("sentence", WCHAR * MAX_STRING_SIZE),
    ]


class AccessibleTextSelectionInfo(Structure):
    _fields_ = [
        ("selectionStartIndex", jint),
        ("selectionEndIndex", jint),
        ("selectedText", WCHAR * MAX_STRING_SIZE),
    ]


class AccessibleTextRectInfo(Structure):
    _fields_ = [
        ("x", jint),
        ("y", jint),
        ("width", jint),
        ("height", jint),
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
        ("fontSize", jint),
        ("alignment", jint),
        ("bidiLevel", jint),
        ("firstLineIndent", jfloat),
        ("leftIndent", jfloat),
        ("rightIndent", jfloat),
        ("lineSpacing", jfloat),
        ("spaceAbove", jfloat),
        ("spaceBelow", jfloat),
        ("fullAttributesString", WCHAR * MAX_STRING_SIZE),
    ]


class AccessibleTableInfo(Structure):
    _fields_ = [
        ("caption", JOBJECT64),
        ("summary", JOBJECT64),
        ("rowCount", jint),
        ("columnCount", jint),
        ("accessibleContext", JOBJECT64),
        ("accessibleTable", JOBJECT64),
    ]


class AccessibleTableCellInfo(Structure):
    _fields_ = [
        ("accessibleContext", JOBJECT64),
        ("index", jint),
        ("row", jint),
        ("column", jint),
        ("rowExtent", jint),
        ("columnExtent", jint),
        ("isSelected", jboolean),
    ]


class AccessibleRelationInfo(Structure):
    _fields_ = [
        ("key", WCHAR * SHORT_STRING_SIZE),
        ("targetCount", jint),
        ("targets", JOBJECT64 * MAX_RELATION_TARGETS),
    ]


class AccessibleRelationSetInfo(Structure):
    _fields_ = [
        ("relationCount", jint),
        ("relations", AccessibleRelationInfo * MAX_RELATIONS),
    ]


class AccessibleHyperlinkInfo(Structure):
    _fields_ = [
        ("text", WCHAR * SHORT_STRING_SIZE),
        ("startIndex", jint),
        ("endIndex", jint),
        ("accessibleHyperlink", JOBJECT64),
    ]


class AccessibleHypertextInfo(Structure):
    _fields_ = [
        ("linkCount", jint),
        ("links", AccessibleHyperlinkInfo * MAX_HYPERLINKS),
        ("accessibleHypertext", JOBJECT64),
    ]


class AccessibleKeyBindingInfo(Structure):
    _fields_ = [
        ("character", jchar),
        ("modifiers", jint),
    ]


class AccessibleKeyBindings(Structure):
    _fields_ = [
        ("keyBindingsCount", jint),
        ("keyBindingInfo", AccessibleKeyBindingInfo * MAX_KEY_BINDINGS),
    ]


class AccessibleIconInfo(Structure):
    _fields_ = [
        ("description", WCHAR * SHORT_STRING_SIZE),
        ("height", jint),
        ("width", jint),
    ]


class AccessibleIcons(Structure):
    _fields_ = [("iconsCount", jint), ("iconInfo", AccessibleIconInfo * MAX_ICON_INFO)]


class AccessibleActionInfo(Structure):
    _fields_ = (("name", WCHAR * SHORT_STRING_SIZE),)


class AccessibleActions(Structure):
    _fields_ = (
        ("actionsCount", jint),
        ("actionInfo", AccessibleActionInfo * MAX_ACTION_INFO),
    )


class AccessibleActionsToDo(Structure):
    _fields_ = (
        ("actionsCount", jint),
        ("actions", AccessibleActionInfo * MAX_ACTIONS_TO_DO),
    )


class VisibleChildrenInfo(Structure):
    _fields_ = [
        ("returnedChildrenCount", jint),
        ("children", AccessibleContext * MAX_VISIBLE_CHILDREN),
    ]
