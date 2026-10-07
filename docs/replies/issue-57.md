Confirming this is still missing. `AccessibleSelection` is used for
list/combo/tab selection, but tables need the row/column selection entry points
and those are not exposed at all yet.

Plan for 1.3.0: expose selection on `AccessibleTable` (select row, select
column, select cell, read back the selection) and document the ordering
requirement -- JAB only lets you interact with a table through its accessible
selection, which is why clicking table cells with `simulate=True` does nothing
when the cells report `bounds = -1` (see #20 and #61).
