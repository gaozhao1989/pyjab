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
