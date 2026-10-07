Contributing
============

Bug reports, documentation fixes and pull requests are all welcome.

Reporting a bug
---------------

The most useful reports include:

* the pyjab version (``python -c "import pyjab; print(pyjab.__version__)"``);
* your Python version and the JDK version the target application runs on;
* the exact window title you bound to;
* what you expected, what happened, and the full traceback;
* whether the control is visible in `Access Bridge Explorer`_.

If pyjab cannot find a control, check `Access Bridge Explorer`_ first: if it
cannot see the control either, the problem is in the application's
accessibility support, not in pyjab.

.. _Access Bridge Explorer: https://github.com/google/access-bridge-explorer

Development setup
-----------------

.. code-block:: console

   $ git clone https://github.com/gaozhao1989/pyjab.git
   $ cd pyjab
   $ python -m venv .venv
   $ .venv\Scripts\activate
   $ pip install -e ".[dev]"

Running the tests
-----------------

There are two suites, and it matters which one you run.

Portable suite -- runs on any OS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: console

   $ pytest

A couple of seconds. This covers the parts of pyjab that have no Windows
dependency: Java Access Bridge DLL discovery, and the message pump
(``pywin32`` is stubbed out so it can be tested anywhere). The GUI modules are
not collected unless you opt in.

This is what CI runs on Linux, macOS and Windows, and it is what you should run
before opening a pull request.

GUI suite -- Windows only
~~~~~~~~~~~~~~~~~~~~~~~~~

These drive real Java Swing applications, so they need Windows, a JDK, an
interactive desktop session, and network access to download the Oracle demo
applications. They are opt-in:

.. code-block:: console

   $ set PYJAB_RUN_GUI_TESTS=1
   $ pytest -v

Every module in this suite is marked ``gui``, so once opted in you can narrow
the run with ``-m "not gui"`` -- though with the opt-in above that is rarely
useful. Note that the authoritative switch is the module list in
``tests/conftest.py``; the marker only lets you deselect.

Individual modules, and what each one covers:

.. list-table::
   :header-rows: 1

   * - Command
     - What it checks
   * - ``pytest tests/test_components.py -v``
     - The main API surface against Oracle's Swing demos: buttons, check boxes,
       combo boxes, dialogs, tables, trees and the rest.
   * - ``pytest tests/test_message_pump_gui.py -v``
     - The 1.3.0 message pump rewrite. The headline test is
       ``test_new_window_is_found_after_a_plain_click``: a dialog opened with
       the default ``simulate=False`` click must be discoverable. Before 1.3.0
       this needed ``simulate=True``, and even then it was unreliable.
       ``test_wait_until_element_exist_backs_off`` compares process CPU time
       against wall-clock time to prove the wait sleeps rather than spins.
   * - ``pytest tests/test_bridge_dll.py -v``
     - Binding with explicit 32-bit and 64-bit ``bridge_dll`` paths.
   * - ``pytest tests/test_bug_fix.py -v``
     - Regression tests for previously fixed bugs.

``tests/test_message_pump_gui.py`` is the suite to run if you want to check the
1.3.0 pump behaviour yourself.

Verifying the pump on a specific machine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you do not want to run pytest at all, there is a standalone script that
reproduces `issue #56`_'s scenario using the Java Control Panel, and prints
``PASSED`` or ``FAILED``:

.. code-block:: console

   $ python tools/verify_message_pump.py

.. _issue #56: https://github.com/gaozhao1989/pyjab/issues/56

What CI runs
------------

``.github/workflows/ci.yml`` runs four jobs on every push:

* the portable suite on Ubuntu, Windows and macOS, on Python 3.9 and 3.12;
* DLL discovery on Windows against real Temurin JDK 8, 11, 17 and 21, asserting
  the DLL is both found **and loaded**;
* a Windows import smoke test, which also exercises the message pump against the
  real ``pythoncom``;
* a distribution build with metadata checks, including a guard that no stale
  copy of the package was packaged.

CI has no interactive desktop session, so the GUI suite does not run there.

Documentation
-------------

The user-facing documentation lives in ``docs/`` and is published to the
`wiki`_. Edit the files in ``docs/`` -- not the wiki -- and publish with:

.. code-block:: console

   $ python tools/sync_wiki.py --dry-run
   $ python tools/sync_wiki.py

See ``docs/README.md`` for the layout.

.. _wiki: https://github.com/gaozhao1989/pyjab/wiki

Code style
----------

Match the surrounding code. Two things worth calling out:

* **Type hints on new public functions.** ``pyjab`` supports Python 3.8, so use
  ``from __future__ import annotations`` if you want builtin generics in
  annotations.
* **Say why, not what, in comments.** The existing comments explain the
  reasoning behind non-obvious choices; that is the standard to aim for.

Releases
--------

Releases are cut from ``master``. The process is:

1. bump ``__version__`` in ``pyjab/__init__.py``;
2. add an entry to ``CHANGELOG.rst``;
3. tag and push:

   .. code-block:: console

      $ git tag -a v1.3.0 -m "pyjab 1.3.0"
      $ git push origin v1.3.0

``.github/workflows/release.yml`` then verifies that the tag matches
``__version__``, builds, publishes to PyPI via Trusted Publishing, and creates a
GitHub release.

.. _GitHub: https://github.com/gaozhao1989/pyjab
