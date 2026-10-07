"""The C structures Java Access Bridge fills in when pyjab asks it a question.

Most JAB calls work by being handed a pointer to one of these, filling in what it
knows, and returning a flag.  ctypes needs the layout to match the DLL's byte for
byte: a field out of order, the wrong width, or a missing padding-sensitive
member means the call writes past the end of the buffer, or pyjab reads one
field's bytes as another's.

The layouts are therefore not a design decision.  They are the ABI declared in
the JDK's ``AccessBridgeCalls.h`` and the headers it includes, and every field
name, type and position below comes from there.  Sizes and offsets are asserted
against the frozen baseline in ``tests/test_accessibleinfo_abi.py``, so an
accidental edit is caught rather than shipped.

The ``MAX_*`` sizes live in :mod:`pyjab.config` because they are also what
decides how large a string can be before JAB truncates it.
"""

from ctypes import Structure
from ctypes import c_bool
from ctypes import c_float
from ctypes import c_int
from ctypes import c_wchar
from ctypes.wintypes import BOOL
from ctypes.wintypes import WCHAR

from pyjab.common.types import JOBJECT64
from pyjab.config import MAX_ACTION_INFO
from pyjab.config import MAX_ACTIONS_TO_DO
from pyjab.config import MAX_KEY_BINDINGS
from pyjab.config import MAX_RELATIONS
from pyjab.config import MAX_RELATION_TARGETS
from pyjab.config import MAX_STRING_SIZE
from pyjab.config import MAX_VISIBLE_CHILDREN
from pyjab.config import SHORT_STRING_SIZE


class AccessBridgeVersionInfo(Structure):
    """The four version strings ``getVersionInfo`` reports.

    Useful for confirming which JDK's bridge was loaded, and for telling a
    JAB 2.0.1 DLL from a 2.0.2 one.
    """

    _fields_ = (
        ("VMVersion", WCHAR * SHORT_STRING_SIZE),
        ("bridgeJavaClassVersion", WCHAR * SHORT_STRING_SIZE),
        ("bridgeJavaDLLVersion", WCHAR * SHORT_STRING_SIZE),
        ("bridgeWinDLLVersion", WCHAR * SHORT_STRING_SIZE),
    )


class AccessibleContextInfo(Structure):
    """Everything JAB knows about one element, from ``getAccessibleContextInfo``.

    The largest structure pyjab uses and the one behind almost every property:
    name, role, states, position and which capabilities the element has.  Note
    that ``role`` and ``states`` are the localised strings and ``role_en_US`` /
    ``states_en_US`` the English ones -- pyjab reads the English pair so that
    matching does not depend on the language of the machine.

    The five ``accessible*`` flags are BOOLs, not Python bools: each is a plain
    C int, so the structure is wider than a packed set of flags would be.
    """

    _fields_ = (
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
        ("accessibleValue", BOOL),
    )


class AccessibleTextInfo(Structure):
    """Character and caret positions, from ``getAccessibleTextInfo``."""

    _fields_ = (
        ("charCount", c_int),
        ("caretIndex", c_int),
        ("indexAtPoint", c_int),
    )


class AccessibleTextItemsInfo(Structure):
    """The letter, word and sentence at an index, from ``getAccessibleTextItems``.

    Three strings of increasing size in one structure, which is why it is one of
    the larger ones even though it reports very little.
    """

    _fields_ = (
        ("letter", WCHAR),
        ("word", WCHAR * SHORT_STRING_SIZE),
        ("sentence", WCHAR * MAX_STRING_SIZE),
    )


class AccessibleTextSelectionInfo(Structure):
    """The selected range and its text, from ``getAccessibleTextSelectionInfo``."""

    _fields_ = (
        ("selectionStartIndex", c_int),
        ("selectionEndIndex", c_int),
        ("selectedText", WCHAR * MAX_STRING_SIZE),
    )


class AccessibleTextRectInfo(Structure):
    """A rectangle in the text, from ``getAccessibleTextRect``."""

    _fields_ = (
        ("x", c_int),
        ("y", c_int),
        ("width", c_int),
        ("height", c_int),
    )


class AccessibleTextAttributesInfo(Structure):
    """Character and paragraph attributes, from ``getAccessibleTextAttributes``.

    The layout groups the six boolean style flags first, then three colour and
    font strings, then the numeric metrics -- the flags are BOOLs rather than
    single bytes, so they occupy six ints before the strings begin.

    ``LeftIndent`` is capitalised in the header while ``rightIndent`` beside it
    is not.  That inconsistency is the header's, and renaming either would break
    attribute access for anyone reading these fields directly.
    """

    _fields_ = (
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
    )


class AccessibleRelationInfo(Structure):
    """One relation and its targets.  Filled in inside a set, never directly."""

    _fields_ = (
        ("key", WCHAR * SHORT_STRING_SIZE),
        ("targetCount", c_int),
        ("targets", JOBJECT64 * MAX_RELATION_TARGETS),
    )


class AccessibleRelationSetInfo(Structure):
    """Every relation an element has, from ``getAccessibleRelationSet``.

    An array of :class:`AccessibleRelationInfo` by value, so the whole set
    arrives in one buffer sized for the worst case.
    """

    _fields_ = (
        ("relationCount", c_int),
        ("relations", AccessibleRelationInfo * MAX_RELATIONS),
    )


class AccessibleActionInfo(Structure):
    """The name of one accessibility action, such as "click" or "toggleexpand"."""

    _fields_ = (
        ("name", c_wchar * SHORT_STRING_SIZE),
    )


class AccessibleActions(Structure):
    """The actions an element offers, from ``getAccessibleActions``."""

    _fields_ = (
        ("actionsCount", c_int),
        ("actionInfo", AccessibleActionInfo * MAX_ACTION_INFO),
    )


class AccessibleActionsToDo(Structure):
    """The actions to perform, passed *into* ``doAccessibleActions``.

    The mirror image of :class:`AccessibleActions`, with its own smaller limit --
    this one is the caller's request rather than the element's inventory.
    """

    _fields_ = (
        ("actionsCount", c_int),
        ("actions", AccessibleActionInfo * MAX_ACTIONS_TO_DO),
    )


class AccessibleTableInfo(Structure):
    """A table and its dimensions, from ``getAccessibleTableInfo``.

    ``caption`` and ``summary`` are object handles rather than strings, and the
    two trailing handles are the table's own context and its ``AccessibleTable``
    -- the latter being what every cell and selection call wants as its second
    argument.
    """

    _fields_ = (
        ("caption", JOBJECT64),
        ("summary", JOBJECT64),
        ("rowCount", c_int),
        ("columnCount", c_int),
        ("accessibleContext", JOBJECT64),
        ("accessibleTable", JOBJECT64),
    )


class AccessibleTableCellInfo(Structure):
    """One cell's position and extent, from ``getAccessibleTableCellInfo``.

    ``isSelected`` is a real ``c_bool`` here, one byte, unlike the BOOL flags in
    :class:`AccessibleContextInfo` -- the header differs between the two.
    """

    _fields_ = (
        ("accessibleContext", JOBJECT64),
        ("index", c_int),
        ("row", c_int),
        ("column", c_int),
        ("rowExtent", c_int),
        ("columnExtent", c_int),
        ("isSelected", c_bool),
    )


class AccessibleKeyBindingInfo(Structure):
    """One keystroke: a character plus its modifier mask."""

    _fields_ = (
        ("character", c_wchar),
        ("modifiers", c_int),
    )


class AccessibleKeyBindings(Structure):
    """An element's keyboard shortcuts, from ``getAccessibleKeyBindings``."""

    _fields_ = (
        ("keyBindingsCount", c_int),
        ("keyBindingInfo", AccessibleKeyBindingInfo * MAX_KEY_BINDINGS),
    )


class VisibleChildrenInfo(Structure):
    """The children currently on screen, from ``getVisibleChildren``.

    An array of handles by value, sized for the worst case, which is why a
    structure reporting a single count is nevertheless kilobytes wide.
    """

    _fields_ = (
        ("returnedChildrenCount", c_int),
        ("children", JOBJECT64 * MAX_VISIBLE_CHILDREN),
    )
