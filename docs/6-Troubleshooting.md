# Troubleshooting

The problems people actually hit, in rough order of frequency.

If you are about to open an issue, please check here first — and if the answer
is here but unclear, say so in the issue. That is a documentation bug and worth
fixing.

---

## `FileNotFoundError: Java Access Bridge DLL ... could not be located`

pyjab could not find `WindowsAccessBridge-64.dll`.

The error message lists every environment variable it read, every directory it
probed, and three ways to fix it. Read it first — it usually names the problem.

The three usual fixes:

1. set `JAVA_HOME` to your JDK installation directory;
2. set `JAB_HOME` to the directory holding the DLL;
3. pass the path explicitly:

   ```python
   JABDriver(title="My App",
             bridge_dll=r"C:\Program Files\Java\jdk-21\bin\WindowsAccessBridge-64.dll")
   ```

**Check the bitness.** A 64-bit Python cannot load a 32-bit DLL. If only the
other architecture is present, the error message says so explicitly. The
commonest cause is a 32-bit JRE alongside 64-bit Python.

Remember that the DLL moved in JDK 11: it used to be in `%JAVA_HOME%\jre\bin`
and is now in `%JAVA_HOME%\bin`. Versions before 1.2.0 only looked in the old
place, which is why JDK 11+ users had to set `JAB_HOME` by hand.

---

## `pip install pyjab` resolves slowly, or reports conflicting dependencies

You are on pyjab 1.1.7 or older. Those releases declared both `pypiwin32>=223`
and `pywin32>=302`; `pypiwin32` is a deprecated shim that pins `pywin32==223`,
so resolution failed for every released version.

Upgrade to 1.2.0 or later, which removes `pypiwin32` and gives `pywin32` a
`sys_platform == "win32"` marker.

---

## `ModuleNotFoundError: No module named 'win32process'`

You are not on Windows. pyjab drives the Windows Java Access Bridge and cannot
run anywhere else.

Since 1.2.0 this is reported as a clear `ImportError` from `pyjab.jabdriver` or
`pyjab.jabelement` rather than a bare `ModuleNotFoundError`. `import pyjab`
itself still works, because `pyjab.config` is platform independent.

---

## `JABException: JABElement with locator ... does not found`

The locator did not match anything. In order of likelihood:

1. **The accessible name is not the visible label.** They are frequently
   different — a button showing `Login` may have the accessible name `Login...`,
   `&Login`, or nothing at all. Install
   [Access Bridge Explorer](https://github.com/google/access-bridge-explorer)
   and read the real value.
2. **You bound to the wrong window.** Check `driver.title` and `driver.hwnd`.
3. **The control is inside a different top-level window** — a dialog or a second
   window. Bind to that window, or search the dialog by role.
4. **The control genuinely has no accessible name.** Use
   `find_elements_by_role(...)` and inspect what comes back; a sibling or parent
   usually carries the label.

Enumerating is almost always faster than guessing:

```python
for element in driver.find_elements_by_role("push button"):
    print(repr(element.name), element.index_in_parent, element.bounds)
```

---

## Elements report `bounds = {'x': -1, 'y': -1, 'width': -1, 'height': -1}`

The application does not report geometry for this control. Table cells are the
usual case.

`simulate=True` **cannot** work here — there is no coordinate to click. Use the
accessibility action API, which is the default (`simulate=False`), or the
table-specific helpers described in [3. pyjab](3-pyjab.md#tables).

---

## `pywintypes.error: (0, 'SetForegroundWindow', 'No error message is available')`

You are using `simulate=True` from a process that is not attached to an
interactive desktop session — typically a CI agent running as a Windows service.

Windows refuses `SetForegroundWindow` from session 0. Two options:

1. **Drop `simulate=True`.** The default drives the control through the
   accessibility action API and does not need the foreground, so it works fine
   from a service session. This is the right answer for most cases.
2. **Run the agent interactively**, as a logged-in user, if you genuinely need
   real mouse input.

---

## The script freezes, or a newly opened window cannot be found

This was a real bug, fixed in **1.3.0**.

Java Access Bridge is COM based, and the accessibility events that announce a
window or dialog are delivered through the COM message queue of the thread that
called `Windows_run()`. Before 1.3.0 pyjab only serviced that queue while it was
waiting for the *first* window, so anything opening later could go unnoticed, and
a modal dialog could appear to hang the script.

If you are on 1.3.0 or later and still see this, please open an issue — and
include whether the window is a **modal** dialog, which JDK the target runs on,
and whether `simulate=True` appears anywhere in the script.

To check the fix on your own machine, run the script that ships with the
repository. It reproduces
[issue #56](https://github.com/gaozhao1989/pyjab/issues/56)'s scenario and prints
`PASSED` or `FAILED`:

```console
> python tools/verify_message_pump.py
```

---

## The application crashes while reading table data

Almost always because the code indexes past the end of the visible children
array on a table with many rows. Bound the loop by the size of what you actually
received, and scroll the row into view before reading it:

```python
children = table._get_visible_children()
count = len(children.children)      # do NOT assume row_count * column_count
```

Rows that are scrolled out of view are not in the accessibility tree. Reaching
for them anyway is what destabilises the application.

---

## Lookups are slow, or CPU is high while waiting

Every `find_element_*` walks the accessibility tree from the root, and each node
costs a cross-process call. On a window with a large table a failed lookup can
take tens of seconds.

Two things help today:

1. **Narrow the search root.** Find a stable ancestor once and search under it:

   ```python
   panel = driver.find_element_by_name("OrderPanel")
   button = panel.find_element_by_name("Submit")     # subtree only
   ```

2. **Do not poll by hand.** `wait_until_element_exist()` backs off between
   attempts; a `try/except` loop around `find_element_by_xpath` does not, and
   every failed attempt is a full traversal.

Writing out the full XPath path does **not** make it faster — pyjab does not yet
use the path to prune the traversal.

---

## Clicks miss on a high-DPI display

On a display at 125% or 150% scaling, Java Access Bridge reports logical
coordinates while the mouse API expects physical ones. pyjab does not convert
between them yet, so `simulate=True` can land in the wrong place.

Workarounds: run at 100% scaling, mark the target application as per-monitor DPI
aware, or use the default `simulate=False` and avoid coordinates entirely.

---

## Double-click and right-click

There is no `click(double=True)` or context-click API yet.

```python
# Double-click: two calls, close together.
element.click()
element.click()
```

That is unreliable if the two clicks straddle the system double-click interval.
For a real double-click you need valid bounds and the window in the foreground:

```python
import win32api, win32con

bounds = element.bounds
if bounds["width"] > 0 and bounds["height"] > 0:
    x = bounds["x"] + bounds["width"] // 2
    y = bounds["y"] + bounds["height"] // 2
    win32api.SetCursorPos((x, y))
    for _ in range(2):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
```

---

## The elements I need are not there at all

Check with [Access Bridge Explorer](https://github.com/google/access-bridge-explorer)
first. **If it cannot see them, pyjab cannot either.** The usual causes:

* **canvas-drawn interfaces** — the component paints its own widgets, so the
  accessibility tree stops at the canvas;
* **Java applets, or Java embedded in a browser or Electron shell** — the process
  does not expose the bridge to the desktop;
* **a stripped-down JRE** without the accessibility classes.

These are limitations of Java Access Bridge, not of pyjab.

---

## A long-running session gets slower and eventually hangs

Reported in [issue #43](https://github.com/gaozhao1989/pyjab/issues/43) and not
fully diagnosed. If you hit it:

* reuse one `JABDriver` instead of creating a new one per test;
* call `release_jabelement()` on elements you have finished with.

Please add your environment details to the issue if you can reproduce it — the
original report could not be reproduced by the maintainer, and "runs for an hour
then stalls, with CPU and memory both normal" is a symptom worth pinning down.
