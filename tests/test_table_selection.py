"""AccessibleTable selection, against the modelled bridge.

A table is not like a list.  JAB has no call that selects a row or a column, and
none that selects a cell: the table is driven through its own AccessibleSelection,
and the index that call wants is the one ``getAccessibleTableIndex`` maps
``(row, column)`` onto.  These tests cover that path, plus the two ``errorcheck``
traps it walks past, plus the error message #57 was actually complaining about.

Everything here runs anywhere: ``tests/_fakejab.py`` models the bridge, including
the reference counting, so a cell handed out and never released is an error rather
than a leak nobody notices.

What these tests cannot show is whether a real Swing table reports a whole row as
selected once its cells are added.  That is the application's answer, not pyjab's,
and it needs a live table on Windows -- see the note on :meth:`select_row`.
"""

from __future__ import annotations

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import
from pyjab.common.exceptions import JABException
from pyjab.jabfixedfunc import SIGNATURES
from pyjab.common.types import JOBJECT64
from tests._fakejab import bind, column_selecting_table, node, row_selecting_table, table


def a_table(rows=3, columns=4):
    """A bound table element and its bridge."""
    return bind(table(rows, columns, name="results"))


def a_row_selecting_table(rows=3, columns=4):
    """Swing's default JTable: row selection on, column selection off."""
    return bind(row_selecting_table(rows, columns, name="results"))


def a_column_selecting_table(rows=3, columns=4):
    return bind(column_selecting_table(rows, columns, name="results"))


# ---------------------------------------------------------------------------
# Reading a selection that is empty
# ---------------------------------------------------------------------------

def test_a_fresh_table_reports_nothing_selected():
    element, _ = a_table()

    assert element.selected_rows == []
    assert element.selected_columns == []
    assert element.selected_row_count == 0
    assert element.selected_column_count == 0


def test_asking_about_one_row_answers_no_rather_than_raising():
    """The `errorcheck` trap, in the shape that would have hidden the answer.

    ``isAccessibleTableRowSelected`` returns a BOOL, and False means "not
    selected" -- an ordinary answer.  Declared with errorcheck, the hook would
    raise ``RuntimeError: Result 0`` on every unselected row, so the question
    could only ever be answered yes.  Same trap as
    ``getAccessibleContextWithFocus`` in AGENTS.md 2.7.
    """
    element, _ = a_table()

    assert element.is_row_selected(0) is False
    assert element.is_column_selected(0) is False


def test_an_empty_selection_yields_no_elements_rather_than_raising():
    """The other half of that trap.

    ``getAccessibleSelectionCountFromContext`` returns 0 when nothing is
    selected.  With errorcheck it would raise on exactly the case callers ask
    about most: a component they have just opened.
    """
    element, _ = a_table()

    assert element.get_selected_elements() == []


def test_the_selection_symbols_are_declared_without_errorcheck():
    """The declarations themselves, not just their behaviour.

    A regression here would not fail any behavioural test until it met a real
    table, because the fake bridge bypasses ctypes entirely -- it is called
    directly rather than through the loaded DLL.  So the flag is asserted.
    """
    flags = {name: errorcheck for name, _, _, errorcheck in SIGNATURES}

    for name in (
        "isAccessibleTableRowSelected",
        "isAccessibleTableColumnSelected",
        "getAccessibleSelectionCountFromContext",
        "getAccessibleTableRowSelections",
        "getAccessibleTableColumnSelections",
    ):
        assert name in flags, f"{name} is no longer declared at all"
        assert flags[name] is False, (
            f"{name} is declared with errorcheck=True, which raises on the "
            "falsy return that means 'no' or 'nothing selected'"
        )


# ---------------------------------------------------------------------------
# Selecting one cell
# ---------------------------------------------------------------------------

def test_selecting_a_cell_shows_up_in_the_selection():
    element, bridge = a_table(rows=3, columns=4)

    element.select_cell(1, 2)

    assert element.selected_row_count == 1
    assert element.selected_column_count == 1
    assert element.selected_rows == [1]
    assert element.selected_columns == [2]
    assert element.is_row_selected(1) is True
    assert element.is_row_selected(0) is False
    assert element.is_column_selected(2) is True


def test_selecting_a_cell_uses_the_tables_own_index():
    """``getAccessibleTableIndex``, not row-major arithmetic.

    They happen to agree for a dense table, which is exactly why the call has to
    be the thing that decides -- a table that hides columns numbers them its own
    way.
    """
    element, bridge = a_table(rows=3, columns=4)

    element.select_cell(1, 2)

    assert bridge.count("getAccessibleTableIndex") == 1
    assert bridge.count("addAccessibleSelectionFromContext") == 1


def test_selecting_another_cell_replaces_the_selection_by_default():
    element, _ = a_table()

    element.select_cell(0, 0)
    element.select_cell(2, 3)

    assert element.selected_rows == [2]
    assert element.selected_columns == [3]


def test_selecting_with_clear_false_extends_the_selection():
    element, _ = a_table()

    element.select_cell(0, 0)
    element.select_cell(2, 3, clear=False)

    assert element.selected_rows == [0, 2]
    assert element.selected_columns == [0, 3]


def test_selecting_a_cell_that_does_not_exist_says_so():
    """JAB answers -1 for an out-of-range cell rather than refusing the call.

    Passing that -1 on would have added child -1 to the selection, which is a
    different object or an error somewhere less obvious.
    """
    element, bridge = a_table(rows=2, columns=2)

    with pytest.raises(JABException, match="no cell at row 5, column 0"):
        element.select_cell(5, 0)

    assert bridge.count("addAccessibleSelectionFromContext") == 0


# ---------------------------------------------------------------------------
# Selecting by row and column, which JAB has no call for
# ---------------------------------------------------------------------------

def test_selecting_a_row_adds_every_cell_in_it():
    element, bridge = a_table(rows=3, columns=4)

    element.select_row(1)

    assert bridge.count("addAccessibleSelectionFromContext") == 4
    assert element.selected_rows == [1]
    assert element.selected_columns == [0, 1, 2, 3]
    assert element.selected_row_count == 1


def test_selecting_a_column_adds_every_cell_in_it():
    element, bridge = a_table(rows=3, columns=4)

    element.select_column(2)

    assert bridge.count("addAccessibleSelectionFromContext") == 3
    assert element.selected_columns == [2]
    assert element.selected_rows == [0, 1, 2]


def test_selecting_a_row_on_a_row_selecting_table_adds_one_cell():
    """The add is a toggle, so one add is the whole row and a second undoes it.

    ``AccessibleJTable.addAccessibleSelection(i)`` calls
    ``JTable.changeSelection(row, column, true, false)``, and ``changeSelection``
    toggles that same ``selected`` value into *both* selection models -- with the
    column model updated unconditionally.  Adding every cell of the row therefore
    turns the row off again: four adds on a 3x4 table left
    ``selected_rows == []`` and ``selected_columns == [0, 2]``, measured on a real
    JDK 17 table through a real bridge.
    """
    element, bridge = a_row_selecting_table(rows=3, columns=4)

    element.select_row(1)

    assert bridge.count("addAccessibleSelectionFromContext") == 1
    assert element.selected_rows == [1]
    assert element.is_row_selected(1) is True
    assert element.selected_row_count == 1


def test_selecting_an_already_selected_row_again_leaves_it_selected():
    """``clear=False`` must not toggle off what is already there."""
    element, bridge = a_row_selecting_table(rows=3, columns=4)

    element.select_row(1)
    added = bridge.count("addAccessibleSelectionFromContext")
    element.select_row(1, clear=False)

    assert bridge.count("addAccessibleSelectionFromContext") == added
    assert element.selected_rows == [1]


def test_selecting_a_column_on_a_column_selecting_table_adds_one_cell():
    """The mirror of the row case, and it failed the same way.

    With an even row count the toggling loop ended on ``selected_columns == []``
    and ``selected_rows == [0, 2]`` -- four adds that selected no column at all.
    """
    element, bridge = a_column_selecting_table(rows=4, columns=3)

    element.select_column(2)

    assert bridge.count("addAccessibleSelectionFromContext") == 1
    assert element.selected_columns == [2]
    assert element.is_column_selected(2) is True


def test_the_fake_reproduces_the_measurement_from_the_runner():
    """A guard on the fake, not on the library.

    Driving the raw adds the old ``select_row`` made must land on exactly what the
    runner reported, or the fake is not a faithful model and the three tests above
    prove nothing.  This one does not exercise the old code path on purpose -- a
    regression test for that is the first test in this group.
    """
    element, _bridge = a_row_selecting_table(rows=5, columns=4)

    for index in (4, 5, 6, 7):
        element._select_accessible_table_index(index)

    assert element.selected_rows == []
    assert element.selected_columns == [0, 2]
    assert element.is_row_selected(1) is False


def test_select_all_takes_the_selection_the_table_offers():
    element, bridge = a_table(rows=2, columns=3)

    element.select_all()

    assert bridge.count("selectAllAccessibleSelectionFromContext") == 1
    assert element.selected_row_count == 2
    assert element.selected_column_count == 3
    # The fallback must not run when the bridge's own call worked; this is the
    # "read the result back" part being cheap rather than doubling the work.
    assert bridge.count("addAccessibleSelectionFromContext") == 0


def test_select_all_is_not_a_no_op_on_a_row_selecting_table():
    """The bridge's own call falls through there, so the table gets walked.

    ``AccessibleJTable.selectAllAccessibleSelection()`` is
    ``if (cellSelectionEnabled) { selectAll(); }`` and does nothing otherwise, so on
    a default Swing table it raises nothing and selects nothing.  One add per row is
    enough, because on that table the first cell of a row selects the whole row.
    """
    element, bridge = a_row_selecting_table(rows=3, columns=4)

    element.select_all()

    assert bridge.count("selectAllAccessibleSelectionFromContext") == 1
    assert bridge.count("addAccessibleSelectionFromContext") == 3
    assert element.selected_rows == [0, 1, 2]
    assert element.selected_row_count == 3


def test_select_all_on_a_column_selecting_table_takes_every_column():
    """The mirror: there one add per column is what selects everything."""
    element, bridge = a_column_selecting_table(rows=4, columns=3)

    element.select_all()

    assert bridge.count("addAccessibleSelectionFromContext") == 3
    assert element.selected_columns == [0, 1, 2]


def test_clearing_the_selection_empties_it():
    element, _ = a_table()

    element.select_row(0)
    element.clear_selection()

    assert element.selected_rows == []
    assert element.selected_columns == []
    assert element.get_selected_elements() == []


# ---------------------------------------------------------------------------
# The elements behind the selection -- what #61 was asking for
# ---------------------------------------------------------------------------

def test_the_selected_cells_come_back_as_elements():
    """The point of the whole exercise.

    ``get_cell()`` reads the table's cell list, which many tables report with
    bounds of -1, so the element is real but cannot be clicked.  The cells behind
    the selection are the ones the application is presenting, and the ones its
    actions will work on.
    """
    element, _ = a_table(rows=3, columns=4)

    element.select_cell(1, 2)
    chosen = element.get_selected_elements()

    assert len(chosen) == 1
    assert chosen[0].name == "r1c2"


def test_a_multi_selection_comes_back_in_order():
    element, _ = a_table(rows=3, columns=4)

    element.select_row(2)
    element.select_cell(0, 1, clear=False)
    names = [each.name for each in element.get_selected_elements()]

    assert names == ["r0c1", "r2c0", "r2c1", "r2c2", "r2c3"]


def test_the_elements_handed_out_really_are_references():
    """They must be released, and the model says so rather than leaking quietly.

    Every object JAB returns carries a reference; obtaining the same cell twice
    means releasing it twice, and using it after the last release is an error.
    ``tests/_fakejab.py`` counts, so this asserts the contract rather than
    trusting it.
    """
    element, bridge = a_table(rows=2, columns=2)
    element.select_cell(0, 1)

    chosen = element.get_selected_elements()
    assert bridge.refs[chosen[0].accessible_context.value] == 2  # held, then taken

    element.release_jabelement(chosen[0])
    assert bridge.refs[chosen[0].accessible_context.value] == 1


def test_get_selected_element_still_returns_the_first_one():
    """Kept for compatibility with what list and combo box callers already use."""
    element, _ = a_table(rows=2, columns=2)

    element.select_row(1)

    assert element.get_selected_element().name == "r1c0"


# ---------------------------------------------------------------------------
# Refusing clearly, which is what #57 was actually about
# ---------------------------------------------------------------------------

def test_select_on_a_table_explains_itself():
    """It used to be ``KeyError: 'table'``.

    The issue asked for a select action on a table and got a dict lookup failure
    from inside pyjab.  The message now names what to use instead.
    """
    element, _ = a_table()

    with pytest.raises(JABException) as caught:
        element.select("anything")

    message = str(caught.value)
    assert "KeyError" not in message
    assert "select_cell" in message
    assert "get_selected_elements" in message


def test_select_still_works_for_the_roles_it_supports():
    """The guard must not have swallowed the four that were already there."""
    element, _ = bind(node("list", name="choices"))

    with pytest.raises(Exception) as caught:
        element.select("missing", wait_for_selection=False)

    # Whatever a list lookup does when the option is absent, it is not the
    # "select() does not apply" guard being tripped by a list.
    assert "does not support a 'list'" not in str(caught.value)


@pytest.mark.parametrize("method, args", [
    ("select_cell", (0, 0)),
    ("select_row", (0,)),
    ("select_column", (0,)),
    ("clear_selection", ()),
    ("select_all", ()),
])
def test_the_table_methods_refuse_a_non_table_by_name(method, args):
    element, _ = bind(node("list", name="choices"))

    with pytest.raises(JABException, match="needs a table"):
        getattr(element, method)(*args)


@pytest.mark.parametrize("attribute", [
    "selected_rows",
    "selected_columns",
    "selected_row_count",
    "selected_column_count",
])
def test_the_table_properties_refuse_a_non_table(attribute):
    element, _ = bind(node("list"))

    with pytest.raises(JABException, match="needs a table"):
        getattr(element, attribute)


def test_a_table_with_no_columns_does_not_divide_by_zero():
    """A table that reports no columns is a table with nothing in it."""
    element, _ = bind(table(0, 0, name="empty"))

    assert element.selected_rows == []
    assert element.selected_columns == []
    assert element.get_selected_elements() == []


# ---------------------------------------------------------------------------
# The visible children, which is what a big table actually has
# ---------------------------------------------------------------------------

def test_visible_children_come_back_as_elements():
    """The supported form of the call the troubleshooting page used to make.

    #59 is "the application crashes while reading table data", and the cause is
    indexing past the end of what `getVisibleChildren` actually returned.  The
    page recommended `table._get_visible_children()` -- private, and reachable
    only by knowing it was there.
    """
    element, bridge = a_table(rows=2, columns=3)

    children = element.get_visible_children()

    assert [each.name for each in children] == ["r0c0", "r0c1", "r0c2",
                                                "r1c0", "r1c1", "r1c2"]
    assert bridge.count("getVisibleChildren") == 1


def test_the_count_comes_from_the_call_not_from_the_table():
    """`returnedChildrenCount`, not row_count * column_count.

    A table that reports 100 rows on screen may have 8.  Believing the table is
    what reads past the array.
    """
    element, _ = bind(node("table", *[node("label", name=f"c{i}") for i in range(3)],
                           name="partial", row_count=100, column_count=3))

    children = element.get_visible_children()

    assert len(children) == 3, "it believed row_count * column_count"
    assert element.table["row_count"] == 100


def test_the_visible_children_are_references_too():
    element, bridge = a_table(rows=1, columns=2)

    children = element.get_visible_children()
    handle = children[0].accessible_context.value

    assert bridge.refs[handle] == 2
    element.release_jabelement(children[0])
    assert bridge.refs[handle] == 1
