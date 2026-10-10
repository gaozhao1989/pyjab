# Overview

_Is pyjab the right tool for your problem?_

## What pyjab does

pyjab automates **Java desktop applications on Windows** — Swing, AWT and
JavaFX — through [Java Access Bridge](https://docs.oracle.com/en/java/javase/21/access/toc.htm),
the accessibility API the JDK exposes on Windows.

Java Access Bridge is the same interface screen readers such as
[NVDA](https://github.com/nvaccess/nvda) use. That is why pyjab can drive an
application the way a real user would, and why it works on applications that
offer no automation API at all: if a screen reader can read it, pyjab can
usually drive it.

## How pyjab sees an application

```
your script
    │  find_element_by_name("Login") / click() / send_text()
    ▼
pyjab
    │  ctypes
    ▼
WindowsAccessBridge-64.dll        (ships with the JDK)
    │  COM
    ▼
the target JVM
    │
    ▼
the application's accessibility tree
```

pyjab loads the bridge DLL into the Python process and calls the Java Access
Bridge C API. It never touches, restarts or injects into the target
application — it only asks the JVM what its controls are.

That is the property that makes pyjab usable against production software:
dependency JARs, launch parameters and classpaths stay exactly as they are.

## Where it sits among the alternatives

| Approach | Example | Java semantics | Needs to change the target app | Platform |
|---|---|---|---|---|
| Screen scraping / vision | screenshot + model | weakest (guesses coordinates) | no | any |
| Generic Windows UI Automation | FlaUI, WinAppDriver, UIA-based MCP servers | partial — Java goes through JAB → MSAA → UIA, and table/text/selection detail is lost | no | Windows |
| **Java Access Bridge (pyjab)** | **pyjab** | **deep — the JVM's own roles, states, text, tables and selections** | **no** | Windows |
| Java agent injection | in-process agents | deepest | **yes — launch parameters must change** | any |

pyjab's position is the third row: near-injection depth without having to change
how the application starts.

The second row's limitation is measured rather than assumed. On a JDK 17 Swing
application, through the same `UIAutomationCore` API that FlaUI and WinAppDriver use:

| | elements | named | depth |
|---|---|---|---|
| UIA, the whole desktop | 147 | 99 | — |
| UIA, the Java window | 6 | 5 | 3 |
| pyjab, the same window | 601 | 513 | 12 |

The first row is the control, and it is the point: the same UIA client enumerated **147
elements across the desktop** and **finished rather than truncating**, so the six it
reports for the Java window are about Java rather than about the client. Those six are
the title bar, the menu bar, one menu item and three buttons — the window's own frame.
The table, the cells' text, the tree and all 35 buttons are not there, and neither is
anything else in the content pane.

The bridge is working: a Swing menu bar is drawn by Java, so the `MenuBarControl` in
those six can only have arrived through the Java accessibility path. It surfaces very
little of the tree, which is a different problem from surfacing none of it.

One measurement, one machine, one application. It is evidence for the row above and not
a general law; the application was pyjab's own test app, and "large table" for that app
is a twenty-cell table rather than a real one.

## Is it for you?

**Probably yes if you:**

* need to automate a Java desktop client that has no API — a back-office tool,
  an internal Swing application, a legacy fat client;
* cannot change how that application is launched;
* want an API shaped like the web-automation one you already know.

**Probably not if you:**

* need Linux or macOS — pyjab is Windows only, because Java Access Bridge is;
* need to automate a browser. For Java applets or Java embedded in a browser or
  Electron shell, see [6. Troubleshooting](6-Troubleshooting.md);
* need to automate an application whose interface is drawn onto a `Canvas` —
  there is nothing in the accessibility tree to find;
* want a completely synchronous, zero-setup experience. Java Access Bridge has
  to be enabled (pyjab does this), and the target application must be running.

## Requirements

| | |
|---|---|
| Operating system | Windows |
| Python | 3.8 or newer |
| JDK | any, 8 through 21+ are tested in CI |
| Target application | must expose accessibility through Java Access Bridge |

If the target application was built with an unusual or stripped-down JRE, or it
runs headless, nothing will be exposed and pyjab cannot help. Access Bridge
Explorer is the quickest way to check — see
[6. Troubleshooting](6-Troubleshooting.md).

## Licence

pyjab is licensed under **MIT** — you can use it in commercial and closed-source
software, and the only obligation is to carry the copyright notice and the licence
text with any copy or substantial portion of it.

Versions up to and including 1.5.0 were GPLv2, because the project then contained
code derived from NVDA, which is GPLv2. **Those releases remain GPLv2**, since a
licence cannot be withdrawn from a version that has already been distributed. The
derived code has since been written again from the behaviour it implements, and
from 1.6.0 pyjab is MIT.

## Next

* [2. Getting Started](2-Getting-Started.md) — install it and run something
* [3. pyjab](3-pyjab.md) — the API guide
