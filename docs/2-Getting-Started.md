# Getting Started

If you are new to pyjab, this page takes you from nothing to a working script.

## 1. Check that your Python is suitable

pyjab needs **Python 3.8 or newer on Windows**. It imports `pywin32`, so it
cannot run anywhere else.

```console
> python --version
Python 3.12.4
```

## 2. Install a JDK

pyjab needs the Java Access Bridge DLL, which ships with the JDK (or a
standalone JAB package). Any JDK works; CI tests against 8, 11, 17 and 21.

Install one and make sure `JAVA_HOME` points at it:

```console
> echo %JAVA_HOME%
C:\Program Files\Eclipse Adoptium\jdk-21.0.4.7-hotspot
```

`JAVA_HOME` is the recommended setup. If you would rather not set it, you can
point pyjab directly at the DLL instead — see
[Where the DLL lives](#where-the-dll-lives).

## 3. Install pyjab

```console
> pip install pyjab
```

## 4. Enable Java Access Bridge

Java Access Bridge has to be enabled for the user account that runs the
automation. **pyjab does this for you**: on first use it writes
`%USERPROFILE%\.accessibility.properties` if that file is missing or does not
already enable the bridge.

If you prefer to do it by hand, enable it from the Java Control Panel
(**Java** → **Accessibility** → *Assistive Technology*), or create the file
yourself:

```properties
assistive_technologies=com.sun.accessibility.AccessBridge
screen_magnifier_present=true
```

## 5. Start the application you want to automate

pyjab binds to an application that is **already running**, by window title. It
can launch one for you as well, but starting it yourself is simpler and more
predictable.

Note the exact window title. It is matched with `fnmatch`, so wildcards are
allowed, but it has to match.

## 6. Write your first script

```python
from pyjab.common.by import By
from pyjab.jabdriver import JABDriver

# Bind by window title.
driver = JABDriver(title="My Application")

# Find a control by its accessible name, and click it.
driver.find_element_by_name("Login").click()

# Wait for something to appear (up to 30 seconds).
dashboard = driver.wait_until_element_exist(By.NAME, "Dashboard", timeout=30)

# Read something back.
print(dashboard.name, dashboard.role, dashboard.states)
```

> **There is no `quit()` method.** `JABDriver` is a context manager, and leaving
> the `with` block terminates the bound Java process. Without `with`, the
> application keeps running; that is often what you want.

The tidier version:

```python
from pyjab.jabdriver import JABDriver

with JABDriver(title="My Application") as driver:
    driver.find_element_by_name("Login").click()
```

Letting pyjab launch the application instead:

```python
# A .jnlp is launched through `javaws`; anything else is executed directly.
with JABDriver(file_path=r"C:\apps\client.exe",
               title="My Application") as driver:
    driver.find_element_by_name("Login").click()
```

Beware: `file_path` waits for the launched process to exit before
`JABDriver(...)` returns. Starting the application yourself and binding by title
avoids that.

## Where the DLL lives

This changed between JDK releases, and is the single most common setup problem:

| JDK version | DLL location |
|---|---|
| JDK 8, 9, 10 | `%JAVA_HOME%\jre\bin\WindowsAccessBridge-64.dll` |
| JDK 11 and newer | `%JAVA_HOME%\bin\WindowsAccessBridge-64.dll` — the bundled `jre` directory was removed in JDK 11 |
| Standalone JAB | `%JAB_HOME%\WindowsAccessBridge-64.dll` |

**You normally do not need to do anything about this.** pyjab searches, in order:

1. the `bridge_dll` argument, if you passed one;
2. `%JAVA_HOME%\bin`, then `%JAVA_HOME%\jre\bin`, then `%JAVA_HOME%`;
3. `%JDK_HOME%`, `%JRE_HOME%`, `%JAB_HOME%`;
4. the usual vendor install locations — Adoptium, Corretto, Zulu, Microsoft,
   IntelliJ-downloaded JDKs, scoop;
5. a bounded recursive search under your JDK directories.

If none of that finds it, the error message lists every directory probed, flags
a 32/64-bit mismatch explicitly, and gives you three ways to fix it. To point
pyjab at a specific file:

```python
JABDriver(title="My Application",
          bridge_dll=r"C:\Program Files\Java\jdk-21\bin\WindowsAccessBridge-64.dll")
```

## Next steps

* [3. pyjab](3-pyjab.md) — finding locators, working with elements, tables
* [6. Troubleshooting](6-Troubleshooting.md) — when something does not work
