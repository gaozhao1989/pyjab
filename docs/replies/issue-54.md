Re-confirming this is a real bug and noting the fix for 1.3.0.

`JABElement.find_element_by_xpath()` calls
`_get_children_by_level(level)` which defaults to `"root"`, so searching from a
child element silently re-traverses from the top of the tree. The `level`
argument exists but is never threaded through from the xpath path.

This is both a correctness bug (a relative path can match something outside
the subtree you started from) and a performance bug (it is why searching from
a child is no faster than searching from the driver -- see #33). Fixing it
together with the traversal pruning work.
