pyjab
=====

Python implementation for Java application UI automation with `Java Access Bridge`_.

``pyjab`` drives **Java desktop applications** (Swing / AWT / JavaFX) on Windows.
It talks to the `Java Access Bridge`_ API to read the accessibility tree of a
running Java application, so you can find elements, read their text, fill forms,
click buttons and read tables -- without the target application exposing any API
of its own.

The locator and element API is deliberately shaped like the web-automation API
most people already know, so that there is nothing new to learn.

* **Platform:** Windows only.
* **Requires:** a JDK (or a standalone Java Access Bridge) and Java Access Bridge
  enabled in the target application.
* **Locators:** familiar ``find_element_by_*`` locators plus an XPath-like syntax.
* **License:** MIT -- see `License and commercial use`_ below.

.. contents::
   :local:
   :depth: 2

How it works
------------

``pyjab`` loads ``WindowsAccessBridge-<bitness>.dll`` into the Python process
and calls the Java Access Bridge C API through ``ctypes``.  Every ``JABElement``
you get back is a thin wrapper around one node of the target application's
accessibility tree.

This means:

* it never needs to touch, modify or restart the target application;
* it is *not* screen scraping or image matching -- it reads real accessibility
  metadata (roles, states, text, tables, selections);
* it only sees what the application exposes through Java Access Bridge.

pyjab does not bundle or redistribute any part of the JDK. It loads the Java
Access Bridge DLL from the JDK you already have installed, and nothing else.

Installation
------------

.. code-block:: console

   $ pip install pyjab

Prerequisites
-------------

1. **Windows.**  pyjab imports ``pywin32`` and loads a Windows DLL.
2. **A JDK, JRE or standalone Java Access Bridge** on the machine running the
   automation.  The DLL ships with the JDK.
3. **Java Access Bridge enabled** for the user running the automation.  pyjab
   does this for you: on first use it writes
   ``%USERPROFILE%\.accessibility.properties`` if the file is missing or does not
   already enable the bridge.

Where the DLL lives depends on your JDK version:

===================  ==================================================================
JDK version          DLL location
===================  ==================================================================
JDK 8, 9, 10         ``%JAVA_HOME%\jre\bin\WindowsAccessBridge-64.dll``
JDK 11 and newer     ``%JAVA_HOME%\bin\WindowsAccessBridge-64.dll``
                     (the bundled ``jre`` directory no longer exists)
Standalone JAB       ``%JAB_HOME%\WindowsAccessBridge-64.dll``
===================  ==================================================================

**You normally do not need to configure anything.**  pyjab searches
``%JAVA_HOME%\bin``, ``%JAVA_HOME%\jre\bin``, ``%JDK_HOME%``, ``%JRE_HOME%``,
``%JAB_HOME%``, the common vendor install locations (Adoptium, Corretto, Zulu,
Microsoft, IntelliJ-downloaded JDKs, scoop) and finally does a bounded recursive
search under your JDK directories.

If discovery fails, the error message lists everything it probed and how to fix
it.  You can also point pyjab at a specific file:

.. code-block:: python

   JABDriver(title="My Application",
             bridge_dll=r"C:\Program Files\Java\jdk-21\bin\WindowsAccessBridge-64.dll")

Quickstart
----------

**Step 1 -- start the Java application you want to automate**, then find its
window title.  The title must match exactly (it is matched with ``fnmatch``, so
wildcards are allowed).

**Step 2 -- write your first script:**

.. code-block:: python

   from pyjab.common.by import By
   from pyjab.jabdriver import JABDriver

   # Bind to an already-running Java application by window title.
   driver = JABDriver(title="My Application")

   # Find a control by its accessible name and click it.
   driver.find_element_by_name("Login").click()

   # Wait for something to appear.
   dashboard = driver.wait_until_element_exist(By.NAME, "Dashboard", timeout=30)

   # Read a value.
   print(dashboard.name, dashboard.role, dashboard.states)

Using the context manager closes the driver and terminates the bound Java
process when the block exits:

.. code-block:: python

   with JABDriver(title="My Application") as driver:
       driver.find_element_by_name("Login").click()

To let pyjab launch the application for you, pass ``file_path``:

.. code-block:: python

   # A .jnlp is launched through `javaws`; anything else is executed directly.
   with JABDriver(file_path=r"C:\jnlps\test.jnlp",
                  title="My Application") as driver:
       driver.find_element_by_name("Login").click()

Finding locators
----------------

This is the part people get stuck on, so it is worth reading carefully.

You write locators for the **accessible name, role, description or state** of a
control -- the same information a screen reader would announce.  To see it,
install `Access Bridge Explorer`_ (Windows) and expand the accessibility tree of
your application.  Each node shows exactly the fields pyjab exposes:
``name``, ``description``, ``role``, ``states``, ``indexInParent``, bounds and so
on.

Common patterns:

.. code-block:: python

   # By accessible name (the label a screen reader would read).
   driver.find_element_by_name("Submit")

   # By role, when the control has no useful name.
   driver.find_element_by_role("push button")

   # By role and state, when several controls share a role.
   driver.find_element(by=By.STATES, value="enabled,focusable,visible,showing")

   # By index among siblings, when the control has neither name nor useful role.
   driver.find_element_by_index_in_parent(3)

   # XPath-like traversal, for complex hierarchies.
   driver.find_element_by_xpath("//internal frame[@name='FRM-999']")
   driver.find_element_by_xpath("//push button[@name=contains('OK')]")

   # All matches, not just the first one.
   buttons = driver.find_elements_by_role("push button")

Available ``By`` strategies: ``NAME``, ``DESCRIPTION``, ``ROLE``, ``STATES``,
``OBJECT_DEPTH``, ``CHILDREN_COUNT``, ``INDEX_IN_PARENT``, ``XPATH``.

.. tip::

   If a control has no accessible name, try ``find_elements_by_role`` first and
   inspect what comes back -- often a sibling or parent carries the label you
   are looking for.

Working with elements
---------------------

.. code-block:: python

   element = driver.find_element_by_name("Username")

   # Read properties.
   element.name          # accessible name
   element.role          # e.g. "push button", "text", "table"
   element.states        # e.g. "enabled,focusable,visible,showing"
   element.bounds        # {'x': .., 'y': .., 'width': .., 'height': ..}
   element.text          # text content, for accessible-text elements
   element.table         # row/column info, for table elements
   element.is_enabled    # also: is_visible, is_showing, is_checked,
                         #       is_selected, is_editable

   # Interact.
   element.click()
   element.send_text("hello")
   element.clear()
   element.select("Option A")     # combo boxes, lists, tabs
   element.scroll(to_bottom=True)
   element.expand()

   # Screenshots.
   element.get_screenshot_as_file("./element.png")
   driver.get_screenshot_as_file("./window.png")

The ``simulate`` parameter
--------------------------

Most interaction methods accept ``simulate=``.  It is worth understanding,
because the two modes have genuinely different trade-offs:

``simulate=False`` (default)
   pyjab drives the control through the Java Access Bridge accessibility action
   API.  This is more reliable for controls whose bounds are unknown or invalid
   (see the ``-1`` bounds case in the troubleshooting section) and it does not
   need the window to be in the foreground.  It is the safer default.

``simulate=True``
   pyjab moves the real mouse cursor to the control's centre and clicks.  Use
   this when the accessibility action does nothing -- for example some custom or
   third-party components.  **It brings the target window to the foreground**,
   which is disruptive if you need the machine for anything else, and it fails
   in non-interactive sessions such as a CI agent running as a service.

Rule of thumb: start with the default, and only reach for ``simulate=True`` when
the accessibility action is ignored.

Limitations
-----------

pyjab can only see what Java Access Bridge exposes.  The following are **not**
supported, and no amount of client-side work will change that:

* **Canvas-drawn UIs.**  If a component paints its widgets itself onto a
  ``Canvas``, there is nothing in the accessibility tree to find.  Access Bridge
  Explorer will show the canvas with no children.
* **Java applets or Java embedded in a browser / Electron shell.**  These
  typically run in a separate process that does not expose the accessibility
  bridge to the desktop.  Access Bridge Explorer cannot see them either, which is
  the quickest way to confirm it.
* **Anything not exposed as accessible.**  Some custom components simply do not
  implement the accessibility interfaces.
* **Off-screen table rows.**  Reading cells that are scrolled out of view is
  unreliable and can destabilise the target application; scroll the table into
  view first.

``pyjab-inspect`` shows what is actually in the window, and needs nothing else
installed: ``pyjab-inspect tree "<window title>"`` prints every element's role,
name, index and child count.  If Access Bridge Explorer cannot see it either,
pyjab cannot see it -- see `Troubleshooting`_.

Troubleshooting
---------------

``FileNotFoundError: Java Access Bridge DLL ... could not be located``
   The DLL was not found.  The message lists every directory that was probed and
   every environment variable it read.  The three usual fixes:

   1. set ``JAVA_HOME`` to your JDK installation directory;
   2. set ``JAB_HOME`` to the directory containing the DLL;
   3. pass ``bridge_dll=r"...\WindowsAccessBridge-64.dll"`` explicitly.

   Also check for a bitness mismatch: a 64-bit Python cannot load the 32-bit
   DLL.  The message calls this out explicitly when it happens.

``ModuleNotFoundError: No module named 'win32process'``
   Not on Windows.  pyjab is Windows only.

``pip install pyjab`` resolves dependencies very slowly or reports conflicts
   You are on an old pyjab.  Versions up to 1.1.7 declared both ``pypiwin32`` and
   ``pywin32``, which conflict.  Upgrade to 1.2.0 or later.

``JABException: JABElement with locator 'name' 'X' does not found``
   The locator did not match.  Common causes: the window title bound to the wrong
   window; the dialog is modal and needs the pump to run (pyjab handles this for
   most cases); or the control's accessible name differs from its visible label.
   ``pyjab-inspect find "<title>" "<locator>"`` reports which step of the locator
   stopped matching, and ``pyjab-inspect tree "<title>"`` shows the real names.

Elements report ``bounds = {'x': -1, 'y': -1, 'width': -1, 'height': -1}``
   The application does not report geometry for this control -- common for table
   cells.  ``simulate=True`` cannot work here, because there is no coordinate to
   click.  Use the accessibility action API (the default ``simulate=False``), or
   the table-specific helpers.

The target application becomes slow or unresponsive after a long run
   Known issue with long-running sessions.  Workarounds: reuse a single
   ``JABDriver`` instead of creating one per test, and call
   ``release_jabelement()`` on elements you are done with.

Development
-----------

.. code-block:: console

   $ pip install -e ".[dev]"
   $ pytest                       # portable suite, runs on any OS

The GUI tests need Windows, a real JDK, real Swing applications and an
interactive desktop session.  They are opt-in:

.. code-block:: console

   $ set PYJAB_RUN_GUI_TESTS=1    # Windows
   $ pytest

``tests/conftest.py`` documents which fixtures exist and what they need.

Related projects
----------------

* `Access Bridge Explorer`_ -- indispensable for inspecting the accessibility
  tree.  Install this first.
* `NVDA`_ -- the screen reader whose Java Access Bridge usage inspired parts of
  pyjab.

Support
-------

* **Bug reports and feature requests:** please open an issue on `GitHub`_.
  Include your JDK version, Python version and the window title you bound to.
* **Commercial support, integration help or custom development:** contact
  `gaozhao89@qq.com`_.

License and commercial use
--------------------------

Oracle, Java and Java Access Bridge are trademarks or registered trademarks of
Oracle Corporation. pyjab is an independent project and is not affiliated with,
endorsed by, or sponsored by Oracle.

pyjab is licensed under `MIT`_.  You may use it in commercial and closed-source
software.  The only obligation is that the copyright notice and the licence text
travel with any copy or substantial portion of it.

Versions up to and including 1.5.0 were released under `GPLv2`_, because the
project then contained code derived from NVDA, which is GPLv2.  **Those releases
remain GPLv2** -- a licence cannot be withdrawn from a version that has already
been distributed -- so pinning one of them means the terms that came with it.
The derived code has since been written again from the behaviour it implements
rather than from NVDA's text, and from 1.6.0 pyjab is MIT.

If an older version under different terms matters to you, please get in touch --
see `Support`_.

Contributing
------------

See `CONTRIBUTING.rst <CONTRIBUTING.rst>`_.  Bug reports with a minimal
reproduction are the most valuable contribution.

© 2021-2026 Gary Gao and contributors.  See `CONTRIBUTORS.txt <CONTRIBUTORS.txt>`_.


.. External references:
.. _Java Access Bridge: https://docs.oracle.com/en/java/javase/21/access/toc.htm
.. _NVDA: https://github.com/nvaccess/nvda
.. _PyPI: https://pypi.org/project/pyjab/
.. _GitHub: https://github.com/gaozhao1989/pyjab
.. _Access Bridge Explorer: https://github.com/google/access-bridge-explorer
.. _MIT: https://opensource.org/license/mit
.. _GPLv2: https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html
.. _gaozhao89@qq.com: mailto:gaozhao89@qq.com
