"""The JAB structures must keep the byte layout the DLL writes.

Every field in ``pyjab/accessibleinfo.py`` is a position in a buffer that the
bridge DLL fills in.  Get one wrong and the call writes past the end of the
allocation, or pyjab reads one field's bytes as another's -- neither of which
raises anything.

The numbers below are therefore frozen, not derived: they were captured from the
structures as they stood before the file was rewritten for provenance reasons, so
that the rewrite could be shown to have changed only comments and formatting.
Sizes are the important part; the per-field offsets are what make a size
mismatch diagnosable.
"""

from __future__ import annotations

import ctypes

import pytest

from pyjab import accessibleinfo


#: name -> (size in bytes, alignment, ((field, offset), ...))
EXPECTED_LAYOUT = {
    "AccessBridgeVersionInfo": (4096, 4, (
        ("VMVersion", "c_wchar[256]", 0), ("bridgeJavaClassVersion",
        "c_wchar[256]", 1024), ("bridgeJavaDLLVersion", "c_wchar[256]",
        2048), ("bridgeWinDLLVersion", "c_wchar[256]", 3072)
    )),
    "AccessibleActionInfo": (1024, 4, (
        ("name", "c_wchar[256]", 0),
    )),
    "AccessibleActions": (262148, 4, (
        ("actionsCount", "c_int", 0), ("actionInfo",
        "AccessibleActionInfo[256]", 4)
    )),
    "AccessibleActionsToDo": (32772, 4, (
        ("actionsCount", "c_int", 0), ("actions",
        "AccessibleActionInfo[32]", 4)
    )),
    "AccessibleContextInfo": (12352, 8, (
        ("name", "c_wchar[1024]", 0), ("description", "c_wchar[1024]",
        4096), ("role", "c_wchar[256]", 8192), ("role_en_US",
        "c_wchar[256]", 9216), ("states", "c_wchar[256]", 10240),
        ("states_en_US", "c_wchar[256]", 11264), ("indexInParent",
        "c_int", 12288), ("childrenCount", "c_int", 12292), ("x",
        "c_int", 12296), ("y", "c_int", 12300), ("width", "c_int",
        12304), ("height", "c_int", 12308), ("accessibleComponent",
        "c_long", 12312), ("accessibleAction", "c_long", 12320),
        ("accessibleSelection", "c_long", 12328), ("accessibleText",
        "c_long", 12336), ("accessibleValue", "c_long", 12344)
    )),
    "AccessibleKeyBindingInfo": (8, 4, (
        ("character", "c_wchar", 0), ("modifiers", "c_int", 4)
    )),
    "AccessibleKeyBindings": (404, 4, (
        ("keyBindingsCount", "c_int", 0), ("keyBindingInfo",
        "AccessibleKeyBindingInfo[50]", 4)
    )),
    "AccessibleRelationInfo": (1232, 8, (
        ("key", "c_wchar[256]", 0), ("targetCount", "c_int", 1024),
        ("targets", "JOBJECT64[25]", 1032)
    )),
    "AccessibleRelationSetInfo": (6168, 8, (
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
    "AccessibleTextAttributesInfo": (7256, 8, (
        ("bold", "c_long", 0), ("italic", "c_long", 8), ("underline",
        "c_long", 16), ("strikethrough", "c_long", 24), ("superscript",
        "c_long", 32), ("subscript", "c_long", 40), ("backgroundColor",
        "c_wchar[256]", 48), ("foregroundColor", "c_wchar[256]", 1072),
        ("fontFamily", "c_wchar[256]", 2096), ("fontSize", "c_int",
        3120), ("alignment", "c_int", 3124), ("bidiLevel", "c_int",
        3128), ("firstLineIndent", "c_float", 3132), ("LeftIndent",
        "c_float", 3136), ("rightIndent", "c_float", 3140),
        ("lineSpacing", "c_float", 3144), ("spaceAbove", "c_float",
        3148), ("spaceBelow", "c_float", 3152), ("fullAttributesString",
        "c_wchar[1024]", 3156)
    )),
    "AccessibleTextInfo": (12, 4, (
        ("charCount", "c_int", 0), ("caretIndex", "c_int", 4),
        ("indexAtPoint", "c_int", 8)
    )),
    "AccessibleTextItemsInfo": (5124, 4, (
        ("letter", "c_wchar", 0), ("word", "c_wchar[256]", 4),
        ("sentence", "c_wchar[1024]", 1028)
    )),
    "AccessibleTextRectInfo": (16, 4, (
        ("x", "c_int", 0), ("y", "c_int", 4), ("width", "c_int", 8),
        ("height", "c_int", 12)
    )),
    "AccessibleTextSelectionInfo": (4104, 4, (
        ("selectionStartIndex", "c_int", 0), ("selectionEndIndex",
        "c_int", 4), ("selectedText", "c_wchar[1024]", 8)
    )),
    "VisibleChildrenInfo": (2056, 8, (
        ("returnedChildrenCount", "c_int", 0), ("children",
        "JOBJECT64[256]", 8)
    )),
}


def describe_type(ctype) -> str:
    """A stable name for a ctypes type, arrays included.

    ``c_int * 1024`` has no ``__name__`` worth printing, so arrays are described
    by their element type and length, and everything else by its name.
    """
    if isinstance(ctype, type) and issubclass(ctype, ctypes.Array):
        return "{}[{}]".format(describe_type(ctype._type_), ctype._length_)
    return getattr(ctype, "__name__", str(ctype))


def structures():
    """Every Structure this module defines, by name."""
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


@pytest.mark.parametrize("name", sorted(EXPECTED_LAYOUT))
def test_size_is_unchanged(name):
    size, _, _ = EXPECTED_LAYOUT[name]

    assert ctypes.sizeof(structures()[name]) == size


@pytest.mark.parametrize("name", sorted(EXPECTED_LAYOUT))
def test_alignment_is_unchanged(name):
    _, alignment, _ = EXPECTED_LAYOUT[name]

    assert ctypes.alignment(structures()[name]) == alignment


@pytest.mark.parametrize("name", sorted(EXPECTED_LAYOUT))
def test_field_types_and_offsets_are_unchanged(name):
    """Types matter as much as offsets, and offsets alone do not catch them.

    Changing a field from ``c_int`` to ``c_short`` can leave the structure the
    same size and every offset where it was -- tail padding absorbs it -- so a
    wrong type would look correct and then truncate the value it read.  The
    declared type is compared for that reason.

    Read through ``_fields_`` rather than through the class attributes: the
    attributes are ``ctypes`` descriptors whose internals are not a documented
    interface, and ``_fields_`` is the declaration itself.
    """
    _, _, fields = EXPECTED_LAYOUT[name]
    structure = structures()[name]

    actual = tuple(
        (field_name, describe_type(field_type), getattr(structure, field_name).offset)
        for field_name, field_type in structure._fields_
    )

    assert actual == tuple((f, t, o) for f, t, o in fields)


@pytest.mark.parametrize("name", sorted(EXPECTED_LAYOUT))
def test_field_order_is_unchanged(name):
    """Offsets could match while the declared order differed, which ctypes allows."""
    _, _, fields = EXPECTED_LAYOUT[name]

    assert [f[0] for f in structures()[name]._fields_] == [f for f, _, _ in fields]
