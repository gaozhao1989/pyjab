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
        ("VMVersion", "uint16[256]", 0), ("bridgeJavaClassVersion",
        "uint16[256]", 512), ("bridgeJavaDLLVersion", "uint16[256]",
        1024), ("bridgeWinDLLVersion", "uint16[256]", 1536)
    )),
    "AccessibleActionInfo": (512, 2, (
        ("name", "uint16[256]", 0),
    )),
    "AccessibleActions": (131076, 4, (
        ("actionsCount", "int32", 0), ("actionInfo",
        "WinAccessibleActionInfo[256]", 4)
    )),
    "AccessibleActionsToDo": (16388, 4, (
        ("actionsCount", "int32", 0), ("actions",
        "WinAccessibleActionInfo[32]", 4)
    )),
    "AccessibleContextInfo": (6188, 4, (
        ("name", "uint16[1024]", 0), ("description", "uint16[1024]",
        2048), ("role", "uint16[256]", 4096), ("role_en_US",
        "uint16[256]", 4608), ("states", "uint16[256]", 5120),
        ("states_en_US", "uint16[256]", 5632), ("indexInParent",
        "int32", 6144), ("childrenCount", "int32", 6148), ("x",
        "int32", 6152), ("y", "int32", 6156), ("width", "int32",
        6160), ("height", "int32", 6164), ("accessibleComponent",
        "int32", 6168), ("accessibleAction", "int32", 6172),
        ("accessibleSelection", "int32", 6176), ("accessibleText",
        "int32", 6180), ("accessibleValue", "int32", 6184)
    )),
    "AccessibleKeyBindingInfo": (8, 4, (
        ("character", "uint16", 0), ("modifiers", "int32", 4)
    )),
    "AccessibleKeyBindings": (404, 4, (
        ("keyBindingsCount", "int32", 0), ("keyBindingInfo",
        "WinAccessibleKeyBindingInfo[50]", 4)
    )),
    "AccessibleRelationInfo": (720, 8, (
        ("key", "uint16[256]", 0), ("targetCount", "int32", 512),
        ("targets", "int64[25]", 520)
    )),
    "AccessibleRelationSetInfo": (3608, 8, (
        ("relationCount", "int32", 0), ("relations",
        "WinAccessibleRelationInfo[5]", 8)
    )),
    "AccessibleTableCellInfo": (32, 8, (
        ("accessibleContext", "int64", 0), ("index", "int32", 8),
        ("row", "int32", 12), ("column", "int32", 16), ("rowExtent",
        "int32", 20), ("columnExtent", "int32", 24), ("isSelected",
        "bool", 28)
    )),
    "AccessibleTableInfo": (40, 8, (
        ("caption", "int64", 0), ("summary", "int64", 8), ("rowCount",
        "int32", 16), ("columnCount", "int32", 20),
        ("accessibleContext", "int64", 24), ("accessibleTable",
        "int64", 32)
    )),
    "AccessibleTextAttributesInfo": (3644, 4, (
        ("bold", "int32", 0), ("italic", "int32", 4), ("underline",
        "int32", 8), ("strikethrough", "int32", 12), ("superscript",
        "int32", 16), ("subscript", "int32", 20), ("backgroundColor",
        "uint16[256]", 24), ("foregroundColor", "uint16[256]", 536),
        ("fontFamily", "uint16[256]", 1048), ("fontSize", "int32",
        1560), ("alignment", "int32", 1564), ("bidiLevel", "int32",
        1568), ("firstLineIndent", "float32", 1572), ("LeftIndent",
        "float32", 1576), ("rightIndent", "float32", 1580),
        ("lineSpacing", "float32", 1584), ("spaceAbove", "float32",
        1588), ("spaceBelow", "float32", 1592),
        ("fullAttributesString", "uint16[1024]", 1596)
    )),
    "AccessibleTextInfo": (12, 4, (
        ("charCount", "int32", 0), ("caretIndex", "int32", 4),
        ("indexAtPoint", "int32", 8)
    )),
    "AccessibleTextItemsInfo": (2562, 2, (
        ("letter", "uint16", 0), ("word", "uint16[256]", 2),
        ("sentence", "uint16[1024]", 514)
    )),
    "AccessibleTextRectInfo": (16, 4, (
        ("x", "int32", 0), ("y", "int32", 4), ("width", "int32", 8),
        ("height", "int32", 12)
    )),
    "AccessibleTextSelectionInfo": (2056, 4, (
        ("selectionStartIndex", "int32", 0), ("selectionEndIndex",
        "int32", 4), ("selectedText", "uint16[1024]", 8)
    )),
    "VisibleChildrenInfo": (2056, 8, (
        ("returnedChildrenCount", "int32", 0), ("children",
        "int64[256]", 8)
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
    """A description of a ctypes type that means the same on every platform.

    Not ``__name__``.  On Windows ``ctypes.c_int`` and ``ctypes.c_long`` are the
    same four-byte type and share a name, so ``c_int.__name__`` is ``'c_long'``
    there -- which made a recorded 'c_int' compare unequal to the same field on
    Windows, fourteen times over, while both were describing the same thing.

    Width and signedness are what a field actually is, so those are what this
    reports.  Arrays are described by their element type and length, structures by
    their name, and the two ctypes oddities -- ``c_wchar`` and ``c_bool`` -- by
    name, because their width is not what distinguishes them.
    """
    if isinstance(ctype, type) and issubclass(ctype, ctypes.Array):
        return "{}[{}]".format(describe_type(ctype._type_), ctype._length_)
    if isinstance(ctype, type) and issubclass(ctype, ctypes.Structure):
        return ctype.__name__
    if ctype is ctypes.c_bool:
        return "bool"
    if ctype is ctypes.c_wchar:
        return "wchar"
    if ctype is ctypes.c_float:
        return "float32"
    if isinstance(ctype, type) and issubclass(ctype, ctypes._SimpleCData):
        width = ctypes.sizeof(ctype)
        unsigned = ctype(-1).value > 0
        return "{}int{}".format("u" if unsigned else "", width * 8)
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

    declared = [(field, describe_type(ctype))
                for field, ctype in windows_layout(structure)._fields_]

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
