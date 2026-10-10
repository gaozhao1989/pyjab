"""Measure what the 14 JAB symbols behind issue #195 return on a real JVM.

``jabfixedfunc.SIGNATURES`` carries an ``errorcheck`` flag per row, and
``_fix_bridge_function`` installs :meth:`JABFixedFunc._check_error` as ctypes' ``errcheck``
when set.  The hook **raises on a falsy result**, so arming a row deletes the caller's own
``if not result:`` check and turns a recoverable miss into an uncaught exception.  Arming is
per row, gated on one measurement: **does this symbol return falsy in ordinary operation on
a real JVM?**  That one answer is what step 3 needs.

The application is started the way ``tests/conftest.py`` starts it, and the window is found
by ``JABDriver(title=...)`` -- pyjab's own lookup and pump.  Each symbol is reached by
driving the widget or method that calls it (``element.name``, ``table.get_cell``, a click)
with the bridge wrapped for the duration, so the raw return of **the call the wrapper really
made** is what is recorded.  There is no second, hand-built call whose value could disagree;
building that second call is where the 1461-line version spent its size, and most of its
commits were fixes to that scaffolding rather than measurements.

Each drive runs under a wall-clock watchdog, so a call that never returns costs one
``not reached`` row instead of the run, and an unreached symbol makes the run
``INCONCLUSIVE`` rather than being quietly absent.  The control is a direct
``getAccessibleContextInfo`` on the root element; the NOTE records that ``-1`` is **truthy**,
so a symbol whose failure answer is ``-1`` is not made safe by arming it.

Windows, a JDK and an interactive desktop.  Dispatched, never run locally:

    gh workflow run windows-gui.yml -f task=jab-return-values
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_SRC, JAVA_CLASSES = REPO_ROOT / "tests/java", REPO_ROOT / "tests/java-classes"
APP_CLASS = WINDOW_TITLE = "PyjabTestApp"
LABEL, FIELD, TABLE, BUTTON = "A Label", "1122233455", "Sports table", "Middle button"

#: The JAB header's documented error answer for the calls that have one.  It is **truthy**,
#: so a falsy test never notices it -- see the NOTE the report prints.
DOCUMENTED_ERROR = -1

#: One row per symbol: ``(where the code calls it, what that site does with the result, how
#: this tool reaches it)``.  ``checks`` means the site reads the return itself, so arming the
#: row would make that check unreachable; ``ignores`` means it reads nothing and would start
#: raising on a falsy return.  **THIS IS THE COMPLETE LIST** -- the sweep runs exactly these
#: keys, so a symbol cannot be dropped by being forgotten in a second place.  Widget names
#: are read from ``tests/java/PyjabTestApp.java``.
SITES = {
    "getAccessibleContextInfo": ("jabelement.py:632", "checks", f".name of {LABEL!r}"),
    "getAccessibleTextInfo": ("jabelement.py:664", "checks", f".text of {FIELD!r}"),
    "getAccessibleTextRange": ("jabelement.py:680", "checks", f".text of {FIELD!r}"),
    "getAccessibleTableCellInfo": ("jabelement.py:810", "checks",
                                   f"get_cell(0, 0) on {TABLE!r}"),
    "getVisibleChildren": ("jabelement.py:988", "checks", "get_visible_children()"),
    "getTopLevelObject": ("jabelement.py:597, jabdriver.py:301", "checks",
                          f"_get_top_level_object() on {LABEL!r}"),
    "setTextContents": ("jabelement.py:1618", "checks", f"send_text() on {FIELD!r}"),
    "getAccessibleChildFromContext": ("jabelement.py:376", "ignores", "children()"),
    "getVersionInfo": ("jabdriver.py:374", "ignores", "get_version_info()"),
    "getAccessibleContextFromHWND": ("jabdriver.py:354", "ignores", "JABDriver(hwnd=)"),
    "getHWNDFromAccessibleContext": ("jabdriver.py:304", "ignores",
                                     "JABDriver(vmid=, accessible_context=)"),
    "requestFocus": ("jabelement.py:530", "ignores", f"_request_focus() on {FIELD!r}"),
    "getAccessibleActions": ("jabelement.py:1005", "ignores", f"click() on {BUTTON!r}"),
    "doAccessibleActions": ("jabelement.py:1036", "ignores", f"click() on {BUTTON!r}"),
}
SYMBOLS = tuple(SITES)


class Recorder(object):
    """A bridge that hands every attribute through, recording one symbol's return.

    ``restype``/``argtypes`` live on the *underlying* function, set by ``JABFixedFunc`` when
    ``JABDriver`` is built, so delegating with ``getattr`` preserves them; re-declaring a
    signature here would measure a different call from the one pyjab makes.
    """

    def __init__(self, bridge, target: str) -> None:
        self._bridge, self.target, self.hits = bridge, target, 0
        #: ``result`` stays None until a call arrives, so a symbol that never arrived is
        #: told apart from one that legitimately answered ``None``.
        self.result, self.falsy, self.error = None, False, None

    def __getattr__(self, name):
        attribute = getattr(self._bridge, name)
        if name != self.target or not callable(attribute):
            return attribute

        def recorded(*args, **kwargs):
            self.hits += 1
            try:
                self.result = attribute(*args, **kwargs)
            except Exception as failure:                # noqa: BLE001 - reported
                self.error = f"{type(failure).__name__}: {failure}"
                raise
            self.falsy = not self.result
            return self.result

        return recorded


#: The recorder in force, so every ``JABElement`` created during a drive inherits it.
#: ``find_element_by_name`` and ``click()`` build their own elements, and one built with the
#: real bridge would make the call the site makes invisible to the measurement.
ACTIVE = None


def install_wrapping() -> None:
    """Make ``JABElement.__init__`` take the bridge in force.  Idempotent."""
    from pyjab.jabelement import JABElement

    if getattr(JABElement, "_measures_through_recorder", False):
        return
    original = JABElement.__init__

    def init(self, bridge=None, hwnd=None, vmid=None, accessible_context=None):
        original(self, ACTIVE or bridge, hwnd, vmid, accessible_context)

    JABElement.__init__ = init
    JABElement._measures_through_recorder = True


def not_reached(reason: str) -> str:
    """The one prefix every unmeasured row carries, so it is grep-able."""
    return f"not reached: {reason}"


def new_hs_errs(where: Path) -> list:
    """Every crash-log name in ``where``, so a sweep can tell a new one from one left over."""
    return [log.name for log in where.glob("hs_err_pid*.log")]


def hs_err(where: Path):
    """The target JVM's crash log, if it left one.  A dead target is the finding.

    ``jab-return-values`` on master@d1fbf9f (run 38069167939) shows the target dying with
    ``EXCEPTION_ACCESS_VIOLATION`` in ``jvm.dll`` about 13s in, and that is what "the harness
    cannot drive the application" looks like from the inside: the window vanishes, so the
    bind times out and every later row reads as unreachable.  The JVM writes
    ``hs_err_pid<pid>.log`` beside its working directory and the workflow uploads ``*.log``,
    so the evidence is already in the artifact -- and a partial log is still evidence.
    """
    for log in sorted(where.glob("hs_err_pid*.log")):
        signal = frame = ""
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if not signal and line.startswith("#  ") and "EXCEPTION_" in line:
                signal = line[3:].strip()
            elif not frame and line.startswith("# V  "):
                frame = line[3:].strip()
        return {"path": log.name, "signal": signal, "frame": frame}
    return None


def watchdog(drive, ctx, seconds: float):
    """Run one drive under a deadline.  Returns ``(where, problem)``.

    A drive parked inside the DLL cannot be killed from here, so the thread is abandoned
    rather than waited on; it is a daemon, and the run has stopped depending on it.  That
    turns a hang into one honest ``not reached`` row instead of a lost run.
    """
    found = {}

    def run():
        try:
            found["where"] = drive(ctx)
        except Exception as failure:                    # noqa: BLE001 - reported
            found["problem"] = f"{type(failure).__name__}: {failure}"

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        return None, (f"the harness could not drive it: no return from the drive within "
                      f"{seconds:g}s, so a JAB call inside it did not come back")
    if "problem" in found:
        return None, f"the harness could not drive it: {found['problem']}"
    return found["where"], None


def measure(jab, symbol: str, seconds: float) -> dict:
    """Drive one symbol through pyjab and report what its raw call returned.

    The drives take the driver from a context dict rather than off a variable called
    ``driver``, which keeps the documented-API checker away from the private helpers the two
    binding rows and the focus row need.
    """
    global ACTIVE
    site, expects, reached_by = SITES[symbol]
    row = dict(symbol=symbol, site=site, expects=expects, reached_by=reached_by, raw=None,
               type=None, falsy=None, outcome=None, reason=None)
    recorder = ACTIVE = Recorder(jab.bridge, symbol)
    owners = [owner for owner in (jab, jab.root_element) if owner is not None]
    for owner in owners:
        owner.bridge = recorder
    try:
        where, problem = watchdog(DRIVES[symbol], {"jab": jab}, seconds)
        if problem is not None:
            row["reason"] = not_reached(problem)
        elif recorder.hits < 1:
            row["reason"] = not_reached(
                f"the harness could not drive it: no call to {symbol} was observed on the "
                f"wrapped bridge while {where}")
        elif recorder.error is not None:
            row["reason"] = not_reached(
                f"the harness could not drive it: the call raised {recorder.error}")
        else:
            row.update(raw=recorder.result, type=type(recorder.result).__name__,
                       falsy=recorder.falsy, outcome=where)
    finally:
        for owner in owners:
            owner.bridge = recorder._bridge
    return row


def control(jab, seconds: float) -> dict:
    """A direct ``getAccessibleContextInfo`` on the root: truthy, or nothing is measured.

    It goes through the same recorder as every row, so this is the same call the candidate
    row for that symbol makes -- on an element that must answer.
    """
    row = {"raw": None, "type": None, "falsy": None, "reason": None}
    root, recorder = jab.root_element, Recorder(jab.bridge, "getAccessibleContextInfo")
    root.bridge = recorder
    try:
        where, problem = watchdog(lambda ctx: ctx["root"].name, {"root": root}, seconds)
        if problem is not None:
            row["reason"] = not_reached(f"{problem} (reading root_element.name)")
        elif recorder.hits < 1 or recorder.error is not None:
            row["reason"] = not_reached(
                "the harness could not drive it: reading root_element.name did not reach "
                f"getAccessibleContextInfo ({recorder.error or 'no call observed'})")
        else:
            row.update(raw=recorder.result, type=type(recorder.result).__name__,
                       falsy=recorder.falsy, note=where)
    finally:
        root.bridge = jab.bridge
    return row


# ---------------------------------------------------------------------------
# Reaching each symbol, through the code that calls it
# ---------------------------------------------------------------------------

def _find(ctx, name):
    return ctx["jab"].find_element_by_name(name)


def _name(ctx):
    _find(ctx, LABEL).name                  # every element property funnels through it
    return SITES["getAccessibleContextInfo"][2]


def _text(ctx):
    _find(ctx, FIELD).text                  # the info, then the range it describes
    return SITES["getAccessibleTextInfo"][2]


def _cell(ctx):
    cell = _find(ctx, TABLE).get_cell(0, 0)
    try:
        return f"{SITES['getAccessibleTableCellInfo'][2]}, cell name={cell.name!r}"
    finally:
        cell.release_jabelement()           # get_cell hands back a reference we own


def _visible(ctx):
    children = ctx["jab"].root_element.get_visible_children()
    try:
        return f"{SITES['getVisibleChildren'][2]}: {len(children)} child(ren)"
    finally:
        for child in children:
            child.release_jabelement()


def _top_level(ctx):
    label = _find(ctx, LABEL)
    top = label._get_top_level_object()
    try:
        return f"{SITES['getTopLevelObject'][2]} -> {top!r}"
    finally:
        if top:
            label.bridge.releaseJavaObject(label.vmid, top)


def _text_write(ctx):
    field = _find(ctx, FIELD)
    field.send_text(FIELD + "-measured")
    field.send_text(FIELD)                  # leave the field as the rows after this found it
    return f"send_text() twice on {FIELD!r}, leaving {FIELD!r} in the field"


def _children(ctx):
    found = list(ctx["jab"].root_element.children())
    try:
        return f"{SITES['getAccessibleChildFromContext'][2]}: {len(found)} element(s)"
    finally:
        for child in found:
            child.release_jabelement()


def _version(ctx):
    return f"get_version_info() returned {ctx['jab'].get_version_info()['VMVersion']!r}"


def _bind(ctx, **kwargs):
    from pyjab.jabdriver import JABDriver

    second = JABDriver(timeout=10, **kwargs)
    try:
        return f"JABDriver({', '.join(sorted(kwargs))}) bound hwnd={second.hwnd!r}"
    finally:
        second.detach()                     # not __exit__: that SIGTERMs the application


def _from_hwnd(ctx):
    jab = ctx["jab"]
    hwnd = jab.get_java_window_hwnd(jab.title)
    if not hwnd:
        raise RuntimeError(f"no window handle for {jab.title!r}")
    return _bind(ctx, hwnd=hwnd)


def _from_context(ctx):
    return _bind(ctx, vmid=ctx["jab"].vmid, accessible_context=ctx["jab"].accessible_context)


def _focus(ctx):
    field = _find(ctx, FIELD)
    field.win32_utils.set_window_foreground(hwnd=field.hwnd)
    field._request_focus()          # the call clear(simulate=True) makes, minus backspaces
    return SITES["requestFocus"][2]


def _actions(ctx):
    _find(ctx, BUTTON).click()
    return f"click() on {BUTTON!r}, where both action calls are made"


DRIVES = {
    "getAccessibleContextInfo": _name, "getAccessibleTextInfo": _text,
    "getAccessibleTextRange": _text, "getAccessibleTableCellInfo": _cell,
    "getVisibleChildren": _visible, "getTopLevelObject": _top_level,
    "setTextContents": _text_write, "getAccessibleChildFromContext": _children,
    "getVersionInfo": _version, "getAccessibleContextFromHWND": _from_hwnd,
    "getHWNDFromAccessibleContext": _from_context, "requestFocus": _focus,
    "getAccessibleActions": _actions, "doAccessibleActions": _actions,
}
assert set(SYMBOLS) == set(DRIVES), "the sweep and its drives disagree"


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

def render(row: dict) -> str:
    """The raw return, its type and its truthiness -- or why there is none."""
    if row["reason"] is not None:
        return f"raw {row['symbol']} -> {row['reason']}"
    return (f"raw {row['symbol']} -> {row['raw']!r} ({row['type']})  "
            f"{'falsy?' if row['falsy'] else 'nonzero?'}")


def note_on_documented_error() -> str:
    """The truthy-``-1`` note, printed with the result rather than kept in a comment."""
    return (f"NOTE: {DOCUMENTED_ERROR} is truthy, so a row armed with the errcheck hook "
            "passes a documented error value straight through. A symbol whose failure "
            f"answer is {DOCUMENTED_ERROR} (getObjectDepth, for one) is not made safe by "
            "arming it.")


def report(rows: list, row_control: dict, crash: dict = None) -> int:
    """Print every row, and return the exit code.  All but a complete sweep is 2.

    ``crash`` is the target JVM's parsed ``hs_err``, or None while it is alive.  It is
    printed beside the control because a dead target is a stronger statement than any row: a
    falsy return measured before the death cannot be attributed to the application rather
    than to the JVM going away.
    """
    print("\n" + "=" * 78)
    print("one line per symbol: raw return, its type, truthiness, and how it was reached")
    print("=" * 78)
    for row in rows:
        print(f"\n{row['symbol']}   ({row['site']}; the site {row['expects']} the result)")
        print(f"  reached by : {row['reached_by']}")
        if row["outcome"] is not None:
            print(f"  pyjab path : {row['outcome']}")
        print(f"  {render(row)}")

    control_ok = row_control["reason"] is None and not row_control["falsy"]
    jvm = ("JVM: alive at the end of the sweep" if crash is None
           else "JVM: JVM crash -- died with {}{} ({})".format(
               crash["signal"] or "a crash",
               f" at {crash['frame']}" if crash.get("frame") else "", crash["path"]))
    print("\n" + "=" * 78)
    print("the control, without which a falsy result means nothing")
    print("=" * 78)
    if row_control["reason"] is not None:
        print(f"  FAIL {row_control['reason']}")
    else:
        verdict = ("truthy as required" if control_ok
                   else "FALSY -- so nothing below it is a measurement")
        print(f"  {'ok' if control_ok else 'FAIL'} direct getAccessibleContextInfo on the "
              f"root -> {row_control['raw']!r} ({row_control['type']}), {verdict}")
    print(f"  {'ok' if crash is None else 'FAIL'} {jvm}")

    unreached = [row for row in rows if row["reason"] is not None]
    falsy = [row for row in rows if row["falsy"]]
    print("\n" + "=" * 78)
    print("summary")
    print("=" * 78)
    print(f"  {'ok' if control_ok else 'FAIL'} control: direct getAccessibleContextInfo on "
          "the root element")
    print(f"  {'ok' if crash is None else 'FAIL'} {jvm}")
    print(f"  reached: {len(rows) - len(unreached)} of {len(SYMBOLS)} symbols measured "
          "through the pyjab call site that makes them")
    for row in rows:
        print(f"  {row['symbol']}: {render(row).split(' -> ', 1)[1]}")
    for row in unreached:
        print(f"  not reached: {row['symbol']} -> {row['reason']}")
    if falsy:
        print(f"  FINDING: {len(falsy)} symbol(s) return falsy in ordinary operation, so "
              "arming those rows needs handling first: "
              + ", ".join(row["symbol"] for row in falsy))
    else:
        print("  FINDING: no candidate symbol returned falsy in this run, so arming any of "
              "these rows changes nothing observable -- subject to the control above")
    print(f"  {note_on_documented_error()}")
    print()
    if crash:
        print(f"INCONCLUSIVE: the target JVM died with {crash['signal'] or 'a crash'}"
              + (f" at {crash['frame']}" if crash.get("frame") else "")
              + f" ({crash['path']}), so the rows above are about a JVM that was going away "
                "rather than about these symbols")
        return 2
    if not control_ok:
        print("INCONCLUSIVE: the direct getAccessibleContextInfo control on the root did "
              "not come back truthy, so nothing above it is a measurement")
        return 2
    if unreached:
        print("INCONCLUSIVE: " + "; ".join(
            f"{row['symbol']} -> {row['reason']}" for row in unreached))
        return 2
    print(f"PASSED: every one of the {len(SYMBOLS)} symbols was reached through its call "
          "site and its raw return was read -- "
          + (f"falsy: {', '.join(row['symbol'] for row in falsy)}" if falsy
             else "none returned falsy"))
    return 0


def unmeasured(symbol: str, reason: str) -> dict:
    """A row for a symbol the sweep did not measure, carrying its reason."""
    site, expects, reached_by = SITES[symbol]
    return dict(symbol=symbol, site=site, expects=expects, reached_by=reached_by, raw=None,
                type=None, falsy=None, outcome=None, reason=not_reached(reason))


def compile_test_app() -> bool:
    """Compile ``tests/java`` on demand, exactly as the ``test_app`` fixture does."""
    javac = shutil.which("javac")
    if not javac:
        print("javac is not on the PATH. Run this from a JDK, not a JRE.")
        return False
    JAVA_CLASSES.mkdir(parents=True, exist_ok=True)
    sources = sorted(str(path) for path in JAVA_SRC.glob("*.java"))
    result = subprocess.run([javac, "-d", str(JAVA_CLASSES), *sources],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"compiling the test application failed:\n{result.stdout}\n{result.stderr}")
        return False
    return True


def launch(title: str):
    """Start the application as ``tests/conftest.py`` does, and bind it with pyjab.

    The title is unique to this run because binding by a fixed one can match a window left
    behind by an earlier run.  The bind is ``JABDriver(title=...)``, pyjab's own window
    lookup and pump, so this tool carries no second way to find a window.
    """
    from pyjab.jabdriver import JABDriver

    java = shutil.which("java")
    if not java:
        print("java is not on the PATH. Run this from a JDK, not a JRE.")
        return None, None
    process = subprocess.Popen([java, "-Duser.language=en", "-Duser.country=US",
                                "-cp", str(JAVA_CLASSES), APP_CLASS, f"--title={title}"])
    try:
        return JABDriver(title=f"{title}*", timeout=60), process
    except Exception as failure:                        # noqa: BLE001 - reported
        process.terminate()
        print(f"binding a JABDriver by title failed: {type(failure).__name__}: {failure}")
        return None, process


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure JAB return values for #195.")
    parser.add_argument("--timeout", type=float, default=1500.0,
                        help="budget for the whole sweep, in seconds (default 1500)")
    parser.add_argument("--symbol-timeout", type=float, default=60.0,
                        help="wall-clock budget for one drive, in seconds (default 60)")
    parser.add_argument("--title", default=WINDOW_TITLE,
                        help="window title stem to launch and bind (default PyjabTestApp)")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("This needs Windows: it asks the Java Access Bridge about a live window.",
              file=sys.stderr)
        return 2
    if not compile_test_app():
        return 2

    install_wrapping()
    # An hs_err log already here belongs to an earlier run, so this run only claims one that
    # appears after this point.
    known = {log.name for log in Path.cwd().glob("hs_err_pid*.log")}
    jab, process = launch(f"{args.title}-{int(time.time())}")
    if jab is None:
        return 2
    deadline, rows = time.monotonic() + args.timeout, []
    row_control, exit_code, crash = None, None, None
    try:
        # The control runs first, while the JVM is known to be healthy: one taken after a
        # mid-sweep death would be a statement about the death, not about the bridge.
        row_control = control(jab, args.symbol_timeout)
        print("  control: direct getAccessibleContextInfo on the root -> "
              f"{row_control['raw']!r}", flush=True)
        for symbol in SYMBOLS:
            exit_code = process.poll() if process is not None else None
            if exit_code is not None or set(new_hs_errs(Path.cwd())) - known:
                # Every later row would be a statement about an absent JVM, not a symbol.
                crash = hs_err(Path.cwd())
                print(f"  the target JVM is gone (exit {exit_code}); stopping the sweep at "
                      f"{symbol}", flush=True)
                for rest in SYMBOLS[SYMBOLS.index(symbol):]:
                    rows.append(unmeasured(rest, "the harness could not drive it: the target "
                                                 f"JVM died (exit {exit_code}) before this "
                                                 "symbol was measured"))
                break
            left = deadline - time.monotonic()
            if left <= 0:
                rows.append(unmeasured(symbol, "the harness could not drive it: the sweep's "
                                               f"{args.timeout:g}s budget ran out first"))
                continue
            rows.append(measure(jab, symbol, min(args.symbol_timeout, left)))
            print(f"  measured {symbol}: {render(rows[-1])}", flush=True)
    finally:
        try:
            jab.detach()
        except Exception:                               # noqa: BLE001 - best effort
            pass
        if process is not None and process.poll() is None:
            process.terminate()
            try:                                        # pragma: no cover - defensive
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        elif process is not None:
            exit_code = process.returncode
        # Read for the crash log last: a JVM dying as this unwinds still leaves one.
        if crash is None and exit_code not in (None, 0):
            crash = hs_err(Path.cwd())
    return report(rows, row_control, crash=crash)


if __name__ == "__main__":
    sys.exit(main())
