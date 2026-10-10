# Changelog

The full changelog lives in the repository, in
[`CHANGELOG.rst`](https://github.com/gaozhao1989/pyjab/blob/master/CHANGELOG.rst),
and is also shown on the GitHub release page for each version.

## Upgrading

```console
> pip install --upgrade pyjab
```

## Release history at a glance

| Version | What it was about |
|---|---|
| **1.11.0** | `send_keys()` for modifier chords, `focus()` for bringing a window forward and reporting whether it worked, and `visible_children_count()` — which is not the number `walk()` yields, because a walk includes hidden children. Five measured JAB calls now raise on failure instead of returning a value to check. |
| **1.10.0** | `pyjab.list_java_windows()` — every Java window the bridge can see, which a caller previously could not find out at all — and `JABDriver.detach()`. `Logger` no longer configures the host's root logger; it adds a `NullHandler` to pyjab's own. |
| **1.9.0** | The GUI suite runs in CI on a hosted Windows runner, which turned out to have a real interactive desktop rather than being a service in session 0 — measured, not assumed. Dropped the `Pillow` dependency: screenshots are captured with GDI and written with zlib. |
| **1.8.0** | Completed the XPath subset the tracking issue asked for: positional predicates, ordered evaluation, comparison operators, unions and the parent axis. Two things came out of it — no result is returned twice, and the new locators are exercised against the real application's tree rather than against trees built to suit them. |
| **1.7.0** | Clicks landed in the wrong place on a scaled display; every absolute xpath lookup leaked a Java object; and `or` between XPath predicates was evaluated as `and`, which found nothing and reported it as the element being absent (#62, #43). |
| **1.6.3** | Three screenshot methods the documentation used to promise, and the removal of a module nothing called. See *Removed* for why that last one went into a patch release rather than a minor. |
| **1.6.2** | `AccessibleTable` selection and scrolling, plus the two Windows failures that 1.6.1 was published with. |
| **1.6.1** | `AccessibleTable` selection (#57). A table is driven through its own accessibility selection, and JAB has no call that selects a row or a column, so there was no way in at all. |
| **1.6.0** | **Relicensed to MIT**, from GPLv2. The reason for the GPL was code derived from NVDA; the five files carrying it were rewritten from their behaviour, and every remaining contributor's consent is recorded in `CONTRIBUTORS.txt`. |
| **1.5.0** | Added `double_click()` and `context_click()`. Fixed a mouse click on an element with impossible bounds moving the cursor to the corner of the display, and added `tools/verify_dpi.py` to measure what coordinate space `simulate=True` needs on a given display (#62). |
| **1.4.3** | `expand()` no longer collapses an element that was already expanded — it sent a toggle, so a `JTree` that started open could not be walked. Added `is_expanded()`. The GUI suite now starts the test application once per run instead of once per test. |
| **1.4.2** | Test-only. Fixed the GUI suite's locators against a real desktop: the test application named components in a way the accessibility layer ignores, and cell renderers were given names that flattened every tree row. |
| **1.4.1** | Test-only. Pinned the test JVM's locale, because a colour chooser's labels come from resource bundles and read differently in Chinese. |
| **1.4.0** | Element lookups now walk the accessibility tree in the order the locator implies, so a deep path costs the same in a large window as a small one — measured at 2,063 JAB calls down to 30. A locator starting with `.` is relative to the element it is issued from, and the GUI suite drives a Swing application that lives in the repository instead of downloading Oracle's demo applets. |
| **1.3.1** | Fixed twelve defects found by reading the source. None had been reported, and most were silent — they produced a wrong answer rather than an error. |
| **1.3.0** | Rewrote the Windows message pump. A window or dialog opened after the first one is now noticed; `wait_until_element_exist()` no longer spins the CPU; the two leaked kernel event handles are gone. |
| **1.2.1** | Shipped `JABDriver.get_focused_element()`, contributed in 2022 but never released. |
| **1.2.0** | First release since 2022. Fixed Java Access Bridge DLL discovery on JDK 11+ — the DLL had moved from `%JAVA_HOME%\jre\bin` to `%JAVA_HOME%\bin`, so every modern JDK failed until you set `JAB_HOME` by hand. Removed the `pypiwin32`/`pywin32` dependency conflict. Migrated packaging to `pyproject.toml` and added CI. |
| 1.1.7 | Last release of the original series (May 2022). |

## Notable upgrade notes

### Upgrading to 1.7.0

Nothing in the API changed, but two defects were fixed that could have made working code
behave wrongly: clicks on a scaled display, and `or` between XPath predicates being
evaluated as `and`. If you worked around either, the workaround is no longer needed.

### Upgrading to 1.6.0

**The licence changed from GPLv2 to MIT.** If you chose not to use pyjab because of the
GPL's terms, that reason is gone as of 1.6.0. Nothing in the API changed.

### Upgrading to 1.4.0

* **A locator that matches more than one element may return a different one than
  it used to.** Lookups now walk the accessibility tree in the order the locator
  implies rather than descending into every node first, which is what made them
  fast. For a locator written to match one element this changes nothing; for an
  ambiguous one it can. Name a component in the locator, or narrow the search
  root with an element-level `find_element_*`, and the question does not arise.
* A locator starting with `.` is now relative to the element it is issued from:
  `element.find_element_by_xpath(".//push button")` searches inside `element`.
  `//push button` still searches from the top-level object, as before.

### Upgrading to 1.3.0

* `Win32Utils.setup_msg_pump()` has been removed. It was an internal generator
  used to drive the message pump; use `Win32Utils.pump_messages()` if you were
  calling it directly.
* `pyjab.common.actorscheduler.ActorScheduler` is deprecated and unused. It is
  still importable, but nothing in pyjab uses it.
* `wait_until_element_exist()` takes a new `poll_interval` argument and now
  sleeps between attempts instead of spinning.

### Upgrading to 1.2.0

* If you were passing `bridge_dll=` or setting `JAB_HOME` purely as a workaround
  for the "DLL not found" error, you should no longer need to. Existing
  workarounds keep working.
* `setup.py` and `setup.cfg` were removed in favour of `pyproject.toml`. If any
  of your tooling called `python setup.py ...`, use `python -m build` instead.
* Python 3.12 users on 1.1.7 could not build from source at all, because
  `setup.py` imported `distutils`.
