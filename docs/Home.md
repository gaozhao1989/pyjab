# pyjab

Python implementation for Java application UI automation with
[Java Access Bridge](https://docs.oracle.com/en/java/javase/21/access/toc.htm).

pyjab drives **Java desktop applications** (Swing / AWT / JavaFX) on Windows with
an API shaped like the web-automation one you already know. It reads the
application's accessibility tree through Java
Access Bridge, so it can find controls, read their text, fill forms, click
buttons and read tables **without the target application exposing any API of its
own**.

## Where to start

| Page | What it covers |
|---|---|
| [1. Overview](1-Overview.md) | What pyjab is, and whether it fits your problem |
| [2. Getting Started](2-Getting-Started.md) | Installation, prerequisites, your first script |
| [3. pyjab](3-pyjab.md) | The API guide: locators, elements, actions, tables |
| [4. Support Packages](4-Support-Packages.md) | What pyjab depends on |
| [5. About this documentation](5-About-this-documentation.md) | How these pages are maintained |
| [6. Troubleshooting](6-Troubleshooting.md) | The problems people actually hit |
| [7. Changelog](7-Changelog.md) | What changed in each release |

## At a glance

```python
from pyjab.common.by import By
from pyjab.jabdriver import JABDriver

with JABDriver(title="My Application") as driver:
    driver.find_element_by_name("Login").click()
    dashboard = driver.wait_until_element_exist(By.NAME, "Dashboard", timeout=30)
    print(dashboard.name, dashboard.role)
```

* **Platform:** Windows only.
* **Requires:** a JDK (or standalone Java Access Bridge), and Java Access Bridge
  enabled for the target application. pyjab enables it for you on first use.
* **Does not require:** any change to the target application. pyjab never
  restarts it, injects into it, or needs its source.
* **Licence:** MIT. See [1. Overview](1-Overview.md) if you plan to ship a product
  that bundles pyjab.

## Project

* Source, issues and releases: <https://github.com/gaozhao1989/pyjab>
* Package: <https://pypi.org/project/pyjab/>
