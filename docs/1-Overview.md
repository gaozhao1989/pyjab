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

pyjab is licensed under **GPLv2**.

GPLv2 is a copyleft licence: if you distribute software that links pyjab, that
software must also be distributed under GPLv2. Using pyjab for internal
automation that you never distribute does not trigger this, but shipping a
product that bundles pyjab does.

If that is a problem for your use case, please get in touch — relicensing is a
topic the maintainer is open to discussing.

## Next

* [2. Getting Started](2-Getting-Started.md) — install it and run something
* [3. pyjab](3-pyjab.md) — the API guide
