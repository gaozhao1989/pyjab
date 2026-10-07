CHANGELOG
=========

All notable changes to pyjab are documented here.
This project adheres to `Semantic Versioning`_ and `Keep a Changelog`_.

.. _Semantic Versioning: https://semver.org/
.. _Keep a Changelog: https://keepachangelog.com/

1.3.0 (unreleased)
------------------

Rewrites the Windows message pump.

pyjab drives Java Access Bridge, which is COM based.  Accessibility events --
including the ones that announce a window or dialog opened *after* the first
one -- are delivered through COM to the thread that called ``Windows_run()``.
That thread has to service its message queue, or pyjab never learns that the
window exists.

The old implementation was a generator advanced one step at a time by
``ActorScheduler``, and it was only driven while waiting for the very first
window.  Once element lookups began, nothing was serviced at all, and a dialog
that opened during a wait was invisible.  This release replaces it with a
plain, non-blocking call that is made on every lookup and on every poll.

Fixed
~~~~~

* **The message queue was never serviced once element lookups started.**  A
  window or dialog that opened after the first window was bound could not be
  seen.  The queue is now pumped at the start of every element lookup and on
  every iteration of both wait loops.
* **Every second pump invocation did nothing.**  Each call built a fresh pump
  generator that was discarded immediately; when it was garbage collected its
  ``finally`` clause set the shared stop event, so the next call saw a
  signalled event and returned without pumping anything.
* **The pump blocked for up to 200ms per invocation**, including while waiting
  for the first window and while constructing every ``JABDriver``.
* **``wait_until_element_exist()`` was a busy loop with no sleep at all.**
  It re-walked the entire accessibility tree as fast as the CPU allowed, which
  is the behaviour reported in issues #29 and #33.  It now backs off between
  attempts, pumps the queue each iteration, and accepts a ``poll_interval``.
* Two kernel event handles were created once per process and never closed.
  They are no longer created at all.

Changed
~~~~~~~

* ``Win32Utils.setup_msg_pump()`` (a generator) is replaced by
  ``Win32Utils.pump_messages()``, a non-blocking call that returns ``True`` if
  a ``WM_QUIT`` was seen.
* ``pyjab.common.actorscheduler.ActorScheduler`` is deprecated and no longer
  used.  It is kept only so that existing imports keep working.
* ``JABDriver.wait_until_element_exist()`` gained a ``poll_interval`` argument.
* New settings in ``pyjab.config``: ``WINDOW_POLL_INTERVAL`` (0.05s) and
  ``ELEMENT_POLL_INTERVAL`` (0.1s).

Added
~~~~~

* ``tests/test_message_pump.py`` -- covers the pump itself, guards against the
  generator pump and ``ActorScheduler`` being reintroduced, and asserts that
  every lookup entry point pumps the queue before touching the tree.  It runs
  on Linux and macOS by stubbing pywin32, rather than being skipped.

Note on verification
~~~~~~~~~~~~~~~~~~~~

CI has no interactive desktop session, so the pump cannot be exercised against
a live Java application.  The tests above cover the logic and the wiring; the
end-to-end behaviour of a window opening mid-script still needs a manual check
on Windows.  See ``docs/TRIAGE.md`` section 3.9 for the analysis behind this
change.

1.2.1 (2026-10-07)
------------------

Released so that ``get_focused_element()``, contributed by `Chih-Yu (y252328)`_
and merged to ``master`` in November 2022, finally reaches users.  It was
present in the repository for three and a half years but never made it into a
published release, because ``master`` was never released again after 1.1.7.

.. _Chih-Yu (y252328): https://github.com/y252328

Added
~~~~~

* ``JABDriver.get_focused_element()`` -- returns the currently focused
  ``JABElement`` in the bound window, or ``None`` when nothing is focused.

  .. code-block:: python

     element = driver.get_focused_element()
     if element is not None:
         print(element.name, element.role)

Fixed
~~~~~

* ``get_focused_element()`` passed the raw ``c_long`` vmID to ``JABElement``
  instead of ``vmid.value``, which is what every other code path in pyjab uses
  (``_get_accessible_context_from_hwnd`` returns ``vmid.value``).  It also now
  uses a plain falsy check on the ``BOOL`` result rather than ``result == 0``.

1.2.0 (2026-10-07)
------------------

The first release since 1.1.7 (2022-05-23).  Focused on making the package
installable and usable on modern JDKs, and on restoring a working feedback loop
(CI + tests).

**Upgrading from 1.1.x:** if you were passing an explicit DLL path or setting
``JAB_HOME`` as a workaround for the "WindowsAccessBridge dll not found" error,
you should no longer need to.  Those workarounds keep working.

Fixed
~~~~~

* **Java Access Bridge DLL discovery on JDK 11 and newer.**  pyjab only ever
  probed ``%JAVA_HOME%\\jre\\bin``, but JDK 11 removed the bundled ``jre``
  directory and moved the DLL to ``%JAVA_HOME%\\bin``.  Every JDK 11+ user hit
  ``FileNotFoundError: WindowsAccessBridge dll not found`` unless they passed
  ``bridge_dll=`` explicitly or set ``JAB_HOME``.  Discovery now walks an
  ordered list of candidates:

  1. the explicit ``bridge_dll`` argument
  2. ``%JAVA_HOME%\\bin`` (JDK 11+), ``%JAVA_HOME%\\jre\\bin`` (JDK 8-10),
     ``%JAVA_HOME%``
  3. ``%JDK_HOME%``, ``%JRE_HOME%`` and ``%JAB_HOME%`` equivalents
  4. common vendor install locations (Adoptium, Corretto, Zulu, Microsoft,
     IntelliJ-downloaded JDKs, scoop, ...)
  5. a bounded recursive search under the JDK/JRE home directories

* **Confusing dependency resolution failures.**  ``requirements.txt`` listed both
  ``pypiwin32>=223`` and ``pywin32>=302``.  ``pypiwin32`` is a deprecated shim
  that pins ``pywin32==223``, so ``pip install pyjab`` failed to resolve
  dependencies for *every* released version.  ``pypiwin32`` has been removed and
  ``pywin32`` now carries a ``sys_platform == "win32"`` marker so it is not even
  requested on other platforms.

* **``setup.py`` could not run on Python 3.12+.**  It imported
  ``distutils.sysconfig``, and ``distutils`` was removed from the standard
  library in Python 3.12.

* **Non-Windows users got an opaque failure.**  pyjab ships as a pure-python
  wheel, so pip installs it on Linux and macOS, where it then failed with
  ``ModuleNotFoundError: No module named 'win32process'``.  ``pyjab.jabdriver``
  and ``pyjab.jabelement`` now raise an ``ImportError`` that states the
  platform limitation up front.

Changed
~~~~~~~

* **Packaging moved to ``pyproject.toml``** (PEP 621).  ``setup.py`` and
  ``setup.cfg`` were removed: the former could not run on Python 3.12+, and the
  latter forced ``--universal`` wheels, which incorrectly advertised a
  Windows-only package as installable and runnable everywhere.

* **The failure message for a missing DLL is now actionable.**  It reports every
  environment variable consulted, every directory probed, whether a DLL of the
  *wrong bitness* was found, and three concrete ways to fix the problem.
  See ``pyjab.config.describe_bridge_dll_search()``.

* **``pyjab.common.service.Service`` gained ``find_bridge_dll()``**, which
  resolves the DLL path without loading it into the process.  Useful for
  diagnostics.

* ``pyjab.config`` no longer imports anything Windows specific, so the DLL
  search logic is unit testable on any platform.

Added
~~~~~

* **Continuous integration** for Windows, Linux and macOS.  The portable test
  suite runs everywhere; an import smoke test runs on Windows.
* **A test suite for DLL discovery** (``tests/test_bridge_dll_discovery.py``),
  covering JDK 8-10 and JDK 11+ layouts, bitness matching, quoting in
  environment variables, deduplication, the recursive fallback and the
  diagnostic output.
* ``pyproject.toml`` ``[project.optional-dependencies] dev`` for test tooling.

Developer notes
~~~~~~~~~~~~~~~

* The GUI tests need Windows, a real JDK, real Swing applications and an
  interactive desktop session.  They used to be collected unconditionally,
  which made ``pytest`` fail at import time on other platforms and triggered a
  25-file download from oracle.com even when no GUI test was selected.  They are
  now opt-in::

      # portable suite only (default)
      pytest

      # include the GUI suite (Windows only)
      set PYJAB_RUN_GUI_TESTS=1
      pytest

* ``build/``, ``dist/``, ``temp.py`` and ``pyjab.egg-info/`` were removed from
  the working tree and are now ignored.  ``build/lib/pyjab/`` contained a stale
  copy of the package that could be picked up by ``find_packages()`` and shipped
  in a distribution.


1.1.7 (2022-05-23)
------------------

Last release before a three year gap in maintenance.  Changes up to this point
are recorded in the git history.
