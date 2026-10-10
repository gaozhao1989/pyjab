# pyjab

The API guide.

**Contents**

* [JABDriver](#jabdriver)
* [Locators](#locators)
* [Locating an element](#locating-an-element)
* [JABElement](#jabelement)
* [The `simulate` parameter](#the-simulate-parameter)
* [Tables](#tables)
* [Windows and screenshots](#windows-and-screenshots)
* [Limitations](#limitations)

---

# JABDriver

`JABDriver` binds to a running Java application and is the entry point for
everything else.

```python
from pyjab.jabdriver import JABDriver

driver = JABDriver(title="My Application")
```

| Argument | Meaning |
|---|---|
| `title` | Window title to bind to. Matched with `fnmatch`, so wildcards work. |
| `file_path` | Optional. Launch this application first. `.jnlp` goes through `javaws`; anything else is executed directly. The process is **not** waited on, so pyjab can bind to the window it opens. Before 1.3.0 this blocked until the application exited, which made `file_path` unusable together with `title`. |
| `bridge_dll` | Optional. Explicit path to `WindowsAccessBridge-XX.dll`. |
| `hwnd` | Optional. Bind by window handle instead of title. |
| `vmid` / `accessible_context` | Optional. Bind to an already-known accessibility context. |
| `timeout` | Seconds to wait for the window to appear. Defaults to 30. |

You need `title`, or `hwnd`, or both `vmid` and `accessible_context`. Passing
`file_path` without `title` will launch the application but not bind to it.

As a context manager, leaving the block terminates the bound Java process:

```python
with JABDriver(title="My Application") as driver:
    ...
```

## Locators

Every `find_element_by_*` takes a locator value, and there is a generic form for
when you want to choose the strategy at runtime.

| `By` strategy | Attribute | Example |
|---|---|---|
| `By.NAME` | accessible name | `find_element_by_name("Login")` |
| `By.DESCRIPTION` | accessible description | `find_element_by_description("Signs you in")` |
| `By.ROLE` | role | `find_element_by_role("push button")` |
| `By.STATES` | states, comma separated | `find_element(by=By.STATES, value="enabled,visible,showing")` |
| `By.OBJECT_DEPTH` | depth in the tree | `find_element_by_object_depth(2)` |
| `By.CHILDREN_COUNT` | number of children | `find_element_by_children_count(0)` |
| `By.INDEX_IN_PARENT` | position among siblings | `find_element_by_index_in_parent(3)` |
| `By.XPATH` | pyjab's XPath-like syntax | `find_element_by_xpath("//push button[@name=contains('OK')]")` |

```python
from pyjab.common.by import By

driver.find_element(By.NAME, "Login")          # generic form
driver.find_elements_by_role("push button")     # every match, not just the first
```

## Locating an element

**This is the part people get stuck on.** Read it before filing an issue.

You write locators for the **accessible name, role, description or state** of a
control — the information a screen reader would announce, which is frequently
*not* the same as the visible label.

### Look, rather than guess

`pyjab-inspect` ships with pyjab and prints what is actually in the window:

```console
$ pyjab-inspect windows                     # which Java windows JAB can see
$ pyjab-inspect tree "My Application"       # role, name, index and children per element
$ pyjab-inspect find "My Application" "//panel//push button"
$ pyjab-inspect locator "My Application" --name Login
```

`tree` shows exactly the fields `find_element_by_*` matches on: `name`,
`description`, `role`, `states`, `indexInParent`, `bounds`, `childrenCount`,
`objectDepth`. Whatever you see there is what you pass to a locator. `find` resolves a
locator one step at a time and reports **which step** stopped matching, which is
usually faster than reading a tree.

For a whole-machine view, [Access Bridge Explorer](https://github.com/google/access-bridge-explorer)
shows every Java process at once and goes further than `pyjab-inspect` does — but it is
a separate Java application to install, and if it cannot see a control, neither can
pyjab.

### Choosing a strategy

```python
# The control has a name -- the common case.
driver.find_element_by_name("Submit")

# No useful name, but a distinctive role.
driver.find_element_by_role("push button")

# Several controls share a role; narrow by state.
driver.find_element(By.STATES, "enabled,focusable,visible,showing")

# Neither name nor useful role: fall back to position.
driver.find_element_by_index_in_parent(3)

# Complex hierarchies.
driver.find_element_by_xpath("//internal frame[@name='FRM-999']")
driver.find_element_by_xpath("//push button[@name=contains('OK')]")
```

When you cannot find a control, enumerate what is there before guessing:

```python
for element in driver.find_elements_by_role("push button"):
    print(repr(element.name), element.role, element.index_in_parent)
```

### XPath syntax

pyjab's XPath support is its own, not a full XPath implementation. It supports:

```
//panel                          any panel, anywhere
//internal frame/panel           a panel that is a child of an internal frame
//push button[@name='OK']         exact name
//push button[@name=contains('OK')]
//text[@states='enabled,visible']
//panel[@indexinparent=3]
//panel[@objectdepth=7]
//panel[@childrencount=2]
```

Also understood: `@description`, `@role`, `@states`, `contains()`, and both `and`
and `or` between predicates, with `and` binding tighter as it does in XPath:

```python
//push button[@name='OK' or @name='Apply']
//push button[@name='OK' and @indexinparent=2]
```

**Where a lookup starts.** A leading `.` means "from this element"; without it the
locator means the whole window. That is XPath's own distinction between `.//` and
`//`, and it is the difference between these two:

```python
element.find_element_by_xpath("//push button")    # anywhere in the window
element.find_element_by_xpath(".//push button")   # only inside element
```

**Positions.** `[n]` picks the n-th match, counted **within each parent** and
**1-based**, which is XPath's own meaning and not "the n-th in the window":

```python
//panel[1]                 # the first panel child of every parent
//panel/panel[2]           # the second panel child of every panel
//push button[@name='OK'][1]
```

Predicates are applied **in order**, so the two orders ask different questions:

```python
//panel[@name='OK'][2]     # the second of those named OK
//panel[2][@name='OK']     # the second panel child, if it happens to be named OK
```

**Comparisons.** `=`, `!=`, `<`, `<=`, `>` and `>=` all work:

```python
//panel[@indexinparent > 9]        # numeric: p10 and p11, not p9
//panel[@role != 'panel']
//panel[@indexinparent>=2 and @indexinparent<5]
```

An attribute the element reports as an integer is compared **numerically**, so
`[@indexinparent > 9]` finds index 10 rather than putting `"10"` before `"9"`.
Everything else is compared as a **string**, which is what XPath does with strings —
`[@name < 'p2']` is lexicographic, and `p10` sorts before `p2`. `contains()` remains
available with `=` only.

**Unions.** `|` searches both sides:

```python
//push button | //label
//internal frame[@name='A'] | //internal frame[@name='B']
```

`find_elements_by_xpath` returns each match **once** — XPath defines a node-set as
having no duplicates — and `find_element_by_xpath` takes the **first branch that
matches**, tried in the order written. That is not the same as "first in document
order", which is what XPath would say for a set; it is what a first-match API can
honestly offer, so it is stated rather than implied.

**The parent axis.** `..` steps up one level, and a step after it is a child of the
result, as in XPath:

```python
//label/..                 # the parent of every label
//label/../panel           # the panel children of each of those parents
//panel/../..              # two levels up
```

A result is never returned twice. XPath defines a node-set as having **no
duplicates**, and `//panel/..` reaches the same parent once per child.

`[0]`, `[position()=2]` and `[last()]` are rejected with a parse error — the first
because positions are 1-based, the others because they need an expression evaluator,
and are rejected rather than answered: a locator that cannot work should say so, not
report that the element is missing.

## JABElement

`find_element_*` returns a `JABElement`.

### Reading properties

```python
element.name                       # accessible name
element.description                # accessible description
element.role                       # 'push button', 'text', 'table', ...
element.role_en_us                 # localised role
element.states                     # 'enabled,focusable,visible,showing'
element.states_en_us
element.bounds                     # {'x': .., 'y': .., 'width': .., 'height': ..}
element.object_depth
element.index_in_parent
element.children_count
element.text                       # text content, when the element exposes AccessibleText
element.table                      # {'row_count': .., 'column_count': ..}, for tables
element.size                       # {'width': .., 'height': ..}

element.accessible_component       # which accessibility interfaces this element has
element.accessible_action
element.accessible_selection
element.accessible_text
```

### State checks

```python
element.is_enabled
element.is_visible
element.is_showing
element.is_checked
element.is_selected
element.is_editable
```

### Acting on an element

```python
element.click()
element.click(simulate=True)       # see below
element.double_click()             # mouse only
element.context_click()            # mouse only: opens the context menu
element.send_text("hello")
element.clear()
element.select("Option A")         # combo boxes, lists, tabs
element.expand()                   # a no-op if it is already expanded
element.scroll(to_bottom=True)
element.slide(to_bottom=True)
element.spin("3")                  # spinners
element.get_selected_element()     # the first selected child
element.get_selected_elements()    # all of them
element.get_visible_children()     # what is actually on screen
element.get_screenshot_as_png()    # PNG bytes, and the base64 and Image forms
element.bounds_within(other)       # geometry, not the `visible` state
element.scroll_into_view()         # best effort; returns whether it worked
```

`double_click()` and `context_click()` always move the mouse: Java Access Bridge
exposes no accessibility action for either, so unlike `click()` they have no
non-simulated form and they need the element to report usable bounds. Both leave
the window in the foreground first.

### Coordinate conversion on scaled displays

`simulate=True` moves the real mouse, and the coordinates JAB reports are the
**target application's** while the mouse API takes the **caller's**. When the two
scale differently the click lands in the wrong place with nothing reporting an
error.

pyjab handles this itself — there is nothing to configure:

| target | pyjab | what happens |
|---|---|---|
| DPI unaware | unaware | coordinates used as-is; the two cancel |
| DPI unaware | aware | scaled up before the click |
| DPI aware | unaware | scaled down, so Windows scales it back |
| DPI aware | aware | coordinates used as-is |

A display at 100% needs no conversion whatever the awarenesses are, and so does a
case where the target's awareness cannot be read — an elevated target cannot be
opened, and guessing there would move the cursor on a setup that works.

### When nothing matches

`find_element*` and `find_elements*` both **raise `JABException`**, with a message
naming the locator:

```python
driver.find_element_by_name("Save")     # raises if there is no Save button
driver.find_elements_by_role("button")  # raises if there are no buttons at all
```

That is Selenium's `find_element` behaviour, and it is deliberately not Selenium's
`find_elements` behaviour — an empty list and a locator that matched nothing look
the same at the call site, and the second one is nearly always the bug. Use
`get_children()` when an empty answer is ordinary:

```python
element.get_children()                  # [] when there are none; never raises
```

### Searching inside an element

Anything you can do from the driver, you can do from an element — the search is
then restricted to that element's subtree, which is considerably faster:

```python
panel = driver.find_element_by_name("OrderPanel")
button = panel.find_element_by_name("Submit")
```

Both objects answer the same way, including about the window itself: a search looks at
**descendants only**, so `driver.find_element_by_name(window_title)` raises rather than
returning the window. A window is not its own descendant, and the window is already
there as `driver.root_element`:

```python
driver.root_element.find_element_by_name("Submit")   # same as above
```

Every element a search returns is yours to release with `release_jabelement`. The root
is the exception, because the driver holds it for its lifetime — which is part of why
the search does not hand it back.

### Screenshots

```python
driver.get_screenshot_as_file("window.png")   # writes a PNG, returns None

png = driver.get_screenshot_as_png()          # the PNG bytes
b64 = driver.get_screenshot_as_base64()       # the same bytes, base64

image = driver.get_screenshot()               # a Pillow Image
```

All four work on an element as well, cropping to that element:

```python
element.get_screenshot_as_file("element.png")
element.get_screenshot_as_png()
element.get_screenshot_as_base64()
element.get_screenshot()
```

The names and the return types are Selenium's, so the usual embedding works:

```python
html = f'<img src="data:image/png;base64,{driver.get_screenshot_as_base64()}">'
```

One difference to know about: **`get_screenshot_as_file()` returns `None`, not
`True`/`False`.** Pillow raises if the file cannot be written, so a failure is an
exception rather than a value you have to remember to check.

## The `simulate` parameter

Most interaction methods accept `simulate=`. The two modes have genuinely
different trade-offs, and getting this wrong is a common source of confusion.

**`simulate=False` (the default)** drives the control through the Java Access
Bridge accessibility action API. It works even when the element reports invalid
bounds, and it does not need the window in the foreground. This is the safer
default.

**`simulate=True`** moves the real mouse cursor to the centre of the element and
clicks. Use it when the accessibility action does nothing — some custom or
third-party components only respond to real input.

Be aware that `simulate=True`:

* brings the target window to the foreground, so the machine cannot be used for
  anything else;
* **fails in a non-interactive session** — a CI agent running as a Windows
  service cannot call `SetForegroundWindow`, and you will see
  `pywintypes.error: (0, 'SetForegroundWindow', ...)`;
* cannot work when `element.bounds` is `-1` for any coordinate, because there is
  no point to click.

Rule of thumb: start with the default, and only reach for `simulate=True` when
the accessibility action is ignored.

## Tables

A Java table is driven through the accessibility selection API, not by clicking
cells — cells frequently report `bounds = -1`, so there is no coordinate to click.

Reading and selecting are separate. `get_cell()` reads the table's **cell list**,
which is fine for text. Selecting goes through the table's **accessible
selection**, and the cells that come back from there are the ones the application
is presenting as selected — for many tables those are the ones whose actions
actually work. That difference is what #57 and #61 were about.

```python
table = driver.find_element_by_role("table")

info = table.table                  # {'row_count': .., 'column_count': ..}
print(table.get_cell(row=2, column=1).text)
```

### Selecting

```python
table.select_cell(row=2, column=1)   # clears the selection first
table.select_row(2)                  # every cell in the row
table.select_column(1)
table.select_all()
table.clear_selection()
```

Then read back what the application reports, rather than assuming it agrees:

```python
table.selected_rows                  # [2]
table.selected_columns               # [1]
table.selected_row_count             # 1
table.is_row_selected(2)             # True
table.is_column_selected(0)          # False
```

**JAB has no call that selects a row or a column.** `select_row()` selects a row by
adding its cells to the table's selection — but adding a cell is a **toggle**, so a
cell that is already selected is skipped rather than added again. On a Swing table in
its default row-selection mode the first cell selects the whole row and the rest are
then found to be selected already; on a table with individual cell selection enabled
every cell is added. Whether the application then reports the *row* as selected is its
own decision — some do, some only ever report cells. Check `selected_rows` after
selecting rather than building on the assumption.

`select_all()` closes the same gap from the other side. On a Swing `JTable` the
bridge's own call does nothing unless individual cell selection is enabled --
`AccessibleJTable.selectAllAccessibleSelection()` falls through in row-selection mode --
so the result is read back and the table is walked when nothing was selected. It selects
every row, every column or every cell, whichever the table allows.

### The selected cells

`get_selected_elements()` returns the cells behind the selection as `JABElement`s
— the "Select Cells" property rather than "Cells", in Access Bridge Explorer's
terms:

```python
table.select_row(2)
for cell in table.get_selected_elements():
    print(cell.name, cell.text)
    cell.release_jabelement()        # see below
```

Each one carries a Java object reference, so **release it when you have finished**,
as with any object pyjab hands out. An empty list means nothing is selected, which
is the ordinary state of a table you have just opened.

### Rows scrolled out of view

They are not in the accessibility tree, so there is nothing to read and trying to
reach them anyway can destabilise the application (#59). Two tools:

```python
children = table.get_visible_children()   # only what is on screen
row = table.get_cell(row=40, column=0)

print(row.bounds_within(table))           # inside the table's rectangle?
if not row.bounds_within(table):
    row.scroll_into_view()                # best effort; returns whether it worked
```

`get_visible_children()` takes its count from the bridge's own
`returnedChildrenCount`, so it cannot run past what came back.

`scroll_into_view()` is **best effort and says so**: Java Access Bridge exposes no
scroll position, so there is no offset to compute and jump to. It nudges the
vertical scroll bar one step at a time and re-reads the rectangle, stopping when
the element comes inside, when the rectangle stops changing (the bar is at its
end), or after `max_steps`. It returns whether it succeeded, and `False` also
means "there is no scrollable ancestor" — a control that does not scroll is
simply not this problem. It needs valid bounds on both the element and its
scrollable ancestor; a table whose cells report `-1` cannot be scrolled this way,
and the accessibility action path is the only option — see
[Selecting](#selecting).


## Windows and screenshots

```python
driver.hwnd
driver.pid
driver.vmid
driver.title
driver.set_window_size(1280, 800)
driver.get_window_position()
driver.set_window_position(0, 0)
driver.maximize_window()
driver.minimize_window()
driver.get_version_info()           # Java Access Bridge version information
driver.root_element                 # the root JABElement of the window
driver.get_focused_element()        # the currently focused element, or None
```

## Limitations

pyjab can only see what Java Access Bridge exposes. The following are **not**
supported, and no client-side work will change that:

* **Canvas-drawn interfaces.** If a component paints its own widgets onto a
  `Canvas`, there is nothing in the accessibility tree to find. Access Bridge
  Explorer will show the canvas with no children.
* **Java applets, or Java embedded in a browser or Electron shell.** These run in
  a process that does not expose the bridge to the desktop.
* **Components that do not implement the accessibility interfaces.**
* **Off-screen table rows** — see [Tables](#tables).

Check with `pyjab-inspect tree "<window title>"` first, and with Access Bridge
Explorer if you want the whole machine at once. **If neither can see it, pyjab
cannot either.**

## Known rough edges

These are tracked, and are the honest answer to "why is this slow / missing":

* **Locating elements in large windows is slow.** Every lookup walks the
  accessibility tree from the root and each node costs a cross-process call. A
  window with a large table can take tens of seconds for a failed lookup.
  Narrowing the search root with an element-level `find_element_*` helps.
* **DPI scaling.** On a display at 125% or 150%, `simulate=True` can miss
  because logical and physical coordinates differ. Whether it does depends on
  this process's DPI awareness and on the target's, so `tools/verify_dpi.py`
  measures it rather than guessing -- run that before reporting it (#62).
* **XPath coverage** is the subset listed above.
