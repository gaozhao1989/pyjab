Thanks for the report. To move this forward I need a bit more detail:

1. What does `table.table` return for `row_count` / `column_count`?
2. What does `table.get_cell(row, column)` give you -- an exception, or an
   element with unusable properties?
3. Does the table report `AccessibleSelection` and `AccessibleTable` in
   `element.accessible_interfaces`?

Background on why this is awkward: JAB only allows interaction with table
contents through the accessible selection, and many tables report
`bounds = {x: -1, y: -1, width: -1, height: -1}` for their cells (see #20).
When bounds are invalid, `simulate=True` cannot work at all -- there is no
coordinate to click -- so the accessibility action path is the only option.
I want to know which of those two situations you are in.

Table selection support (select row/column/cell, read back the selection) is
planned for 1.3.0, tracked in #57.
