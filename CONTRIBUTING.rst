Contributing
============

Bug reports, documentation fixes and pull requests are all welcome.

Licence of your contribution
----------------------------

pyjab is MIT. It was GPLv2 until 1.6.0, and getting there took a written permission
from every contributor whose work was still in the code -- which is exactly the
situation this section exists to keep from happening again. So a patch is accepted
under two conditions.

**1. Sign off your commits.** Use ``git commit -s``, which appends a line to the
commit message:

.. code-block:: text

   Signed-off-by: Your Name <you@example.com>

That is the `Developer Certificate of Origin`_. Signing it says you wrote the
patch, or otherwise have the right to submit it, and that it may be distributed
under the project's licence. It states provenance only -- **you keep your
copyright.**

**2. Grant a relicensing right.** By signing off you also agree that the
maintainer may distribute your contribution under any OSI-approved licence,
including one other than the licence in force when you sent it.

The second condition is what keeps the first from being a trap. Without it, every
future licence change would need separate permission from every past contributor --
which is how pyjab spent four years on a licence it had inherited rather than
chosen, and could not leave without asking three people it had no other reason to
contact.

If your employer owns your work, check that you have their permission before
signing off. There is no CLA to sign and nothing to email.

CI checks this on every pull request, and you can check it yourself first:

.. code-block:: console

   $ python tools/check_dco.py --base origin/master

It fails on a commit with no sign-off, and on one whose sign-off names somebody
who is neither the author nor the committer -- a trailer naming nobody states
nothing. Merge commits and bots are skipped. If you have already committed
without ``-s``, ``git rebase --signoff <base>`` adds it to the whole branch.

.. _Developer Certificate of Origin: https://developercertificate.org/

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
dependency. ``pywin32`` is stubbed out by ``tests/_win32stubs.py``, which
installs a stand-in for each pywin32 module that is missing, so the logic in
``jabelement``, ``jabdriver`` and ``win32utils`` can be exercised anywhere. The
GUI modules are not collected unless you opt in.

This is what CI runs on Linux, macOS and Windows, and it is what you should run
before opening a pull request.

.. list-table::
   :header-rows: 1

   * - Module
     - What it covers
   * - ``tests/test_bridge_dll_discovery.py``
     - Locating ``WindowsAccessBridge-{32,64}.dll`` across the JDK 8 and JDK 11+
       layouts, bitness selection and the diagnostics when nothing is found.
   * - ``tests/test_message_pump.py``
     - The message pump: that it runs, that it runs on every lookup, and that the
       removed generator implementation does not come back.
   * - ``tests/test_xpath_parser.py``
     - The XPath subset: role and attribute parsing, and how a path is split.
   * - ``tests/test_element_logic.py``
     - Element logic that needs no live application: XPath traversal levels,
       states matching, the wait helpers, empty text, and visible children.
   * - ``tests/test_win32_helpers.py``
     - The virtual key table and window geometry.
   * - ``tests/test_jabdriver_launch.py``
     - Process teardown and how the launch command line is built.

GUI suite -- Windows only
~~~~~~~~~~~~~~~~~~~~~~~~~

These drive a real Java Swing application, so they need Windows, a JDK, and an
interactive desktop session. They are opt-in:

.. code-block:: console

   $ set PYJAB_RUN_GUI_TESTS=1
   $ pytest -v

The application is ``tests/java/PyjabTestApp.java``. It is part of the
repository and is compiled on demand by the ``test_app`` fixture, so there is
nothing to download and nothing to install beyond a JDK. ``javac`` and ``java``
are looked for in ``JAVA_HOME`` first and then on the ``PATH``.

If you have a JRE but no JDK, the suite fails with a message saying so rather
than with a bare ``FileNotFoundError``.

**Before running the suite, check that its locators still resolve.** This needs
only a JDK, works on any platform, and catches the failure that is otherwise
invisible until someone runs the suite on a Windows desktop:

.. code-block:: console

   $ python tools/verify_test_app.py

There is also a diagnosis for the coordinate problem tracked as #62, which
cannot be settled by reading the source because it depends on the DPI
awareness of two separate processes. It clicks a control whose state change
is observable, so it reports which coordinate space this display needs:

.. code-block:: console

   $ python tools/verify_dpi.py

It dumps the application's accessibility tree -- which is what Java Access
Bridge reads, and is a JVM-side API, so it reports the same thing everywhere --
and fails if any name or role the suite looks for is missing. To compile by hand
instead:

.. code-block:: console

   $ javac -Xlint:all -d tests/java/classes tests/java/PyjabTestApp.java

The compiled classes are ignored by git; CI compiles the same file with a real
JDK on Windows, which is the only automated check on it, because a CI runner has
no desktop session to run the suite in.

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
     - The main API surface against the local application: buttons, check boxes,
       combo boxes, dialogs, menus, tables, trees, sliders, spinners and the
       rest. Where an interaction has two paths -- the accessibility action and
       simulated input -- both are covered.
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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you do not want to run pytest at all, there is a standalone script that
reproduces `issue #56`_'s scenario using the Java Control Panel, and prints
``PASSED`` or ``FAILED``:

.. code-block:: console

   $ python tools/verify_message_pump.py

.. _issue #56: https://github.com/gaozhao1989/pyjab/issues/56

What CI runs
------------

``.github/workflows/ci.yml`` runs six jobs. Five run on every push:

* the portable suite on Ubuntu, Windows and macOS, on Python 3.9 and 3.12;
* DLL discovery on Windows against real Temurin JDK 8, 11, 17 and 21, asserting
  the DLL is both found **and loaded**;
* a Windows import smoke test, which also exercises the message pump against the
  real ``pythoncom``;
* a check that what the repository declares matches what it contains: that every
  runtime dependency is permissively licensed
  (``tools/check_dependency_licences.py``), that the licence pyjab declares is the
  one it ships (``tools/check_license_consistency.py``), and that every pyjab API
  the documentation names actually exists (``tools/check_documented_api.py``);
* a distribution build with metadata checks, including a guard that no stale
  copy of the package was packaged.

The sixth runs on pull requests only: **every commit must be signed off**
(``tools/check_dco.py``). It is not run on a push because the commits already on
``master`` predate the requirement. See `Licence of your contribution`_ above for
why the sign-off is asked for.

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
