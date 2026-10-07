"""The JAB structures must keep the byte layout the bridge DLL writes.

Every field in ``pyjab/accessibleinfo.py`` is a position in a buffer that the
Windows bridge DLL fills in. Get one wrong and the call writes past the end of
the allocation, or pyjab reads one field's bytes as another's -- neither of which
raises anything.

The layout that matters is the **Windows** one, and two ctypes types are a
different width there than on the POSIX platforms ctypes emulates: ``WCHAR`` is
two bytes on Windows and four elsewhere, ``BOOL`` is a four-byte ``long`` rather
than an eight-byte one.  Asserting sizes measured on macOS would therefore assert
numbers that never apply where the DLL runs, which is how the first version of
this test failed on Windows -- 31 assertions, all correct about the wrong
platform.

So the expected layout below is the Windows one, and the structure under test is
translated into it before being measured (:func:`windows_layout`).  That
translation is not taken on trust: it reproduces the sizes Windows reported for
this file in CI, all ten that differ from the POSIX ones, exactly.

The declared layout is checked too, and on every platform.  A field renamed,
reordered, narrowed or shortened changes the declaration, and that check catches
it wherever it runs.
"""

from __future__ import annotations

import ctypes
from ctypes.wintypes import BOOL
from ctypes.wintypes import WCHAR

import pytest

from pyjab import accessibleinfo


#: The two types whose width differs between Windows and the POSIX platforms
#: ctypes emulates.  ``WCHAR`` is ``c_wchar`` -- two bytes on Windows, four
#: elsewhere; ``BOOL`` is ``c_long`` -- four bytes on Windows, eight elsewhere.
WINDOWS_WIDTHS = {
    WCHAR: ctypes.c_uint16,
    BOOL: ctypes.c_int32,
}

#: name -> (size, alignment, ((field, declared type, offset), ...)) as Windows
#: lays it out.
EXPECTED_LAYOUT = {
    "AccessBridgeVersionInfo": (2048, 2, (
        ("VMVersion", "c_wchar[256]", 0), ("bridgeJavaClassVersion",
        "c_wchar[256]", 512), ("bridgeJavaDLLVersion", "c_wchar[256]",
        1024), ("bridgeWinDLLVersion", "c_wchar[256]", 1536)
    )),
    "AccessibleActionInfo": (512, 2, (
        ("name", "c_wchar[256]", 0),
    )),
    "AccessibleActions": (131076, 4, (
        ("actionsCount", "c_int", 0), ("actionInfo",
        "AccessibleActionInfo[256]", 4)
    )),
    "AccessibleActionsToDo": (16388, 4, (
        ("actionsCount", "c_int", 0), ("actions",
        "AccessibleActionInfo[32]", 4)
    )),
    "AccessibleContextInfo": (6188, 4, (
        ("name", "c_wchar[1024]", 0), ("description", "c_wchar[1024]",
        2048), ("role", "c_wchar[256]", 4096), ("role_en_US",
        "c_wchar[256]", 4608), ("states", "c_wchar[256]", 5120),
        ("states_en_US", "c_wchar[256]", 5632), ("indexInParent",
        "c_int", 6144), ("childrenCount", "c_int", 6148), ("x",
        "c_int", 6152), ("y", "c_int", 6156), ("width", "c_int",
        6160), ("height", "c_int", 6164), ("accessibleComponent",
        "c_long", 6168), ("accessibleAction", "c_long", 6172),
        ("accessibleSelection", "c_long", 6176), ("accessibleText",
        "c_long", 6180), ("accessibleValue", "c_long", 6184)
    )),
    "AccessibleKeyBindingInfo": (8, 4, (
        ("character", "c_wchar", 0), ("modifiers", "c_int", 4)
    )),
    "AccessibleKeyBindings": (404, 4, (
        ("keyBindingsCount", "c_int", 0), ("keyBindingInfo",
        "AccessibleKeyBindingInfo[50]", 4)
    )),
    "AccessibleRelationInfo": (720, 8, (
        ("key", "c_wchar[256]", 0), ("targetCount", "c_int", 512),
        ("targets", "JOBJECT64[25]", 520)
    )),
    "AccessibleRelationSetInfo": (3608, 8, (
        ("relationCount", "c_int", 0), ("relations",
        "AccessibleRelationInfo[5]", 8)
    )),
    "AccessibleTableCellInfo": (32, 8, (
        ("accessibleContext", "JOBJECT64", 0), ("index", "c_int", 8),
        ("row", "c_int", 12), ("column", "c_int", 16), ("rowExtent",
        "c_int", 20), ("columnExtent", "c_int", 24), ("isSelected",
        "c_bool", 28)
    )),
    "AccessibleTableInfo": (40, 8, (
        ("caption", "JOBJECT64", 0), ("summary", "JOBJECT64", 8),
        ("rowCount", "c_int", 16), ("columnCount", "c_int", 20),
        ("accessibleContext", "JOBJECT64", 24), ("accessibleTable",
        "JOBJECT64", 32)
    )),
    "AccessibleTextAttributesInfo": (3644, 4, (
        ("bold", "c_long", 0), ("italic", "c_long", 4), ("underline",
        "c_long", 8), ("strikethrough", "c_long", 12), ("superscript",
        "c_long", 16), ("subscript", "c_long", 20),
        ("backgroundColor", "c_wchar[256]", 24), ("foregroundColor",
        "c_wchar[256]", 536), ("fontFamily", "c_wchar[256]", 1048),
        ("fontSize", "c_int", 1560), ("alignment", "c_int", 1564),
        ("bidiLevel", "c_int", 1568), ("firstLineIndent", "c_float",
        1572), ("LeftIndent", "c_float", 1576), ("rightIndent",
        "c_float", 1580), ("lineSpacing", "c_float", 1584),
        ("spaceAbove", "c_float", 1588), ("spaceBelow", "c_float",
        1592), ("fullAttributesString", "c_wchar[1024]", 1596)
    )),
    "AccessibleTextInfo": (12, 4, (
        ("charCount", "c_int", 0), ("caretIndex", "c_int", 4),
        ("indexAtPoint", "c_int", 8)
    )),
    "AccessibleTextItemsInfo": (2562, 2, (
        ("letter", "c_wchar", 0), ("word", "c_wchar[256]", 2),
        ("sentence", "c_wchar[1024]", 514)
    )),
    "AccessibleTextRectInfo": (16, 4, (
        ("x", "c_int", 0), ("y", "c_int", 4), ("width", "c_int", 8),
        ("height", "c_int", 12)
    )),
    "AccessibleTextSelectionInfo": (2056, 4, (
        ("selectionStartIndex", "c_int", 0), ("selectionEndIndex",
        "c_int", 4), ("selectedText", "c_wchar[1024]", 8)
    )),
    "VisibleChildrenInfo": (2056, 8, (
        ("returnedChildrenCount", "c_int", 0), ("children",
        "JOBJECT64[256]", 8)
    )),
}


def _translate(ctype):
    """The same type as Windows would size it."""
    if ctype in WINDOWS_WIDTHS:
        return WINDOWS_WIDTHS[ctype]
    if isinstance(ctype, type) and issubclass(ctype, ctypes.Array):
        return _translate(ctype._type_) * ctype._length_
    if isinstance(ctype, type) and issubclass(ctype, ctypes.Structure):
        return windows_layout(ctype)
    return ctype


_translated: dict = {}


def windows_layout(structure):
    """``structure`` re-declared with Windows widths, so it can be measured here."""
    name = structure.__name__
    if name in _translated:
        return _translated[name]
    _translated[name] = None  # a self-referential structure would recurse forever
    fields = [(field, _translate(ctype)) for field, ctype in structure._fields_]
    _translated[name] = type("Win" + name, (ctypes.Structure,), {"_fields_": fields})
    return _translated[name]


def describe_type(ctype) -> str:
    """A stable name for a declared ctypes type, arrays included."""
    if isinstance(ctype, type) and issubclass(ctype, ctypes.Array):
        return "{}[{}]".format(describe_type(ctype._type_), ctype._length_)
    return getattr(ctype, "__name__", str(ctype))


def structures():
    """Every Structure the module defines, by name."""
    found = {}
    for name in dir(accessibleinfo):
        obj = getattr(accessibleinfo, name)
        if (isinstance(obj, type) and issubclass(obj, ctypes.Structure)
                and obj is not ctypes.Structure):
            found[name] = obj
    return found


def test_the_expected_layout_covers_every_structure():
    """A new structure must be added here, with its layout, or it goes unchecked."""
    assert set(structures()) == set(EXPECTED_LAYOUT)


def test_the_windows_translation_matches_what_windows_reported():
    """The sizes the first version of this test got wrong, when run on Windows.

    These ten are the structures whose size differs from the POSIX one, as
    reported by the Windows CI job.  Pinning them here means the translation
    above cannot quietly drift into describing a layout Windows does not use.
    """
    reported = {
        "AccessBridgeVersionInfo": 2048,
        "AccessibleActionInfo": 512,
        "AccessibleActions": 131076,
        "AccessibleActionsToDo": 16388,
        "AccessibleContextInfo": 6188,
        "AccessibleRelationInfo": 720,
        "AccessibleRelationSetInfo": 3608,
        "AccessibleTextAttributesInfo": 3644,
        "AccessibleTextItemsInfo": 2562,
        "AccessibleTextSelectionInfo": 2056,
    }

    for name, size in reported.items():
        assert ctypes.sizeof(windows_layout(structures()[name])) == size, name


@pytest.mark.parametrize("name", sorted(EXPECTED_LAYOUT))
def test_the_declared_layout_is_unchanged(name):
    """Field names, declared types and order -- the same on every platform.

    This is the check that catches an edit, and it is why the byte-level numbers
    below are the smaller half of the story: narrowing a field or reordering two
    of them shows up here even where the resulting size happens to be unchanged.
    """
    _, _, fields = EXPECTED_LAYOUT[name]
    structure = structures()[name]

    declared = [(field, describe_type(ctype)) for field, ctype in structure._fields_]

    assert declared == [(f, t) for f, t, _ in fields]


@pytest.mark.parametrize("name", sorted(EXPECTED_LAYOUT))
def test_the_windows_byte_layout_is_unchanged(name):
    """Size, alignment and every offset, as Windows lays the structure out."""
    size, alignment, fields = EXPECTED_LAYOUT[name]
    structure = windows_layout(structures()[name])

    assert ctypes.sizeof(structure) == size
    assert ctypes.alignment(structure) == alignment
    assert [(f, getattr(structure, f).offset) for f, _, _ in fields] == [
        (f, o) for f, _, o in fields
    ]
