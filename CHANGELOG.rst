CHANGELOG
=========

All notable changes to pyjab are documented here.
This project adheres to `Semantic Versioning`_ and `Keep a Changelog`_.

.. _Semantic Versioning: https://semver.org/
.. _Keep a Changelog: https://keepachangelog.com/

1.4.2 (2026-10-08)
------------------

A test-only release, like 1.4.1.  The wheel is functionally identical to 1.4.0;
what changed is the GUI suite and the application it drives.

The GUI suite had never been run against a real desktop until 1.4.1 reached one,
and five things were wrong.  Three were the application's, one the test's, one
the harness's.

* **The application named components with ``setName()``, which the accessibility
  layer ignores.**  A ``JSlider``, ``JComboBox``, ``JList``, ``JTextComponent``
  or ``JSpinner`` builds its accessible context in a class that does not read the
  component name, so a lookup by name either found nothing or found the label
  beside the control -- and reported the role ``label`` for what should have been
  a slider.  Names are now set through ``AccessibleContext.setAccessibleName()``
  as well.
* **Those labels carried the same text as the controls**, so a lookup by name
  matched the label first.  They read ``First slider:`` now, and the control
  stays ``First slider``.
* **Copying every component name into its accessible name flattened the tree.**
  ``JTree`` names its shared cell renderer ``Tree.cellRenderer``, so every row
  reported that instead of its own node text.  Renderers are skipped, and rows
  report ``Root`` / ``Child one`` / ``Child one leaf A`` again.
* **``test_multiple_key_press`` called a method that does not exist.**
  ``JABDriver`` has no ``_press_hold_release_key``; the key helpers live on
  ``Win32Utils``.  It had raised ``AttributeError`` since it was written.
* **``test_spinner`` asserted absolute values** after ``spin(option=...)``, which
  writes into the spinner's editor without the model adopting it.  It compares
  against the value it started from now.
* **``test_push_button`` was intermittent** because every launch bound to the
  same window title, so a JVM left behind by an earlier test could be matched
  instead of the new one.  Each launch gets its own title.

Added
~~~~~

* ``tools/verify_test_app.py`` checks that every name and role the GUI suite
  looks for actually exists in the application, by dumping its accessibility
  tree.  That is a JVM-side API, so it reports the same thing on every platform:
  the check needs only a JDK, takes about a second, and runs in CI on every push.
  It closes the gap that let all of the above reach a user -- the suite cannot
  run without a Windows desktop, so nothing else was looking.
* ``PyjabTestApp --dump-accessibility`` prints that tree, and is what the check
  uses.

1.4.1 (2026-10-08)
------------------

A test-only release.  The wheel is functionally identical to 1.4.0; what changed
is the GUI suite that ships inside the sdist.

* **The GUI test JVM is now started with a fixed locale**, and the colour
  chooser's page-tab assertions match on a substring rather than a whole name.
  Swing builds some component labels from resource bundles: a colour chooser's
  tabs read ``HSV`` / ``HSL`` / ``RGB`` in English but ``HSV(H)`` / ``HSL(L)`` /
  ``RGB(G)`` plus a localised ``Swatches`` under a Chinese locale.  Two tests
  therefore passed or failed depending on the language of the machine running
  them, which is not something anyone should have to debug.

Also included, from the 1.4.0 line, for anyone reading this as the first release
they install: element lookups walk the accessibility tree in the order the
locator implies, the path prunes the walk and the search backtracks, and the GUI
suite drives a Swing application that lives in the repository instead of
downloading Oracle's demo applets.

1.4.0 (2026-10-08)
------------------

Makes element lookups walk the accessibility tree in an order that follows the
locator, adds methods for walking one level at a time, and makes the GUI test
suite runnable without downloading anything.

The lookup change is the larger one: on a window with a few thousand nodes it
turns a path lookup from thousands of cross-process calls into tens.

Contributed by `shine-jayakumar`_ in #77.

Fixed
~~~~~

* **A lookup walked a node's whole subtree before looking at the node itself.**
  ``_generate_all_childs`` yields a node *after* recursing into it -- post-order
  -- so the search root's own first child was reached only once everything
  beneath it had been visited. A path six levels deep over a table with a few
  thousand cells therefore cost ~2000 ``getAccessibleContextInfo`` calls instead
  of a handful, which is where the 40 seconds in #33 went. Lookups now test a
  node before descending into it; measured on a synthetic tree, the same path
  costs 30 calls in a 28-node window and 30 calls in a 2008-node one.
* **The path did not prune the walk, and there was no backtracking.** Once a
  node matched its role and attributes, the remainder of the path had to fit
  underneath *that* node or the lookup raised -- even if a later candidate
  matched. The search now tries the rest of the path under each candidate and
  carries on when it does not fit.
* **A locator issued from a child element silently started at its parent.**
  ``_get_node_element`` substituted ``self.parent`` for any element that was not
  the window's top-level object (#54). An absolute locator now starts at the
  top-level object, as XPath's ``//`` means, and a locator beginning with ``.``
  is relative to the element it is issued from:

  .. code-block:: python

     # anywhere in the window
     button = pane.find_element_by_xpath("//push button")
     # this pane's own button, and only this one
     button = pane.find_element_by_xpath(".//push button")

Added
~~~~~

* ``JABElement.get_children()`` returns the *immediate* children of an element,
  optionally filtered by a ``By`` strategy and locator.  The existing
  ``find_elements_by_*`` methods search the whole descendant tree and are the
  only way to enumerate children today; this makes one level explicit.  It
  returns an empty list when the element has no children, unlike the
  ``find_elements_by_*`` family, which raises.
* ``JABElement.find_elements_by_name_pattern()`` and
  ``JABElement.find_element_by_name_pattern()`` match a name with a regular
  expression, optionally case-insensitively.  Useful where a name carries a
  changing suffix such as a file path or a counter.

The filtered-out children in ``get_children()`` are released with
``release_jabelement()``.  Java Access Bridge holds its own reference to every
object it returns, so a child that is dropped without being released
accumulates Java objects for the life of the process -- the pattern behind #43.

Note on ownership, for anyone extending the traversal: JAB returns a fresh
object reference from every call that hands one out, and each must be released
exactly once. A node that matches the first path segment is enumerated twice
when the rest of the path does not fit under it, so the search collects what it
created and releases the whole lot once it is done, rather than releasing as it
walks.

``find_elements_by_xpath`` still walks with the old level-based traversal, so it
does not benefit from the pruning yet. It is the next piece of this work.

Testing
~~~~~~~

* **The GUI suite no longer downloads anything.** It used to fetch 27 demo
  applets from ``docs.oracle.com`` and drive those, which made it depend on a
  third party staying online and on the exact widget names inside somebody
  else's demos. The application it drives is now in the repository, in
  ``tests/java/PyjabTestApp.java``, and the ``test_app`` fixture compiles it on
  demand with the JDK's ``javac`` (found in ``JAVA_HOME`` or on the ``PATH``).
* The suite no longer needs Java Web Start, and ``requests`` is no longer a
  development dependency.
* ``test_bridge_dll.py`` and ``test_bug_fix.py`` no longer drive the Java Control
  Panel at a hardcoded ``jdk1.8.0_311`` path, so they do not require a JDK 8
  install. They drive the same local application as everything else.
* CI compiles the application with ``-Xlint:all`` and fails on any warning, and
  checks that the sdist carries the Java sources rather than the compiled
  classes. A CI runner has no desktop session, so that is the only automated
  check on the application; running the suite itself still needs a Windows
  desktop.

.. _shine-jayakumar: https://github.com/shine-jayakumar

1.3.1 (2026-10-07)
------------------

Fixes twelve defects found by reading the source.  None of them had been
reported, and most are silent: they produce a wrong answer rather than an error.

Two are worth singling out.  An empty text field could not be read at all --
``text`` raised ``RuntimeError`` instead of returning ``""``, which also meant
``clear()``, whose whole job is to wait for that empty state, could never
succeed.  And the two wait helpers never re-read the value they were waiting on:
they compared a value the caller had already evaluated, so the result could not
change and the loop span until it timed out.

Fixed
~~~~~

* **``find_element_by_xpath`` mis-resolved repeated node names.**  The level of
  each node was decided with ``nodes.index(node)``, which returns 0 for every
  occurrence of a repeated name -- so ``//panel/panel`` looked up the second
  ``panel`` as a root-level node and degraded into a whole-tree search.  Now
  uses the node's position.
* **A ``/`` inside a quoted XPath value split the path.**  The path was split on
  every ``/`` before it was parsed, so ``//panel[@name='a/b']`` became two nodes
  and could never match.  Splitting is now quote-aware.
* **``find_element_by_xpath("/")`` returned ``None``.**  An empty node path
  produced silently no lookup, contradicting the declared return type.  It now
  raises ``XpathParserException``.
* **``find_element_by_states()`` could not match a string locator.**
  ``set("enabled")`` is a set of characters, so the documented ``str`` form
  never matched anything.  Comma-separated strings are now accepted.
* **The wait helpers did not wait.**  ``_wait_for_value_to_be`` and
  ``_wait_for_value_to_contain`` operated on an already-evaluated value, so they
  could never observe a change, never slept, and spun the CPU until they timed
  out.  They now take a callable and re-read it each poll.
* **Reading an empty text field raised.**  With ``charCount`` of 0 the end
  offset became -1, which Java Access Bridge rejects.  ``text`` now returns
  ``""``; an element without the Accessible Text interface still returns
  ``None``.
* **``_set_window_position`` computed a negative size.**  The width and height
  were derived from the *requested* position (``left - right``), which is
  negative for any real window, so ``MoveWindow`` was asked to make the window a
  negative number of pixels wide.  It now measures the existing edges.
* **Typing a ``+`` raised ``KeyError``.**  ``_send_keys`` expands ``+`` into
  ``("left_shift", "=")``, but ``=`` was missing from the virtual key table.
* **The right shift key was unreachable.**  The table held ``"right_shift "``
  with a trailing space, so it could never be looked up.
* **``doAccessibleActions`` discarded its failure index.**  A bare ``jint()``
  instance was passed where ``jint *failure`` is declared.  ctypes accepts that
  and writes through the instance's own address, so the value was thrown away.
  It is now passed with ``byref()`` and logged.
* **Visible children were indexed with the wrong count.**  The number came from
  ``getVisibleChildrenCount`` while the array came from ``getVisibleChildren``;
  the two calls disagreeing read past the real contents.  Both now come from the
  same call.
* **``JABDriver.__exit__`` raised ``TypeError`` when nothing was bound.**  If
  ``init_jab`` failed before resolving the window -- the usual case, since it is
  what happens when the window never appears -- ``os.kill(None, ...)`` replaced
  the real exception with a misleading one.
* **``open_application`` could not launch a path containing spaces.**  The path
  was joined into a shell string and run with ``shell=True``, so cmd.exe split
  it; ``C:\Program Files\...\javacpl.exe`` was never started.  It now passes an
  argv list.

Also replaced seven non-raw string literals passed to ``re.compile``.  They
emitted ``SyntaxWarning`` on Python 3.12+ and would become errors in future;
the compiled patterns are unchanged.

1.3.0 (2026-10-07)
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
* ``JABDriver.open_application()`` no longer waits for the launched process to
  exit.  ``file_path=`` is meant to start an application and then bind to its
  window, which is impossible if the constructor blocks until that application
  closes -- and with ``javaws`` it could block for as long as the user left the
  window open.  Regression from 1.2.0, which made the ``javaws`` branch work for
  the first time.

Added
~~~~~

* ``tests/test_message_pump.py`` -- covers the pump itself, guards against the
  generator pump and ``ActorScheduler`` being reintroduced, and asserts that
  every lookup entry point pumps the queue before touching the tree.  It runs
  on Linux and macOS by stubbing pywin32, rather than being skipped.
* ``tests/test_message_pump_gui.py`` -- the Windows end-to-end counterpart, part
  of the opt-in GUI suite.  ``test_new_window_is_found_after_a_plain_click``
  asserts that a dialog opened with the default ``simulate=False`` click is
  discoverable, which is the behaviour 1.3.0 set out to fix;
  ``test_wait_until_element_exist_backs_off`` compares process CPU time against
  wall-clock time to prove the wait sleeps rather than spins.
* ``tools/verify_message_pump.py`` -- a standalone script that reproduces issue
  #56's scenario using the Java Control Panel and prints ``PASSED`` or
  ``FAILED``, for checking a specific machine without running pytest.
* ``tools/sync_wiki.py`` -- publishes ``docs/`` to the GitHub wiki.

Note on verification
~~~~~~~~~~~~~~~~~~~~

CI has no interactive desktop session, so the pump cannot be exercised against
a live Java application there.  The portable tests cover the logic and the
wiring, and the Windows smoke job proves the real ``pythoncom`` call works; the
end-to-end behaviour is covered by ``tests/test_message_pump_gui.py`` and
``tools/verify_message_pump.py``, both of which need a Windows machine with a
desktop session.  See ``CONTRIBUTING.rst`` for how to run them.  The analysis
behind this change is in ``docs/TRIAGE.md`` section 3.9 (not versioned).

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
