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

### Use Access Bridge Explorer

Install [Access Bridge Explorer](https://github.com/google/access-bridge-explorer).
It shows the accessibility tree of any Java application, and every node displays
exactly the fields pyjab exposes: `name`, `description`, `role`, `states`,
`indexInParent`, `bounds`, `childrenCount`, `objectDepth`.

Whatever you see there is what you pass to `find_element_by_*`. This removes all
the guesswork, and it is also how you tell whether a control is reachable at all
— if Access Bridge Explorer cannot see it, neither can pyjab.

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

Also understood: `@description`, `@role`, `@states`, `contains()`, `and`
between predicates, and `[n]` positional predicates. Axes (`/` vs `//`,
`.`/`..`), comparisons such as `[@indexinparent > 10]`, and union (`|`) are
**not** supported.

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
element.get_selected_element()
```

`double_click()` and `context_click()` always move the mouse: Java Access Bridge
exposes no accessibility action for either, so unlike `click()` they have no
non-simulated form and they need the element to report usable bounds. Both leave
the window in the foreground first.

### Searching inside an element

Anything you can do from the driver, you can do from an element — the search is
then restricted to that element's subtree, which is considerably faster:

```python
panel = driver.find_element_by_name("OrderPanel")
button = panel.find_element_by_name("Submit")
```

### Screenshots

```python
driver.get_screenshot_as_file("window.png")
driver.get_screenshot_as_png()
driver.get_screenshot_as_base64()

element.get_screenshot_as_file("element.png")
```

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

Java tables are reached through the accessibility selection API, not by clicking
cells — cells frequently report `bounds = -1`.

```python
table = driver.find_element_by_role("table")

info = table.table                  # {'row_count': .., 'column_count': ..}
cell = table.get_cell(row=2, column=1)
print(cell.text)
```

**Rows scrolled out of view are not readable.** They are not in the
accessibility tree, and trying to reach them can destabilise the target
application. Scroll the table so the row is visible, then query again.

## Windows and screenshots

```python
driver.hwnd
driver.pid
driver.vmid
driver.title
driver.get_window_size()
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

Always check Access Bridge Explorer first. If it cannot see it, pyjab cannot
either.

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
