CHANGELOG
=========

All notable changes to pyjab are documented here.
This project adheres to `Semantic Versioning`_ and `Keep a Changelog`_.

.. _Semantic Versioning: https://semver.org/
.. _Keep a Changelog: https://keepachangelog.com/

Unreleased
----------

Added
~~~~~

* **The GUI suite runs in CI, on a hosted Windows runner.** The four
  ``GUI_TEST_MODULES`` need Windows, a JDK and an interactive desktop session, so they
  had only ever been run by hand -- ``AGENTS.md`` said GitHub runners have no desktop
  session, and five other documents repeated it. That is not true of ``windows-latest``.
  Measured: the runner is in an **active console session** -- session 2, user
  ``runneradmin``, with ``explorer.exe`` running -- so a Swing frame created there gets a
  real ``MainWindowHandle``, ``EnumWindows`` finds it among the desktop's windows, and
  pyjab's own JAB-backed window list reports it.

  ``.github/workflows/windows-gui.yml`` dispatches one task against a chosen Temurin
  JDK: the GUI suite, the M0 comparison, one of the ``tools/verify_*`` scripts, or the
  soak. Runner minutes are free and unmetered for a public repository, so this replaces
  "run it on the other machine and carry the results back" with a log anyone can read.
  It is not a status check and does not run on a push, so a red one does not block a
  merge -- and a green one does not mean the GUI suite ran.

  Enabling the bridge is its own step *before* any JVM starts, and it fails loudly when
  ``~/.accessibility.properties`` was not written. The GUI fixtures launch the
  application before the first ``JABDriver`` exists, and getting that order wrong reads
  as "JAB cannot see the window in CI" rather than as an ordering mistake.

* **``pyjab-inspect``, a locator tool that ships with pyjab.** Issue #75 is "cannot
  find a control", and the answer was to install a separate Java application or read
  the source of the error message, which says nothing matched but not why.

  ```console
  pyjab-inspect windows                      # which Java windows JAB can see
  pyjab-inspect tree "My Application"        # role, name, index, children, per element
  pyjab-inspect find "My Application" "//panel//push button"
  pyjab-inspect locator "My Application" --name Login
  ```

  ``find`` is the one that earns its place: a locator is a sequence of steps and usually
  only one is wrong, so it resolves each prefix and reports the step where the count
  went from *n* to zero, along with the parse errors a predicate can raise. ``tree``
  shows the fields locators match on, and ``locator`` prints locators that resolve right
  now rather than leaving one to be written by hand.

  It is a console script rather than a script in ``tools/``, deliberately: the wheel
  contains only ``pyjab``, so anything under ``tools/`` ships in the sdist and never
  arrives with ``pip install pyjab``. Issue #75 is about someone who installed from
  PyPI.

  It never terminates an application it did not start. ``JABDriver.__exit__`` stops the
  bound Java process by pid, which is right for a driver that launched one and wrong for
  a tool asked to look at a window that was already open.

* **``tools/verify_m0.py``, which measures whether JAB actually sees more than UIA.**
  The whole pyjab-mcp plan rests on the assumption that reading a Java application
  through Java Access Bridge beats reading it through UIA, and nothing had ever tested
  it. The script attaches to a window by title, dumps both trees and prints a
  side-by-side table, then applies the plan's decision table: does each side find the
  table, read a cell's text, see the tree nodes, and how many *named* elements does each
  expose.

  Its one important property is that a measurement it could not take is reported as
  ``UNAVAILABLE (reason)`` and never as a zero. A comparison script that cannot reach
  UIA would otherwise print "pyjab 40 elements, UIA 0" and look like a decisive win for
  the thing under test. Any unavailable row makes the conclusion ``INCONCLUSIVE`` and
  the exit status 1.

  The UIA side is read with a Python UIA client rather than with FlaUI-MCP. That is a
  fair comparison of semantics -- both read the same tree through the same
  ``UIAutomationCore`` -- but it does not measure FlaUI-MCP's own rendering or token
  budget, and the script says so.

* **``tools/check_jab_object_sites.py``, which makes the object-lifetime audit
  mechanical.** Java Access Bridge hands out a reference on every call that returns an
  object, and it has to be released exactly once. Two leaks have been found in this
  codebase that way and neither was found by reading.

  The set of calls that hand out a reference is derived from ``SIGNATURES`` in
  ``pyjab/jabfixedfunc.py`` -- a symbol qualifies if its result type is ``JOBJECT64`` or
  an argument is ``POINTER(JOBJECT64)`` -- so a symbol added to that table is covered
  without anyone remembering. There are seven call sites, and each has a recorded
  destination in the checker. Adding one fails CI until somebody writes down where the
  reference goes.

  What it does **not** do is prove reachability: whether a returned reference is released
  correctly depends on the caller, which is not decidable by reading a call site. The
  disposition is prose because it is a judgement. The set is enforced because it is not.

* **``tools/soak.py``, which measures whether the library gets slower over hours.**
  The roadmap's acceptance criterion for issue #43 is "two hours continuous without
  degradation" and there was no way to check it: no script, no number, nothing to
  compare against.

  It attaches once, runs a fixed workload against the same window, and samples the
  workload's duration and the Java process's resident memory. Then it compares the first
  quarter of the latency samples with the last, as medians rather than endpoints -- one
  GC pause at minute three must not decide the answer -- and reports the least-squares
  slope alongside the ratio, because the two answer different questions: how much worse
  it ended up, and how steadily.

  It measures **the symptom, not a diagnosis**. #43 reads "gets slower until it stalls",
  and a rising curve has several possible causes; the script does not distinguish them
  and says so in its output, in both directions. A stable run is explicitly **not** a
  proof that nothing leaks -- two hours catches a leak costing milliseconds a minute, not
  one costing a byte a lookup.

  It attaches rather than launching, so it never terminates the application it is
  measuring.

* **``SUPPORT.md``: what is free, what is not, and what to include in a report.** The
  README said where to write and nothing about what happens next. This sets out the two
  channels, the things that are deliberately not free -- integration work, a response
  time commitment, custom development, anything under an NDA -- and, most usefully, the
  five things a bug report needs. Almost every report that cannot be acted on is missing
  the same ones.

  It also says the free channel is best effort with **no response time promised**, which
  is true and which the README implied nothing about either way. It is a one-person
  project; an invented service level would be worse than none.

  The bug report checklist points at ``pyjab-inspect``, since a control that cannot be
  found is the most common report and ``find`` reports which step of the locator stopped
  matching.

Fixed
~~~~~

* **``select_row()`` and ``select_column()`` selected nothing on a Swing table.**
  ``addAccessibleSelection`` is a *toggle*, not an add. For a ``JTable``,
  ``AccessibleJTable.addAccessibleSelection(i)`` calls
  ``changeSelection(row, column, toggle=true, extend=false)``, and ``changeSelection``
  toggles that one ``selected`` value into **both** selection models -- with the column
  model updated unconditionally, not guarded by ``getColumnSelectionAllowed()``.

  So ``select_row``'s one add per column turned the row off again on the second cell. A
  5x4 table ended on ``selected_rows == []`` and ``selected_columns == [0, 2]``: the
  caller got no row selected, two columns of junk selection, and no error.
  ``select_column`` was the mirror image, and with an even row count it selected no
  column at all. Measured through a real bridge on JDK 17
  (``tools/verify_table_selection.py``, issue #57's scenario), then reproduced offline
  and on the runner.

  Both now ask ``isAccessibleChildSelectedFromContext`` -- a newly bound symbol, no
  ``errorcheck`` because ``False`` is an answer rather than a failure -- and skip what is
  already selected. In cell-selection mode nothing changes, because there every add is
  wanted. ``clear=False`` stops toggling off a row that was already selected.

  ``select_all()`` had the same root: ``AccessibleJTable.selectAllAccessibleSelection()``
  is ``if (cellSelectionEnabled) { selectAll(); }`` and falls through, so on a default
  Swing table it was a **silent no-op** -- nothing selected, nothing raised. It reads the
  result back now and walks the table when nothing was selected, adding only cells that are
  not already selected, which selects every row, every column or every cell according to
  what the table allows. Where the bridge's own call did work, the check costs one call and
  no adds.

  The offline suite was green because nothing modelled this. ``tests/_fakejab.py`` kept a
  single set of cell indices, and the defect lives in the divergence between the two
  selection models a ``JTable`` keeps. It models both now, from the JDK source, and
  reproduces the runner's exact numbers. Three tests fail on the pre-fix code.

* **``tools/verify_m0.py`` could not return its own clear-win verdict.** ``report()``
  judged each row by the *rendered string*, and ``describe()`` rendered two opposite
  things identically: "the measurement could not be taken" and "the measurement was
  taken and the answer is nothing there". So UIA exposing no table at all made the run
  INCONCLUSIVE, and ``verdict()`` returned there -- before reaching
  ``if jab_text and not uia_text``.

  That branch is the plan's own example of a clear win, and it was unreachable for the
  case it was written for. When UIA finds no table it never sets ``cell`` at all, so
  the row counted as unanswered. The go/no-go for the whole MCP layer could only ever
  answer INCONCLUSIVE.

  ``Absent`` now marks a measured absence, ``report()`` tests the type rather than the
  string, and the ``cell`` question is recorded explicitly when there is no table --
  without that last part the row falls back to "not measured" and nothing changes.
  Both sides set it, and ``--json`` reports ``measured_absence`` beside each reason.

  On the first real run -- pyjab 601 elements and a table cell's text, UIA 6 elements
  and no table -- this turns INCONCLUSIVE into "JAB CLEARLY BETTER", the decision
  table's first row. A regression test drives ``report()`` and ``verdict()`` with that
  payload and returns INCONCLUSIVE under the old logic.

  Failures to measure are unaffected and still make the run incomplete. The five
  per-question reasons a failed call can produce ("could not enumerate UIA windows"
  among them) do not pass through the ``_client`` check, so the type test is what
  keeps them fatal.

* **``verify_m0.py`` printed "a table cell_report's text" in every verdict.** A partial
  rename left ``cell_report`` inside the sentences the script prints. Same commit
  because it is the same function.

* **``tools/verify_xpath.py`` announced a launch it never performed.** The default
  path -- no ``--no-launch`` -- printed "launching PyjabTestApp ..." and then waited
  for a window that nothing had started, so it could only ever time out: ``process =
  None`` was assigned and never read, and the only ``subprocess`` call in the file was
  ``javac``. Only ``--no-launch``, attaching to an application already running, ever
  worked. Found by running it on the hosted Windows runner, which is the first time
  its default path had been run anywhere.

* **``tools/verify_table_selection.py`` reported every table cell as ``None``, and
  asserted something ``select_row()`` does not promise.** The five row mismatches came
  from reading ``.text``. A ``JTable`` cell has no Accessible Text interface -- pyjab
  logs "current JABElement does not support Accessible Text" once per cell and
  ``.text`` returns ``None`` by its own documented contract -- while Swing puts the
  rendered value in the accessible *name*. ``tests/test_components.py`` already
  asserted ``get_cell(0, 0).name == "Kathy"``, and the tool's own scenario 10 prints
  those same values out of ``.name``.

  The sixth mismatch was ``is_row_selected(1)`` after ``select_row(1)``, which
  ``select_row()``'s docstring explicitly declines to promise: there is no JAB call
  that selects a row, it adds each of the row's cells, and "whether the application
  then reports the *row* as selected is up to its implementation". It is reported
  rather than judged now. The observation behind it is still worth reading and is
  flagged in its own words: ``select_row(1)`` left ``selected_rows`` empty and
  ``selected_columns`` ``[0, 2]``, where ``select_cell(2, 1)`` does select its row.

* **The workflow guard could not see a duplicate key.** ``safe_load`` accepts one and
  keeps the last value, so ``test_every_workflow_is_valid_yaml`` passed a file that
  GitHub Actions refuses -- and a refused file is the exact symptom that test exists
  to prevent: the run ends after 0 seconds as "This run likely failed because of a
  workflow file issue", with no jobs and no logs. It now walks the node tree and fails
  with the line and the key, and there is a test that it can find one.

* **Five GUI tests still asserted the root special cases that were removed.** The
  ``test_frame``, ``test_dialog`` and ``test_component_info`` tests in
  ``tests/test_components.py``, and both new-window tests in
  ``tests/test_message_pump_gui.py``, asked for the window's own role as though it were
  a descendant. A search looks at descendants only, so each one raised ``JABException``.

  In the two message-pump tests the raise came on the line *after* the assertion that
  matters: binding the dialog by title -- which is exactly what the pump fix is about --
  had already succeeded. So the pump was never implicated; the incidental follow-up
  check was.

  The entry recording the special-case removal says the eight methods "were not covered
  by a test, and none failed when the special cases were removed". That was wrong in a
  small way. They were covered, by these five call sites, and nothing ran them: the
  first run of the GUI suite in CI found all five.

* **Every error message printed as the repr of a tuple.** ``CommonException`` passed
  ``status`` to ``Exception.__init__`` as a second argument, so ``str()`` of every
  exception pyjab raises was ``('the message', None)`` -- in a terminal, in a log line, and
  quoted in an issue. ``status`` is still there as an attribute; it is no longer a second
  value in the same tuple.

* **``tools/verify_m0.py`` measures a control, without which its result meant nothing.**
  M0 asks whether JAB sees more of a Java application than generic UI Automation does.
  The first run answered 601 elements against 6 and looked decisive — but a UIA client
  that **cannot enumerate at all** produces the same six elements, and UIA reaches Java
  through the MSAA proxy, whose presence is a property of the machine.

  So the same client now walks the **desktop root** as well, and reports what it found
  there. Measured: **147 elements, 99 named, 17 roles, and it finished rather than
  truncating**. The six it reports for the Java window are therefore about Java rather
  than about the client.

  A missing control is ``INCONCLUSIVE`` rather than assumed healthy, and an unmeasured
  one makes the run incomplete, so the exit status matches the conclusion. Both are
  tested, and so is the call itself — the first version of the control defined the
  function and never called it, which no test noticed because every test passed a
  fixture that already had a control in it.

* **The ``gui`` marker is registered.** Four test files set it and nothing declared it, so
  pytest emitted an unknown-mark warning on every run and ``-m gui`` selected nothing
  reliably. It is declared now, which makes ``-m "gui"`` a usable way to run only the
  tests that need a live application and a desktop — worth having now that
  ``windows-gui.yml`` can actually run them.

Added
~~~~~

* **``JABElement.walk()``, a public way to read a subtree.**
  ``max_depth`` and ``limit`` bound it, and each step yields a plain dict —
  ``role``, ``name``, ``description``, ``index_in_parent``, ``children_count``,
  ``object_depth``, ``states``, ``bounds`` — so a caller can write a locator without
  holding anything with a lifetime. ``as_record()`` gives the same dict for one element.

  It moved out of ``pyjab.inspector``, where it was written for the ``pyjab-inspect`` CLI
  and had never promised to be stable. Traversal is something an element can do and the
  CLI was only its first caller; a second project needing it is what settled the question.

  **A truncated walk can now be told from a complete one.** They produce identical
  records, and the old signature — a bare generator — had nowhere to put the answer, so a
  caller could not know whether the window had that much in it or whether they had stopped
  reading. The return value is a ``JABTree`` with ``truncated``, ``limit_hit`` and
  ``max_depth_hit``.

  **Two bugs found while writing its tests**, both pre-existing in the CLI version:

  * ``get_children()`` materialises every child, and each carries a JAB reference. A walk
    that stopped early had taken references to children it would never reach, and nothing
    released them — asking for the first two of twenty **leaked eighteen**. It now uses the
    lazy child generator, so an abandoned walk has taken only what it released.
  * the ``limit`` check sat inside the recursion, where ``return`` ends one frame while the
    parent's loop calls back in. The count was right and the walk re-entered once per
    remaining sibling to discover it had enough.

  Both are covered by ``tests/test_tree_walk.py``, including the case a count cannot
  distinguish: a walk that ends exactly at ``limit``.

* **The thread-affinity rule is now in the user documentation.** Java Access Bridge
  delivers its events to the thread that called ``Windows_run()``, so a driver has to be
  created and used on one thread. That rule lived only in the project's internal notes,
  which are not shipped and not published — so the one thing a caller can get wrong
  silently was the one thing the documentation did not mention.

  ``docs/3-pyjab.md`` now states it, says what it looks like when it is wrong (a window
  that opens later is never seen — no exception), and names ``Win32Utils.pump_messages()``
  as the supported way to keep events arriving from the owning thread between calls.

  No behaviour changed. What changed is that a caller can find out.

* **The bridge DLL is now looked for beside a running JVM, not only in install
  locations.** An application bundled with its own private JRE keeps that JRE somewhere no
  search of ``JAVA_HOME``, ``Program Files`` or ``~/.jdks`` would guess. The application is
  running, so it can be asked: pyjab enumerates top-level windows, reads the image path of
  each process that owns one, and adds the bridge directories those paths imply.

  **This also makes the DLL the right one.** The client DLL pairs with the bridge inside the
  target JVM, and a mismatched pair fails as "pyjab cannot see my window" — the hardest
  failure in this project to tell apart from the bridge simply not being enabled. Using the
  target's own DLL makes the pairing true by construction.

  It runs **after** the environment variables and **before** the vendor sweep: an explicitly
  configured ``JAVA_HOME`` is what the user meant, and this is an inference from what happens
  to be running.

  The search is **best effort** and cannot make discovery worse. Anything that fails while
  asking — no windows, a process that refuses, a platform without the call — leaves the
  existing search untouched, because this only ever adds candidates. There is a test whose
  counter-example is exactly that: removing the guard makes it fail.

  Enumerating windows is plain Win32 and needs nothing from Java, which is what makes this
  possible at all — the DLL is loaded *before* any window can be asked anything, because
  ``isJavaWindow`` needs the DLL.

Changed
~~~~~~~

* **A search that fails because the window itself matches now says so.** Removing the
  root special cases made ``driver.find_element_by_name(window_title)`` raise where it
  used to return the window, and the message was a bare "not found" -- which tells the
  person whose code just broke nothing about what to do. When the window's own name, role
  or description is what would have matched, the exception now names
  ``driver.root_element`` and says that earlier versions returned the window.

  Only on that path: if a descendant matches, the search succeeded and there is nothing
  to explain.

Fixed
~~~~~

* **A second Java object leak, in ``JABDriver``'s vmid construction path.**
  ``init_jab()`` calls ``getTopLevelObject`` to turn a vmid and a context into an hwnd,
  and never released the object it was handed. One Java object per driver built that way
  -- ``JABDriver(vmid=..., accessible_context=...)`` rather than by title or hwnd -- so it
  is far quieter than the per-lookup leak fixed in 1.7.0, and it had gone unnoticed.

  Found by a new check rather than by reading, which is the part worth recording: a hand
  inventory of the calls that hand out a Java object **missed this call twice**, because
  ``init_jab`` also calls ``getAccessibleContextFromHWND``'s wrapper and grouping by
  enclosing function hid the second one.

Changed
~~~~~~~

* **``JABDriver.find_element_by_name`` and seven siblings no longer return the window
  itself.** Searching for the root's own name, role, description or states returned
  ``driver.root_element``; the same call on a ``JABElement`` raised. Two defensible
  behaviours, and having both made the result impossible to release correctly: the
  docstring on every one of these methods says the caller owns what comes back, and the
  root is not the caller's -- the driver holds it for its lifetime.

  ``JABDriver.find_elements_by_name`` and its three siblings were quieter about it.
  They returned ``[root]``, reporting the window as one of its own elements, which it is
  not: a window is not its own descendant.

  The driver's versions now delegate, so both objects answer the same way. The root is
  still reachable, as ``driver.root_element``, which says what it is rather than leaving
  it to be inferred from a search.

  This is a behaviour change for anyone who relied on the old result. The eight methods
  were not covered by a test, and none failed when the special cases were removed.

Changed
~~~~~~~

* **The two XPath traversals are one traversal.** ``_search_path`` returned the first
  match and ``_search_path_all`` collected every match, and they were two
  implementations of the same walk -- 53% identical, differing only in whether a match
  ends the search. The part that was written twice is the ownership bookkeeping: which
  of the references a walk creates belong to the caller and which to the search, each
  released exactly once. That rule is subtle enough that the one leak found in this code
  was a missed case of it, and two copies is how a third case goes unnoticed.

  ``_search_path`` now takes the collection as a parameter and does both. No behaviour
  change: the same locators return the same elements and the same number of bridge calls
  before and after, checked over ten locators in both modes.

  ``tests/test_xpath_ownership.py`` is new and is the reason that claim is checkable
  rather than asserted. It runs a battery of nineteen locators -- predicates, positions,
  comparison, unions, the parent axis, matches at several depths, and paths that fail at
  each step -- through both modes, and checks after every one that the only references
  still outstanding are the elements the caller was given. Nineteen cases in each mode,
  plus a check that the two modes agree about what matches.

Fixed
~~~~~

* **Five places still said pyjab was GPLv2, three releases after it became MIT.**
  The licence declaration at the top of ``AGENTS.md`` was one of them, and so was the
  message ``tools/check_dependency_licences.py`` prints when it refuses a copyleft
  dependency -- which told the reader pyjab "is being moved off the GPLv2 it
  inherited", true before 1.6.0 and false since.

  The check that exists to catch exactly this did not, for two reasons: it scanned
  the README and ``docs/*.md`` but not ``tools/*.py``, where three of the five were,
  and its pattern matched only "pyjab is licensed under ..." and the README's
  "**License:**" bullet. None of the five was written either way.

  The check now reads ``tools/*.py`` and ``AGENTS.md`` when it is present, and matches
  "<project> is <Licence>" as well, with the licence required to be one the check
  knows -- so "pyjab is Windows only" is not read as a claim. That covers two of the
  five; the other three have no verb joining the subject to the licence, or put a
  verb phrase between them, and the check says so in a comment rather than leaving
  the edges to be discovered.

1.8.0 (2026-10-09)
------------------

The XPath subset the tracking issue asked for, completed: positional
predicates and ordered evaluation, comparison operators, unions, and the
parent axis.  Plus two changes that came out of it -- no result is returned
twice, and the new locators are exercised against the real application's
accessibility tree rather than only against trees built to suit them.

Added
~~~~~

* **`tools/verify_xpath.py`, for the part the real-tree test cannot reach.**  The
  locators are tested against the real application's accessibility tree everywhere,
  but that tree comes from the application's own accessibility API -- so it says
  nothing about what **Java Access Bridge** reports, how many round trips a locator
  costs, or whether a click lands.  This script runs on Windows and checks those:
  JAB's `role_en_us` spelling, JAB's `indexinparent` / `childrencount` /
  `objectdepth` values, a real `getAccessibleParentFromContext` for `..`, a
  `simulate=True` click, and the average cost of a lookup.  It exits non-zero and
  prints what each number is supposed to show.

* **The new locators are exercised against the real application's tree, not only
  against hand-built ones.**  `tests/test_xpath_real_tree.py` starts the Swing
  application the GUI suite drives, asks it for its accessibility tree, loads that
  into the fake bridge and runs the locators against **it**.  The accessibility layer
  is a JVM-side API, identical on every platform, so the tree is the one Java Access
  Bridge reports on Windows; only the transport is faked.

  That catches what a hand-built tree cannot: a role spelled the way pyjab expects
  and the application does not use, a name that is not the accessibility name, a
  locator that assumes a depth the real hierarchy does not have.  It needs a JDK and
  skips without one -- including when `which` finds macOS's `/usr/bin/java` stub,
  which is not a JDK and exits non-zero.

* **The parent axis, `..`.**  `//label/..` is the parent of every label, and a step
  after it is a child of that parent: `//label/../panel` is the panel children of
  each label's parent, not every panel below it. `//panel/../..` walks up twice.

  **Results are no longer returned twice.** XPath defines a node-set as "an unordered
  collection of nodes without duplicates", and `//panel/..` reaches the same parent
  once per child. No earlier path could produce a duplicate -- `//a/b` yields a
  distinct `b` each time -- so this was reachable only from the union work and now
  from `..`. The collapse is in one place for both, and the repeat is **released**
  rather than dropped, because the caller owns one reference to each element it is
  handed.

  An ancestor from `getAccessibleParentFromContext` is a reference like any other and
  is released exactly once; `..` past the top of the tree yields nothing rather than
  an error.

* **Unions: `|`.**  `//push button | //label` searches both sides.
  `find_elements_by_xpath` returns each match **once**, because XPath defines a
  node-set as having no duplicates; the repeat is released rather than handed to the
  caller, who would then release it twice. `find_element_by_xpath` takes the **first
  branch that matches**, in the order written -- which is not "first in document
  order", and is documented as the difference rather than glossed over. A `|` inside
  a quoted attribute value is part of the value, the same rule `split_nodes` applies
  to `/`.

* **Comparison operators: `!=`, `<`, `<=`, `>` and `>=`.**  An attribute the element
  reports as an integer is compared **numerically**, so `[@indexinparent > 9]` finds
  index 10 -- compared as strings, `"10"` sorts before `"9"` and the answer would be
  a plausible-looking wrong one. Everything else is compared as a string, which is
  what XPath does with strings: `[@name < 'p2']` is lexicographic and `p10` sorts
  before `p2`.

  `!=` is the complement of `=`, and `=` still routes through the existing matchers,
  so `contains()` keeps working there. Comparisons compose with `and` and with `[n]`.

* **`[n]` positional predicates, and predicates applied in order.**  XPath's own
  semantics, taken from the specification rather than from intuition: `[n]` is
  **1-based** and counted **within each parent**, so `//panel[1]` is the first panel
  child of every parent, not the first panel in the window. The second example in
  W3C XPath 1.0 section 2 is `child::para[position()=1]`, "the first `para` child of
  the context node".

  Predicates now filter **left to right**, which is what makes these two different
  questions rather than the same one:

  ```python
  //panel[@name='OK'][2]     # the second of those named OK
  //panel[2][@name='OK']     # the second panel child, if it happens to be named OK
  ```

  The parser returns an ordered predicate list rather than a flat attribute list,
  because a flat list cannot tell them apart -- and the previous version refused a
  second bracket outright (`extra node conditions found`) rather than approximating.
  The flattened `attributes` key is still returned, so older callers are unaffected.

  `[0]`, `[position()=2]` and `[last()]` are rejected with a parse error instead of
  being approximated: the first because positions are 1-based, the others because
  they need an expression evaluator. `[0]` matching nothing, or `[last()]` quietly
  behaving like `[1]`, would report "no element" for a locator that was never going
  to work.

* **A check that a released changelog section cannot change.**  Every entry added
  after v1.6.3 went into the 1.6.3 section -- that section sits at the top of the
  file and the anchor used to insert them matched it -- so the repository claimed
  1.6.3 included the DPI fix and the xpath leak fix while the sdist on PyPI, built
  from the tree at the tag, did not.  Nothing failed; the next release found it by
  hand.

  ``tools/check_changelog_immutable.py`` compares each released section against a
  digest recorded in ``tools/released_changelog_sections.json``, and CI runs it.  A
  comparison against the tag is the obvious check and does not work where it has to
  run: GitHub Actions checks out at depth 1, with no tags and no history, which is
  also why ``check_dco.py`` skips itself in CI.  The recorded digest needs neither.

  Records all eleven versions whose tags carry a versioned section.  The four older
  ones whose sdists predate the heading format have nothing to compare against, and
  the check says so rather than passing over them silently.

* **``docs/reference/`` — the .bak files that quoted Oracle's headers were recorded
  under the wrong release and are now recorded nowhere.**  Their ``Removed`` entry
  sat in the 1.6.0 section, but v1.6.0 still contains both files and the commit that
  deleted them is first reachable from v1.6.1.  Moving the entry to 1.6.1 would
  change *that* released section instead, so it was removed: it never appeared in any
  sdist, and the removal itself is in the git history where it belongs.  This is the
  same mistake as the one above, one release earlier, and it is why the check exists.

1.7.0 (2026-10-09)
------------------

Clicks landed in the wrong place on a scaled display, every absolute xpath lookup
leaked a Java object, and `or` between XPath predicates was evaluated as `and` --
which found nothing and reported it as the element being absent.

Added
~~~~~

* **`simulate=True` clicks at the wrong place on a scaled display (#62).**  JAB
  reports the **target application's** coordinates and ``SetCursorPos`` takes the
  **calling thread's**; when the two processes scale differently those are different
  spaces, and the click lands elsewhere with nothing reporting an error.

Fixed
~~~~~

* **The run that reproduced #62 ended in a traceback instead of a verdict.**
  ``main()`` read ``landed_raw`` in the reproduction branch before the line that
  assigns it, so the one pass whose answer mattered raised ``UnboundLocalError``
  after printing the numbers — and the numbers were the reproduction.
* **``tools/verify_dpi.py`` now runs the decisive check twice, and can reproduce
  #62 on demand.**  A 150% run on a display with an **unaware** target and an
  **unaware** pyjab reported the JAB position landing — which is the result to
  expect once the two-process geometry is clear: both ends are in the same
  virtualised space, so logical coordinates on the way in and logical coordinates
  on the way out cancel.  That configuration cannot show the bug, and the run said
  "nothing to fix" while testing only one of the two arrangements that matter.
* **``tools/verify_dpi.py`` asked for the target's DPI awareness with a process id
  where the API takes a process handle.**  ``GetProcessDpiAwareness`` is declared
  ``HRESULT GetProcessDpiAwareness(HANDLE hprocess, PROCESS_DPI_AWARENESS *value)``,
  and its ``E_INVALIDARG`` is documented as "the handle or pointer passed in is not
  valid".  Passing the id produced ``-0x7ff8ffa9`` — ``0x80070057``,
  ``ERROR_INVALID_PARAMETER`` 87 — and the tool printed it as though it were a fact
  about the target application rather than a bug in itself.  It now calls
  ``OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, ...)`` first and closes the
  handle afterwards, and decodes any failure into the unsigned HRESULT, its
  facility and its code, with ``E_INVALIDARG`` and ``E_ACCESSDENIED`` named.
* **An aware target was reported as unaware.**  The flag was computed by comparing
  the *display name* — ``PER_MONITOR_AWARE`` — against the *enum member*,
  ``PROCESS_PER_MONITOR_DPI_AWARE``.  They differ, so the comparison never matched
  and every target came back unaware, which is the one answer this must not get
  wrong: it is the value that decides whether a conversion is needed at all.  It
  compares the enumeration values now.
* **``tools/verify_dpi.py`` could not see a scaled display at all.**  It computed the
  monitor scale from ``GetDpiForWindow()``.  Microsoft documents that call as
  returning **96** when the window is DPI unaware — "the answer will depend on the
  DPI awareness mode of the HWND", and the Unaware row is a flat 96.
  ``GetDpiForMonitor`` is the same: its table gives 96 for ``PROCESS_DPI_UNAWARE``
  and the display's real DPI only for per-monitor aware callers.
* **``tools/verify_dpi.py`` could not tell the two explanations apart.**
  ``GetProcessDpiAwareness()`` was called with ``None``, which asks about *this*
  process. Issue #62 turns on **two**: the target decides whether the coordinates
  JAB reports are logical or physical, and pyjab decides whether ``SetCursorPos``
  receives physical pixels or a space Windows scales for it.
* **`or` between XPath predicates was silently evaluated as `and`.**  The parser
  collected every `@name=value` in a predicate and discarded whatever joined them,
  so the matcher ANDed all of them. `//panel[@name='outer' or @name='second']`
  found nothing and reported "no element" — which reads as **the element being
  absent** rather than the locator being wrong, and that is the most expensive way
  to be wrong. Rejecting the operator would have been better than answering it
  incorrectly; honouring it is better still.
* **Every absolute `find_*_by_xpath` lookup leaked a Java object.**
  `_xpath_search_root()` calls `_get_top_level_object()`, which is a JAB call that
  hands out a reference, and nothing released it — not on the found path, not on
  the not-found path. One object per lookup, for the life of the process, in the
  API a test script calls in a loop. Relative locators were never affected: their
  root is `self`, which the caller already owns.
* **`find_elements_by_xpath` had a return contract that depended on the locator.**
  It checked whether its working list was empty at the *top* of each path segment,
  so `//push button` returned `[]` while `//push button/label` — the same failure,
  one segment earlier — raised `JABException`. The rest of the family raises, and
  `get_children()` is the documented exception; this was neither. It raises now,
  always.
* **`find_elements_by_xpath` returns matches in document order.** It ran through
  `_generate_all_childs`, which yields a node *after* its whole subtree, so
  `//label` returned an inner label before the outer one containing it.
* **`find_elements_by_xpath` respects `MAX_SEARCH_DEPTH`.** The traversal it used
  had no ceiling, so a cyclic accessibility tree would still have run away there
  after the single-match path was bounded.
* `_get_elements_by_node`, `_get_children_by_level` and `_get_node_info` are gone.
  The first had no callers once the above landed and the other two were only
  reachable through it.

1.6.3 (2026-10-09)
------------------

Three screenshot methods that the documentation used to promise, and the
removal of a module nothing called.  See Removed for why that last one is
here rather than in a minor release.

Added
~~~~~

* **Three methods the documentation used to promise now exist.**
  ``get_screenshot_as_png()`` and ``get_screenshot_as_base64()`` on both
  ``JABDriver`` and ``JABElement``, and ``get_window_size()`` on the driver.
  ``docs/3-pyjab.md`` had been written from Selenium's documentation and named all
  three; none had ever existed here, and 1.6.1's fix was to correct the docs and
  pin their absence with a test so that adding them would be a decision rather
  than an accident inherited from a copy-paste.  The decision was made, so the
  test now pins their presence instead, for the same reason turned around.

  ``get_screenshot_as_png()`` returns the PNG bytes, ``get_screenshot_as_base64()``
  returns the same bytes base64 encoded -- which is what makes
  ``data:image/png;base64,...`` embedding work -- and ``get_window_size()``
  returns ``(width, height)``.  A tuple rather than the dict Selenium returns for
  that name, to match ``get_window_position()``, which pyjab already made a tuple.

Removed
~~~~~~~

* **``pyjab.common.shortcutkeys``.**  164 lines, 37 methods, and **zero callers**
  anywhere -- not in the package, the tests, the docs or the tooling.  It was a
  list of Oracle *Forms* keyboard shortcuts, which is a different product from
  Swing/AWT; the file's own comment said so.  Left over from somewhere else, and
  never reachable from anything pyjab does.

  It also could not have worked if something had used it: the combination keys
  called ``press_key``, which presses *and releases*, so ``previous_field`` sent
  shift-release followed by tab rather than shift+tab.  The correct call is used
  elsewhere in the same file.

  **This ships in a patch release, which breaks the project's own rule.**  The
  rule is in the release skill and it exists for a reason: a patch is what people
  take without reading.  It is being broken here deliberately, on the
  maintainer's decision, and the reasoning is that the module had **zero callers
  anywhere** -- not in pyjab, not in the tests, not in the docs, not in any script
  -- and was a list of Oracle *Forms* shortcuts in a Swing/AWT library.  The
  exposure is real but small: anyone who imported it by name will get
  ``ModuleNotFoundError`` on a patch version.

  Recorded rather than quietly done, so that the next person who reads "do not
  break existing public API in a patch release" and then looks at this history
  finds a decision instead of an oversight.  It is in the git history for anyone
  who wants it back.

Fixed
~~~~~

* **``tools/verify_dpi.py`` could not finish, on the one machine that can run it.**
  It reached ``driver.win32_utils``, and ``JABDriver`` names that ``win32utils``
  — ``JABElement`` is the one that spells it with an underscore.  The script used
  the element's spelling on the driver, so it raised ``AttributeError`` after the
  JDK had compiled and the measurements had been taken, at the point of the
  decisive click, and produced no verdict.

  Nothing here could have caught it by reading: it compiles, it imports, and it
  runs until Windows.  It is exactly the failure AGENTS.md 1.1 describes, and
  exactly the one it says is mechanical to prevent.

* **The API check now reads ``tools/`` as well**, which is what AGENTS.md 1.1
  asks for — an API is to be confirmed before it is cited "in documentation,
  tests, scripts and issue replies alike".  The check covered the documentation
  and the package's own docstrings and stopped there, so the scripts went unread.

  ``class_members()`` also had to learn that an attribute assigned to ``self``
  inside a method is a member.  ``JABDriver`` sets ``self.win32utils`` in
  ``__init__``, and a check that looked only at the class body reported that as
  missing — a false positive that would have failed on correct code, and a check
  that fails on correct code gets turned off.

* **The XPath documentation claimed a feature that does not exist, and denied two
  that do.**  ``docs/3-pyjab.md`` listed ``[n]`` positional predicates as
  supported.  They are not, and never were: ``get_node_attributes`` recognises
  only ``@name=value``, so a bare ``[1]`` raises.  The test suite knew —
  ``tests/test_xpath_parser.py`` lists ``panel[1]`` among the nodes that must be
  rejected — and the manual said the opposite, for long enough that the tracking
  issue for it recorded it as done.

  The same paragraph called the ``/`` versus ``//`` and ``.`` axes unsupported.
  They are supported and the difference matters: a locator with no leading ``.``
  means the whole window, and ``.//`` means only inside the element it was issued
  from.  Only ``..``, the parent axis, is missing.

  A test now reads the examples out of the documentation and asks the parser about
  each one (``tests/test_xpath_syntax_docs.py``), which is the connection that was
  absent.  It cannot say whether a locator will match anything — that depends on
  the application — but it can say whether the syntax in the manual is syntax
  pyjab accepts, and that is the half that was wrong.

  Also documented while correcting it: ``or`` and ``[n]`` are not rejected.  They
  parse, and then answer wrongly or find nothing, so a locator using them fails as
  "not found" rather than as a syntax error — which is the more expensive way to
  be wrong, because it looks like the element is absent.

* **The documented sign-off command no longer fails on this repository's own
  history.**  ``CONTRIBUTING.rst`` tells a contributor to run
  ``python tools/check_dco.py --base origin/master``, and the obvious way to try
  it is against ``master`` — where it reported nine commits as missing a
  sign-off.  All nine are commits the maintainer pushed directly, from before
  ``tools/check_dco.py`` existed.  Nothing was wrong with them and nothing could
  be: a requirement cannot apply to commits made before it.

  ``check_dco.py`` now knows the commit that introduced the requirement
  (``REQUIRED_FROM``) and reports anything older as ``before-rule`` rather than as
  a failure — reported, not skipped silently, because a rule nobody can see being
  applied is a rule people stop reading.  Everything after that commit is checked
  normally, and a checkout that does not contain the baseline — a fork, a
  throwaway test repository — exempts nothing and checks everything.  That is the
  right direction to fail: a false exemption lets an unsigned commit go
  unremarked, while a false failure is what made the command look broken to the
  person being asked to trust it.

1.6.2 (2026-10-09)
------------------

AccessibleTable selection and scrolling, and the two Windows failures that
1.6.1 was published with.

Added
~~~~~

* **AccessibleTable selection** (#57).  A table is driven through its own
  accessibility selection, and JAB has no call that selects a row or a column, so
  there was no way in at all: ``table.select(...)`` raised ``KeyError: 'table'``
  because the role dispatch did not know about tables.
  ``select_cell(row, column)``, ``select_row(row)``, ``select_column(column)``,
  ``select_all()`` and ``clear_selection()`` now exist, along with
  ``selected_rows``, ``selected_columns``, ``selected_row_count``,
  ``selected_column_count``, ``is_row_selected()`` and ``is_column_selected()``.
  ``select_row`` and ``select_column`` add each cell of that row or column to the
  selection, one index at a time -- whether the application then reports the *row*
  as selected is its decision, so read ``selected_rows`` back rather than assuming
  it.
* **``get_selected_elements()``** (#61).  The cells behind the selection, as
  elements.  ``get_cell()`` reads the table's cell list, which many Java tables
  report with ``bounds = -1`` -- real elements that cannot be clicked.  The ones
  reached through the selection are the ones the application presents, and the
  ones whose actions work.  ``get_selected_element()`` is kept, and its
  relationship to the new method is documented.
* **``get_visible_children()``**.  The children actually on screen, as elements.
  ``docs/6-Troubleshooting.md`` already told readers to bound their loop by what
  ``getVisibleChildren`` returned rather than by ``row_count * column_count``, but
  the only way to make that call was the private ``_get_visible_children()``.
* Seven JAB symbols, none of them declared before:
  ``getAccessibleTableRowSelections``, ``getAccessibleTableColumnSelections``,
  ``isAccessibleTableRowSelected``, ``isAccessibleTableColumnSelected``,
  ``getAccessibleSelectionCountFromContext``,
  ``removeAccessibleSelectionFromContext`` and
  ``selectAllAccessibleSelectionFromContext``.

* **``scroll_into_view()``** (#15).  Best effort, and it returns whether it
  worked rather than assuming.  Java Access Bridge exposes no scroll position --
  there is no call that says where a scroll bar is -- so there is no offset to
  compute and jump to.  This nudges the vertical scroll bar one step at a time and
  re-reads the rectangle, stopping when the element comes inside, when the
  rectangle stops changing, or after ``max_steps``.  ``False`` also means "there
  is no scrollable ancestor", which is not an error.
* **``bounds_within(container)``**.  The geometric half of "on screen", and not
  the same question as ``is_visible()``, which reads the ``visible`` state -- a
  control can be visible and scrolled out of its viewport, which is the whole
  problem here.  Swing's ``-1`` rectangles answer False rather than being compared
  arithmetically.
* ``JABElement.parent`` now says what it is.  Its docstring claimed it returned
  "the JabDriver instance this element was found from"; it returns the accessible
  parent.

Fixed
~~~~~

* **A hanging Java Access Bridge call no longer hangs the suite silently.**
  ``faulthandler_timeout`` is set in ``pyproject.toml``, so a test that stops
  making progress prints every thread's stack -- naming the pyjab call that never
  returned -- and gives up.  It is built into pytest, so it needs no dependency.
  This exists because a hang in the GUI suite is the one failure mode nothing
  covers: CI cannot run that suite, and the machine that can had no way to say
  where it stopped.  The colour chooser tests are where it was first needed.
* **A cyclic accessibility tree no longer walks forever.**  ``_search_element``
  and ``_search_path`` recursed without a ceiling, and Java Access Bridge will
  report a parent among a node's descendants when an application's accessibility
  implementation is wrong or mid-update.  Every step of the walk is a fresh
  cross-process call that succeeds, so following that is not an error -- it is
  either a ``RecursionError`` from inside pyjab or, for a cycle that does not go
  straight down, an unbounded number of calls.  ``MAX_SEARCH_DEPTH`` bounds it and
  the stop is logged, because a silent one would look like a locator problem.  A
  real Swing hierarchy is under twenty deep; the ceiling is a hundred.


* **``double_click()`` raised ``AttributeError`` on Windows.**  ``_double_click_mouse``
  asked ``win32api`` for ``GetDoubleClickTime``; that module does not expose it,
  so every real double click failed with ``AttributeError: module 'win32api' has
  no attribute 'GetDoubleClickTime'``.  It goes through ``ctypes`` to
  ``user32.GetDoubleClickTime`` now, which is where the function actually lives
  and needs no pywin32.  Found by running the GUI suite on Windows, which is the
  only place it can be found: **CI never runs that suite**, so the defect sat
  behind a green build.
* **Seven ``test_dco_check.py`` cases failed on any machine with
  ``commit.gpgsign = true``.**  The throwaway repository those tests build
  inherits the global git config, and a signing requirement it cannot satisfy
  makes ``git commit`` fail there -- ``cannot run gpg`` / ``failed to write commit
  object``.  Confirmed by setting that option locally: seven failures, the same
  seven.  The test repository now disables signing, hooks and message templates
  for itself, and reports git's own stderr when a command fails instead of
  discarding the one thing worth having.


* **Reading a table with off-screen rows could crash the application** (#59).
  Nothing in pyjab indexed past ``returnedChildrenCount``, but the published
  advice did: ``docs/6-Troubleshooting.md`` showed ``len(children.children)`` as
  the bound to use, which was right, while the only way to make the call was a
  private method.  ``get_visible_children()`` is that call, publicly.  Also
  ``get_visible_children()`` is now the supported form of
  ``table._get_visible_children()``, which the troubleshooting page recommended
  and which was never part of the published surface.
* **The scroll-into-view walk leaked Java references.**  Both
  ``find_element_by_role`` and the ancestor walk hand out objects the caller owns,
  and an early version released neither -- one accumulated reference per call,
  which is the shape of #43 ("gets slower until it stalls", still undiagnosed).  A
  test compares the fake bridge's reference counts before and after and fails on
  any growth.


* **Three of those symbols return a bool that means "no".**  Declared with
  ``errorcheck=True`` -- the default mistake in this codebase --
  ``isAccessibleTableRowSelected`` would raise ``RuntimeError: Result 0`` on every
  unselected row, so "is row 3 selected?" could only ever be answered yes; and
  ``getAccessibleSelectionCountFromContext`` would raise on every freshly-opened
  table, which is when it is most often asked.  Both are declared without
  errorcheck, and a test asserts the flags rather than only the behaviour: the
  fake bridge bypasses ctypes, so behaviour alone would not notice.
* **``select()`` on a table raised ``KeyError: 'table'``.**  It now raises
  ``JABException`` naming the methods that do apply, and says the same for any
  other unsupported role instead of failing a dict lookup.
* **``docs/6-Troubleshooting.md`` recommended a private method.**
  ``table._get_visible_children()`` is not part of the published surface.  The API
  check found it as soon as ``table`` was added to the variables it reads -- which
  it was not, so the whole Tables section had been going unchecked.

1.6.1 (2026-10-08)
------------------

A fix for the 1.6.0 release, which is already published and cannot be withdrawn.
See the note under Fixed.

Fixed
~~~~~

* **An MIT wheel contained GPLv2-derived code.**  Two test files kept the
  implementations they were written to compare against, verbatim, as oracles:
  ``_textreader_reference.py`` held the pre-rewrite ``TextReader``, which came
  from NVDA's GPLv2 ``getTextFromRawBytes``, and ``test_focused_element.py`` held
  Chih-Yu's ``get_focused_element``.  Tests travel in the sdist, so both shipped
  -- including in **1.6.0, which is published**.  A PyPI version cannot be
  withdrawn, so this is fixed in 1.6.1; anyone who needs a clean sdist should use
  that rather than the 1.6.0 tarball.  The behaviour each oracle recorded is now
  data -- 1,890 input/output pairs for the decoder, seven rows for the focused
  element -- so the assertions are unchanged and the code they were checking
  against is gone.
* **``pyjab.__license__`` said GPLv2 in the 1.6.0 wheel** whose own METADATA said
  ``License-Expression: MIT``.  Two answers in one installation, and the one a
  user reaches for first was the wrong one.  The licence check reads the module
  attribute now.
* **Six docstrings still carried Selenium's wording.**  The licence change
  rewrote the README and the docs and left the package's own prose alone:
  ``"Saves a screenshot of the current window to a PNG image file. Returns False
  if there is any IOError, else returns True"`` and
  ``"Sets the width and height of the current window. (window.resizeTo)"`` are
  Selenium's text, under the Apache-2.0 licence pyjab no longer mentions.  They
  are written again and say what the methods actually do.
* **Three of those docstrings described behaviour the code does not have.**
  ``get_screenshot_as_file`` returns ``None`` -- its own annotation says so --
  while the docstring promised ``True`` or ``False``.  One example called
  ``element.screenshot()``, which has never existed here, and two cited
  ``window.resizeTo`` and ``window.moveTo``, JavaScript methods with no meaning
  in pyjab.
* **The README named the wrong copyright holder.**  It said "Gary Gao" while
  ``LICENSE`` says "Gary Gao and contributors".  The licence is the operative one,
  so the README was corrected, and the check now compares them.

Changed
~~~~~~~

* ``tools/check_documented_api.py`` reads the package's own docstrings, not only
  the published pages.  That is where the fourth missing method was hiding: the
  package's prose was documentation nobody was checking.
* ``tools/check_license_consistency.py`` also compares the copyright holder in
  ``LICENSE`` with the one the README states.

Removed
~~~~~~~

* ``README_CN.rst``, the Chinese readme, along with its ``MANIFEST.in`` line so it
  stops shipping.  It had drifted out of step with the English one -- its examples
  were reported broken in #64 and never fixed -- and a second readme that nobody
  maintains is a liability rather than a translation.  It is in the git history for
  anyone who wants it.
* ``docs/reference/`` -- two ``.bak`` files that quoted Oracle's headers.  See
  1.6.0 below for what they were; they were dead, unpublished, and the only files
  in the repository that were not pyjab's own.

1.6.0 (2026-10-08)
------------------

Licence
~~~~~~~

**pyjab is now MIT.**  It was GPLv2, and it was GPLv2 for one reason: it
contained code derived from NVDA, which is GPLv2.  That reason is gone -- the
five files that carried it have been written again from the behaviour they
implement rather than from NVDA's text -- and every contributor whose work
remains has agreed to the change.

What this means if you use pyjab:

* you may now use it in commercial and closed-source software.  The only
  obligation is that the copyright notice and the licence text travel with any
  copy or substantial portion of it;
* **versions up to and including 1.5.0 remain GPLv2.**  A licence cannot be
  withdrawn from a version that has already been distributed, so if you are
  pinning one of those, the terms that came with it still apply;
* nothing about the API changes because of this.

Each contributor's consent is recorded in ``CONTRIBUTORS.txt``, with the text of
the reply where there is one to quote.

Fixed
~~~~~

* **The documentation promised three methods that do not exist.**
  ``driver.get_screenshot_as_png()`` and ``driver.get_screenshot_as_base64()``
  were in the screenshots example and have never existed in pyjab, and
  ``driver.get_window_size()`` was listed beside ``get_window_position()`` with no
  counterpart in the code.  ``JABDriver.get_screenshot()``'s own docstring also
  described it as returning base64, and its example called the method that is not
  there -- it returns a Pillow ``Image``.  All four are corrected.  Found by
  ``tools/check_documented_api.py``, written for the purpose.
* **``get_focused_element()`` raised on a window with nothing focused.**  Its
  docstring has always said it returns ``None`` for that; it did not.
  ``getAccessibleContextWithFocus`` was declared with ``errorcheck=True``, and
  that hook raises ``RuntimeError`` on a falsy result before the caller can see
  it, so the guard written for exactly that case was unreachable.  The symbol no
  longer has ``errorcheck``, and the caller checks the status itself.  Found while
  writing the method again for the licence change (below); the live test could
  not have caught it, because on a desktop that has been clicked, something
  always has focus.

Changed
~~~~~~~

* **The code derived from NVDA has been written again.**  Five files --
  ``common/textreader.py``, ``config.py``, ``common/service.py``,
  ``accessibleinfo.py`` and ``jabfixedfunc.py`` -- are now pyjab's own work rather
  than a derivative of another project's, which is what allows the licence to
  change at all.  Every rewrite was checked against the behaviour it replaced:
  1,896 differential comparisons for the encoding heuristics, a field-by-field
  round trip for the structures and the symbol table, and the stream of JAB calls
  left identical.  No behaviour was intended to change, and none was found to.
* ``jabfixedfunc.py`` is a table of signatures rather than three hundred
  repetitive calls, and ``tools/check_jab_symbols.py`` compares its names against
  ``WinAccessBridge.DEF`` from a real JDK.  Doing that found two functions --
  ``getAccessibleTableRowSelectionCount`` and
  ``getAccessibleTableColumnSelectionCount`` -- that were being called with no
  signature declared, so ctypes narrowed their 64-bit context handle to a C int.
  Both are declared now.
* ``get_focused_element()`` has been written again from its behaviour.  The
  method is still Chih-Yu's, and ``CONTRIBUTORS.txt`` says so.

Added
~~~~~

* ``tools/check_license_consistency.py`` -- fails if the licence pyjab declares
  is not the one it ships, across ``LICENSE``, ``pyproject.toml`` and every
  published page that states it.
* ``tools/check_dco.py``, run in CI on pull requests -- fails a commit with no
  ``Signed-off-by``, or one whose sign-off names nobody involved in it.
* ``tools/check_dependency_licences.py``, run in CI -- fails on a copyleft
  runtime dependency, which would either block the licence change or impose its
  terms on everyone who installs pyjab.
* ``tools/verify_dpi.py`` -- measures which coordinate space ``simulate=True``
  needs on a given display, rather than assuming (#62).
* ``tools/check_documented_api.py``, run in CI -- reads the API out of the code
  and fails if ``README.rst`` or ``docs/`` names something that is not there.  It
  exists because this failure is invisible in the direction that matters: a
  missing method in a test fails the suite, whereas a missing method in the
  README fails nothing until a user copies the example.  It found three on its
  first run.

1.5.0 (2026-10-08)
------------------

Added
~~~~~

* **``double_click()`` and ``context_click()``** (#71, #23).  Neither has an
  accessibility action, so both move the mouse and, unlike ``click()``, have no
  non-simulated form.  ``double_click()`` asks Windows for the configured
  double-click interval and puts the gap between its two clicks at half of it,
  rather than assuming a constant -- the documented workaround, two ``click()``
  calls, was only a double click when they happened to fall close enough
  together.
* **``tools/verify_dpi.py``**, which measures what coordinate space
  ``simulate=True`` needs on a given display (#62).  See below for why this is a
  measurement and not a fix.

Fixed
~~~~~

* **A mouse click on an element with impossible bounds moved the cursor to the
  corner of the display.**  ``click(simulate=True)`` rejected only a width or
  height of exactly zero, not the ``-1`` that JAB reports for anything it does
  not place on screen -- table cells above all.  Such a click now raises
  ``JABException`` saying the element cannot be clicked with the mouse and that
  the accessibility action is the way to click it.

Not fixed: DPI scaling (#62)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``simulate=True`` still uses the coordinates JAB reports, unchanged.  Whether
those need converting depends on the DPI awareness of *this* process and of the
*target*: an aware process gives ``SetCursorPos`` physical pixels, an unaware one
gets a virtualised space that Windows scales for it, and the target decides
whether JAB reported logical or physical coordinates in the first place.

Guessing wrong makes a working setup stop working, so this release adds the
measurement instead.  ``tools/verify_dpi.py`` clicks a control whose state change
is observable and reports which coordinate space the display needed.  The
conversion follows once that is in, as its own change with real evidence behind
it.

1.4.3 (2026-10-08)
------------------

Fixed
~~~~~

* **``expand()`` collapsed an element that was already expanded.**  It sent the
  accessibility action ``toggleexpand`` unconditionally, and clicked *twice*
  when asked to simulate; both do the opposite of what the name promises once
  the element is open.  A ``JTree`` shows its root expanded by default, so
  expanding a node in order to reach its children closed it instead and the
  children became invisible.  Expanding something already expanded is now a
  no-op, and ``simulate=True`` sends one click rather than two that cancel out.
* **``is_expanded()`` did not exist.**  The class had ``is_checked``,
  ``is_enabled``, ``is_visible`` and ``is_selected``, but no way to ask the
  question ``expand()`` acts on.

Changed
~~~~~~~

* **The GUI suite starts the test application once per run**, rather than once
  per test.  Starting a JVM and waiting for its window was most of the runtime of
  a suite that is otherwise seconds of work.  Each test still gets its own
  driver, and the application disposes any open dialog before showing a new one,
  so a test cannot be confused by what an earlier one left behind.
* ``test_push_button``, ``test_checkbox`` and ``test_radio_button`` assert on the
  change they make rather than on the state they start in, so any of them can be
  run on its own.

Also ships ``tools/`` in the sdist.  ``CONTRIBUTING.rst``, ``docs/5`` and
``docs/6`` all tell the reader to run a script from there, and the directory had
never been included -- nor had the repository those files would otherwise be read
from.

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
