#!/usr/bin/env python
"""Measure what pyjab actually reaches in a real JavaFX window, and what UIA reaches.

Issue #227: ``README.rst`` and four other places claim pyjab drives "Swing / AWT /
**JavaFX** ... through Java Access Bridge", and OpenJFX's own source says JavaFX on Windows
does not use Java Access Bridge at all -- ``com.sun.glass.ui.win.WinAccessible`` implements
the UIA provider interfaces directly and contains no JAB reference.  The half of that which
is *not* known is what pyjab does when it is pointed at a JavaFX window.  This tool answers
that and nothing else.  **It prints numbers; it does not decide what they mean about the
claim.**

Three questions, in this order, because each one is only interpretable if the one before it
was answered:

1. **Can pyjab/JAB find and bind the window at all?**  ``JABDriver(title=...)``, pyjab's own
   lookup and pump.  If it binds, the exact exception is printed -- "not found" and "the
   call failed" are different answers and are printed differently.
2. **If it binds, what does a full walk see?**  ``JABElement.walk()`` with no depth or
   element limit, printed as the roles and names it reached, and as a count.
3. **What does a UIA client see for the same window?**  The same walk M0 used for Swing,
   plus the same **desktop-wide control**: the UIA client enumerates the whole desktop as
   well, so a small count for the JavaFX window can be told apart from a client that cannot
   enumerate anything.  That control is imported from ``tools/verify_m0.py`` rather than
   rewritten, so it is literally the measurement M0 took.

The JAB side also measures the repository's **Swing** application as a control.  Without it
"JAB could not bind the JavaFX window" has two readings -- JavaFX is not exposed through JAB,
or this machine's JAB is broken -- and they look identical in the output.  The Swing window
is the same one M0 measured 601 elements on, so if it binds here, the JavaFX answer is about
JavaFX.  The two applications are launched by this tool, so nothing depends on a window left
behind by an earlier step.

The application is ``tests/java/fx/PyjabFxApp.java``, and the block it prints
(``javafx-app.txt``) is the application's own statement of what it built -- the tool's copy
of the same inventory is printed beside it, so the reader can see both.

Windows, a JavaFX-bearing JDK and an interactive desktop.  Dispatched, never run locally
(AGENTS.md section 4):

    python tools/gui_run.py javafx --java 21

Exit status is 0 when the measurement completed -- **including when the answer is that JAB
found nothing** -- and 2 when it did not, with the reason printed as "not reached".  A
measurement that could not be taken is never printed as a zero.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# The desktop-wide control and the walk that records what it could not read live in
# verify_m0.py.  Imported rather than copied on purpose: the control is only a control if it
# is the same measurement M0 took, and a copy would drift the day either one changed.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_m0 import (  # noqa: E402  (the path has to be set up first)
    Unavailable,
    UiaWalk,
    _counts,
    _uia_walk,
    uia_control,
)

FX_SOURCE = REPO_ROOT / "tests" / "java" / "fx" / "PyjabFxApp.java"
FX_CLASSES = REPO_ROOT / "tests" / "java" / "fx" / "classes"
FX_APP_CLASS = "PyjabFxApp"
FX_INVENTORY_END = "--- end inventory ---"

SWING_SOURCE = REPO_ROOT / "tests" / "java" / "PyjabTestApp.java"
SWING_CLASSES = REPO_ROOT / "tests" / "java" / "classes"
SWING_APP_CLASS = "PyjabTestApp"

#: The application's own inventory, copied here so the reader sees the expectation next to
#: the numbers rather than only in a Java file.  It must match
#: ``PyjabFxApp.CONTROL_INVENTORY``; the application prints its own copy into
#: ``javafx-app.txt`` and a difference between the two is itself worth seeing.
EXPECTED_CONTROLS = (
    "MenuBar",
    "Menu 'File'",
    "MenuItem 'Open'",
    "MenuItem 'Quit'",
    "Label 'FX label'",
    "Button 'FX button one'",
    "Button 'FX button two'",
    "TextField 'fx-text'",
    "TableView",
    "TableColumn 'Name'",
    "TableColumn 'Value'",
)
EXPECTED_CELLS = 4

#: How much of a JAB tree to print.  The Swing control's walk is hundreds of elements and
#: printing all of it would bury the answer; the JavaFX tree, whatever it is, is printed in
#: full up to this many lines.
TREE_LINES = 80

#: The application is launched by this tool, and the whole JAB section runs on one thread
#: (AGENTS.md 2.1: the pump must service the queue of the thread that called Windows_run).
#: A JAB call that never returns therefore has to cost this tool one honest "not reached"
#: row rather than the run, so the section has a wall-clock deadline.
JAB_SECTION_SECONDS = 300.0


# ---------------------------------------------------------------------------
# The JDK and the application
# ---------------------------------------------------------------------------

def java_versions() -> dict:
    """Which ``java`` this run has, and which JavaFX modules it can see.

    ``--list-modules`` is the evidence for the load-bearing claim that the Liberica
    ``jdk+fx`` package really does put JavaFX inside the JDK: if it does, the ``javafx.*``
    modules are listed here.  If the OpenJFX-SDK route was taken instead they are not, and
    the module path is printed instead.  Both are printed rather than assumed.
    """
    info = {"java": shutil.which("java"), "javac": shutil.which("javac"),
            "JAVA_HOME": os.environ.get("JAVA_HOME", "(unset)"),
            "java_version": "(not run)", "modules": "(not run)", "javafx_modules": []}
    if not info["java"]:
        return info
    for args, key in ((["-version"], "java_version"), (["--list-modules"], "modules")):
        try:
            done = subprocess.run([info["java"]] + args, capture_output=True, text=True,
                                  timeout=120)
        except Exception as failure:                        # noqa: BLE001 - reported
            info[key] = f"(could not run java {' '.join(args)}: {failure})"
            continue
        info[key] = (done.stdout + done.stderr).strip()
    info["javafx_modules"] = [line for line in info["modules"].splitlines()
                              if "javafx" in line.lower()]
    return info


def run_javac(source: Path, into: Path, module_path: str = None) -> tuple:
    """Compile one source file, and answer ``(ok, output)``.  Never raises.

    ``module_path`` is passed on to javac as well as to the JVM: when JavaFX is supplied on
    a module path rather than resolved from the JDK's own module image, javac needs it too,
    and a compile that fails there looks exactly like a JDK with no JavaFX at all.
    """
    javac = shutil.which("javac")
    if not javac:
        return False, "javac is not on the PATH. Run this from a JDK, not a JRE."
    into.mkdir(parents=True, exist_ok=True)
    arguments = [javac]
    if module_path:
        arguments += ["--module-path", module_path,
                      "--add-modules", "javafx.controls,javafx.graphics"]
    arguments += ["-d", str(into), str(source)]
    try:
        done = subprocess.run(arguments, capture_output=True, text=True, timeout=300)
    except Exception as failure:                            # noqa: BLE001 - reported
        return False, f"javac could not be run: {failure}"
    return done.returncode == 0, (done.stdout + done.stderr).strip()


def launch(java: str, class_path: Path, app_class: str, title: str, log_path: Path,
           module_path: str = None):
    """Start one application, its output going to a file.

    To a file rather than a pipe: nothing here may block on a reader that stopped reading,
    and the file is uploaded as part of the artifact so the application's own words are
    available even when this tool fails.
    """
    arguments = ["-Duser.language=en", "-Duser.country=US"]        # English locale, as the
    if module_path:                                                # Swing app pins too
        arguments += ["--module-path", module_path,
                      "--add-modules", "javafx.controls,javafx.graphics"]
    arguments += ["-cp", str(class_path), app_class, f"--title={title}"]
    handle = open(log_path, "w", encoding="utf-8")
    try:
        process = subprocess.Popen([java] + arguments, stdout=handle,
                                   stderr=subprocess.STDOUT, cwd=str(REPO_ROOT))
    except Exception:                                       # noqa: BLE001 - re-raised
        handle.close()
        raise
    return process, handle, arguments


def wait_for_inventory(path: Path, process, seconds: float) -> tuple:
    """Wait for the application to say it built its UI.  ``(text, problem)``.

    "the window never appeared" and "the window appeared and this tool did not wait" are
    different findings, so the wait is explicit and its failure is named.  A process that
    has already exited is reported with its output, not waited out.
    """
    deadline = time.monotonic() + seconds
    while True:
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        if FX_INVENTORY_END in text:
            return text, None
        exit_code = process.poll()
        if exit_code is not None:
            return text, (f"the application exited with {exit_code} before it printed its "
                          f"inventory; its output is in {path.name}")
        if time.monotonic() >= deadline:
            return text, (f"the application printed no inventory within {seconds:g}s; its "
                          f"output so far is in {path.name}")
        time.sleep(0.5)


# ---------------------------------------------------------------------------
# pyjab / JAB
# ---------------------------------------------------------------------------

def _window_with_title(windows: dict, title: str):
    for hwnd, window_title in windows.items():
        if window_title == title:
            return hwnd
    return None


def bind_and_walk(driver_class, title: str, timeout: float) -> dict:
    """Bind one window with pyjab and walk it, or report exactly why not.

    The exception text is the answer when the bind fails, so it is captured rather than
    allowed to end the run.  ``bound=False`` with no exception cannot happen and is not
    printed as an empty value -- one of the two is always filled in.
    """
    row = {"title": title, "bound": False, "exception": None, "hwnd": None,
           "elements": None, "tree": None, "tree_truncated": None, "role_counts": {},
           "named": None, "depth": None, "walk_exception": None}
    driver = None
    try:
        driver = driver_class(title=title, timeout=timeout)
    except Exception as failure:                            # noqa: BLE001 - reported
        row["exception"] = f"{type(failure).__name__}: {failure}"
        return row
    row["bound"] = True
    try:
        row["hwnd"] = int(driver.hwnd) if driver.hwnd else None
    except Exception:                                       # noqa: BLE001 - not the question
        pass
    try:
        from pyjab.inspector import walk

        tree = walk(driver.root_element, None, None)
        entries = [(depth, item) for depth, item in tree]
        row["tree"] = entries
        row["tree_truncated"] = tree.truncated
        row["elements"] = len(entries)
        row["role_counts"] = _counts(item["role"] for _depth, item in entries)
        row["named"] = sum(1 for _depth, item in entries if item["name"])
        row["depth"] = max((item["object_depth"] for _depth, item in entries), default=0)
    except Exception as failure:                            # noqa: BLE001 - reported
        row["walk_exception"] = f"{type(failure).__name__}: {failure}"
    finally:
        try:
            driver.detach()             # not __exit__: that terminates the process
        except Exception:                                   # noqa: BLE001 - best effort
            pass
    return row


def jab_section(swing_title: str, fx_title: str, timeout: float) -> dict:
    """Everything measured through pyjab, on one thread.  Runs inside the watchdog."""
    from pyjab.common.win32utils import Win32Utils
    from pyjab.inspector import bridge_without_window
    from pyjab.jabdriver import JABDriver

    result = {}
    bridge = bridge_without_window()
    windows = Win32Utils().enum_windows()
    java_windows = {hwnd: title for hwnd, title in windows.items()
                    if title and bridge.isJavaWindow(hwnd)}
    result["top_level_windows"] = len(windows)
    result["java_window_titles"] = [title for title in java_windows.values() if title]
    for label, title in (("swing", swing_title), ("javafx", fx_title)):
        hwnd = _window_with_title(windows, title)
        result[f"{label}_window_present"] = hwnd is not None
        result[f"{label}_is_java_window"] = bool(hwnd) and bool(bridge.isJavaWindow(hwnd))
    result["swing"] = bind_and_walk(JABDriver, swing_title, timeout)
    result["javafx"] = bind_and_walk(JABDriver, fx_title, timeout)
    return result


def run_jab_section(swing_title: str, fx_title: str, timeout: float,
                    seconds: float) -> tuple:
    """Run :func:`jab_section` under a deadline.  ``(result, problem)``.

    The thread is abandoned rather than joined when it overruns, exactly as
    ``tools/verify_jab_return_values.py`` does: a drive parked inside the DLL cannot be
    killed from here, and the run has stopped depending on it.  Abandoning it turns a hang
    into one honest "not reached" instead of a run with no recording at all.
    """
    found = {}

    def worker():
        try:
            found["result"] = jab_section(swing_title, fx_title, timeout)
        except Exception as failure:                        # noqa: BLE001 - reported
            found["problem"] = f"{type(failure).__name__}: {failure}"

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        return None, (f"the JAB section did not return within {seconds:g}s, so a JAB call "
                      "inside it never came back")
    if "problem" in found:
        return None, found["problem"]
    return found.get("result"), None


# ---------------------------------------------------------------------------
# The UIA client
# ---------------------------------------------------------------------------

def _uia_attribute(control, name: str) -> str:
    try:
        return str(getattr(control, name))
    except Exception as failure:                            # noqa: BLE001 - reported
        return f"(could not read {name}: {type(failure).__name__}: {failure})"


def uia_side(title: str, timeout: float) -> dict:
    """Read the same window through a UIA client.  Never raises.

    The first version of ``tools/verify_m0.py`` printed "UIA sees 0" for a client failure,
    and this one keeps that apart in the same way: a client that is missing or a walk that
    could not finish is :class:`Unavailable`, and is never rendered as a count.
    """
    try:
        import uiautomation
    except Exception as failure:                            # noqa: BLE001 - reported
        return {"_client": Unavailable("the uiautomation package is not importable",
                                       str(failure))}
    try:
        window = uiautomation.WindowControl(searchDepth=2, SubName=title,
                                            Timeout=int(timeout * 1000))
        if not window.Exists(maxSearchSeconds=timeout):
            return {"_client": Unavailable(
                f"no UIA window whose name contains {title!r} appeared within {timeout:g}s")}
    except Exception as failure:                            # noqa: BLE001 - reported
        return {"_client": Unavailable("attaching through UIA failed", str(failure))}

    result = {
        "class_name": _uia_attribute(window, "ClassName"),
        "control_type": _uia_attribute(window, "ControlTypeName"),
        "native_handle": _uia_attribute(window, "NativeWindowHandle"),
    }
    try:
        top_level = [child for child in uiautomation.GetRootControl().GetChildren()
                     if child.ControlTypeName]
        result["windows"] = {"top_level": len(top_level),
                             "sample": [w.Name for w in top_level if w.Name][:5]}
    except Exception as failure:                            # noqa: BLE001 - reported
        result["windows"] = Unavailable("could not enumerate UIA windows", str(failure))

    tree = UiaWalk()
    try:
        _uia_walk(window, 0, tree)
    except Exception as failure:                            # noqa: BLE001 - reported
        result["_client"] = Unavailable("walking the UIA tree failed", str(failure))
        return result
    entries = tree.elements
    result["_walk"] = tree.as_dict()
    result["elements"] = len(entries)
    result["roles"] = len({item["role"] for item in entries})
    result["named"] = sum(1 for item in entries if item["name"])
    result["depth"] = max((item["depth"] for item in entries), default=0)
    result["role_counts"] = _counts(item["role"] for item in entries)
    result["tree"] = entries
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def render_jab_tree(entries: list) -> str:
    """The JAB walk as text, in the inspector's own format, capped."""
    from pyjab.inspector import render_tree

    lines = render_tree(entries).splitlines()
    if len(lines) > TREE_LINES:
        lines = lines[:TREE_LINES] + [
            f"    ... {len(lines) - TREE_LINES} more line(s) not printed"]
    return "\n".join(lines)


def render_uia_tree(entries: list) -> str:
    lines = [f"{'  ' * item['depth']}{item['role']}  name={item['name']!r}"
             for item in entries]
    if len(lines) > TREE_LINES:
        lines = lines[:TREE_LINES] + [
            f"    ... {len(lines) - TREE_LINES} more line(s) not printed"]
    return "\n".join(lines)


def describe_bind(row: dict) -> str:
    """One line for a bind attempt: what happened, or why nothing did."""
    if not row["bound"]:
        return f"NOT BOUND -- {row['exception']}"
    if row["walk_exception"] is not None:
        return (f"bound (hwnd={row['hwnd']}), but the walk failed -- "
                f"{row['walk_exception']}")
    return (f"bound (hwnd={row['hwnd']}), walk {row['elements']} element(s)"
            + (", TRUNCATED" if row["tree_truncated"] else ""))


def print_expectation() -> None:
    """The count the application was built to produce, and why it is that number."""
    print("=" * 78)
    print("what the JavaFX application contains, before anything is measured")
    print("=" * 78)
    for control in EXPECTED_CONTROLS:
        print(f"    {control}")
    print(f"  {len(EXPECTED_CONTROLS)} controls constructed by the application.")
    print(f"  Plus {EXPECTED_CELLS} table cells, which the TableView renders from 2 rows x "
          "2 columns.")
    print(f"  So a complete accessibility tree of the content is at least "
          f"{len(EXPECTED_CONTROLS) + EXPECTED_CELLS} elements, and a larger one is expected "
          "once")
    print("  the containers (root pane, content VBox, button HBox, the table's internal")
    print("  header and rows) and the window's title bar and caption buttons are counted.")
    print("  This is the floor a reader can reason about; the ceiling is what is measured")
    print("  below, and it is not asserted here.")
    print()


def print_jdk(info: dict, module_path: str) -> None:
    print("=" * 78)
    print("the JDK, and whether JavaFX is inside it")
    print("=" * 78)
    print(f"  java      : {info['java']}")
    print(f"  javac     : {info['javac']}")
    print(f"  JAVA_HOME : {info['JAVA_HOME']}")
    for line in info["java_version"].splitlines():
        print(f"  java -version      : {line}")
    if info["javafx_modules"]:
        print("  JavaFX modules this JDK resolves (from `java --list-modules`):")
        for line in info["javafx_modules"]:
            print(f"      {line}")
    else:
        print("  JavaFX modules in this JDK: NONE listed by `java --list-modules`")
    if module_path:
        print(f"  --module-path      : {module_path}")
        print("      (JavaFX is being supplied on the module path, not resolved from the")
        print("       JDK's own module image -- whatever this is, it is not assumed)")
    print()


def print_jab(result: dict, problem: str, swing_title: str, fx_title: str) -> None:
    print("=" * 78)
    print("the pyjab / Java Access Bridge measurement")
    print("=" * 78)
    if problem is not None:
        print(f"  NOT REACHED: {problem}")
        print("  No JAB number is printed, because none was taken. That is not a zero.")
        print()
        return

    print(f"  Windows JAB calls Java windows ({result['top_level_windows']} top-level "
          "windows enumerated):")
    if result["java_window_titles"]:
        for title in result["java_window_titles"]:
            print(f"      {title!r}")
    else:
        print("      (none)")
    for label in ("swing", "javafx"):
        present = result[f"{label}_window_present"]
        is_java = result[f"{label}_is_java_window"]
        print(f"  {label:7s} window present on the desktop: {present}; "
              f"JAB reports it as a Java window: {is_java}")

    print()
    print(f"  CONTROL -- the Swing application {swing_title!r}, the same application M0")
    print("  measured 601 elements on. If this does not bind, the JavaFX answer below says")
    print("  nothing about JavaFX, because JAB is not working on this machine at all.")
    print(f"      {describe_bind(result['swing'])}")
    if result["swing"]["bound"] and result["swing"]["tree"]:
        print("      roles: " + ", ".join(
            f"{role} x{count}" for role, count in
            list(result["swing"]["role_counts"].items())[:10]))
    print()

    print(f"  MEASURED -- the JavaFX application {fx_title!r}")
    print(f"      {describe_bind(result['javafx'])}")
    fx = result["javafx"]
    if fx["bound"] and fx["tree"]:
        print(f"      named elements: {fx['named']} of {fx['elements']}; "
              f"deepest object depth: {fx['depth']}")
        print("      roles: " + ", ".join(
            f"{role} x{count}" for role, count in fx["role_counts"].items()))
        print("      what the walk reached, in the inspector's own format:")
        print(render_jab_tree(fx["tree"]))
    print()


def print_uia(result: dict, control) -> None:
    print("=" * 78)
    print("what a UIA client sees for the same window")
    print("=" * 78)
    client = result.get("_client")
    if isinstance(client, Unavailable):
        print(f"  NOT REACHED: {client.reason}")
        if client.detail:
            print(f"      {client.detail.strip().splitlines()[0][:160]}")
        print("  The UIA number is not printed, because none was taken.")
    else:
        print(f"  window found: class_name={result['class_name']}  "
              f"control_type={result['control_type']}  "
              f"native_handle={result['native_handle']}")
        windows = result.get("windows")
        if isinstance(windows, dict):
            print(f"  top-level UIA windows on the desktop: {windows['top_level']} "
                  f"(sample: {windows['sample']})")
        elif isinstance(windows, Unavailable):
            print(f"  top-level UIA windows: UNAVAILABLE ({windows.reason})")
        print(f"  elements: {result['elements']}  named: {result['named']}  "
              f"roles: {result['roles']}  deepest depth: {result['depth']}")
        print("  roles: " + ", ".join(
            f"{role} x{count}" for role, count in result["role_counts"].items()))
        walk = result.get("_walk")
        if isinstance(walk, dict) and walk.get("incomplete"):
            print(f"  WARNING: the UIA walk did not finish -- {walk.get('reason')}")
            print("           every count above is therefore a lower bound, not a total.")
        print("  the walk, indented by UIA depth:")
        print(render_uia_tree(result["tree"]))
    print()

    print("=" * 78)
    print("the UIA control -- the same one tools/verify_m0.py measured with")
    print("=" * 78)
    print("  A small UIA tree for the JavaFX window has two explanations: the window is")
    print("  opaque to UIA, or this client cannot enumerate anything. This is the number")
    print("  that tells them apart.")
    if isinstance(control, Unavailable):
        print(f"  NOT REACHED: {control.reason}")
        if control.detail:
            print(f"      {control.detail.strip().splitlines()[0][:160]}")
    else:
        print(f"  elements across the whole desktop: {control['elements']}  "
              f"named: {control['named']}  roles: {control['roles']}")
        print(f"  reached the client's element cap: {control['reached_limit']}  "
              f"walk incomplete: {control['incomplete']}")
    print()


def print_summary(jdk: dict, jab: dict, jab_problem: str, uia: dict, control,
                  module_path: str) -> int:
    """The numbers, and whether every one of them was actually taken.

    The exit status is decided here and nowhere else. A missing measurement is a 2; a
    measured answer -- **including "JAB found nothing"** -- is a 0. So a JAB bind failure
    exits 0 and is a result, while "the JavaFX application never started" exits 2 and is not.
    """
    print("=" * 78)
    print("summary")
    print("=" * 78)
    version_lines = jdk["java_version"].splitlines()
    print(f"  JDK        : {version_lines[0] if version_lines else '(unknown)'}")
    if jdk["javafx_modules"]:
        print(f"  JavaFX     : {', '.join(line.strip() for line in jdk['javafx_modules'])}")
    elif module_path:
        print(f"  JavaFX     : from the module path {module_path}")
    else:
        print("  JavaFX     : NOT LISTED by this JDK -- see the JDK section above")

    incomplete = []
    if jab_problem is not None:
        print(f"  JAB        : not reached -- {jab_problem}")
        incomplete.append("the JAB section")
    else:
        swing = jab["swing"]
        fx = jab["javafx"]
        for label, row in (("JAB Swing control", swing), ("JAB JavaFX window", fx)):
            if row["bound"] and row["elements"] is not None:
                print(f"  {label:<17s} : bound, {row['elements']} element(s)")
            else:
                print(f"  {label:<17s} : {describe_bind(row)}")
        if not (swing["bound"] and swing["elements"] is not None):
            print("  -> the Swing control did not bind and walk, so the JavaFX number above")
            print("     cannot be attributed to JavaFX rather than to JAB on this machine.")
            incomplete.append("the Swing control")
    client = uia.get("_client")
    if isinstance(client, Unavailable):
        print(f"  UIA window        : not reached -- {client.reason}")
        incomplete.append("the UIA window")
    else:
        print(f"  UIA JavaFX window : {uia['elements']} element(s), {uia['named']} named")
    if isinstance(control, Unavailable):
        print(f"  UIA desktop control: not reached -- {control.reason}")
        incomplete.append("the UIA desktop control")
    else:
        print(f"  UIA desktop control: {control['elements']} element(s), "
              f"{control['named']} named, {control['roles']} role(s), "
              f"complete walk: {not control['incomplete']}")
    print()
    if incomplete:
        print("NOT REACHED: " + "; ".join(incomplete) + ". No number is invented for any of")
        print("these; the run is not a comparison and exits non-zero.")
        return 2
    print("MEASURED: every side of the comparison was taken. What the numbers mean about")
    print("the README's JavaFX claim is not this tool's answer to give.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--title", default="PyjabFxApp",
                        help="title stem for the launched windows (default PyjabFxApp)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="how long a bind or a UIA window search waits (default 30)")
    parser.add_argument("--app-timeout", type=float, default=60.0,
                        help="how long the application has to print its inventory "
                             "(default 60)")
    parser.add_argument("--module-path", default=None,
                        help="an OpenJFX SDK 'lib' directory, when JavaFX is not in the JDK")
    parser.add_argument("--json", action="store_true",
                        help="also write the numbers as JSON to stdout")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("This needs Windows: it asks the Java Access Bridge and UI Automation about "
              "a live window. Nothing here can be measured elsewhere.", file=sys.stderr)
        return 2

    jdk = java_versions()
    print()
    print("=" * 78)
    print("issue #227 -- what pyjab reaches in a real JavaFX window, and what UIA reaches")
    print("=" * 78)
    print()
    print_expectation()
    print_jdk(jdk, args.module_path)

    if not jdk["java"] or not jdk["javac"]:
        print("NOT REACHED: java and javac must both be on the PATH. No number is printed.")
        return 2

    stamp = str(int(time.time()))
    swing_title = f"{args.title}-swing-{stamp}"
    fx_title = f"{args.title}-{stamp}"

    fx_ok, fx_output = run_javac(FX_SOURCE, FX_CLASSES, args.module_path)
    if not fx_ok:
        print("=" * 78)
        print("the JavaFX application did not compile")
        print("=" * 78)
        print(fx_output)
        print()
        print("NOT REACHED: javac could not build tests/java/fx/PyjabFxApp.java, so no "
              "JavaFX window exists")
        print("to measure. If this says 'package javafx.application does not exist', the "
              "JDK has no JavaFX")
        print("and the run needs the jdk+fx package or --module-path pointing at an OpenJFX "
              "SDK.")
        return 2

    processes = []
    handles = []
    try:
        # The Swing control first, and always: without it a JAB failure on the JavaFX
        # window has two readings -- JavaFX is not exposed through JAB, or JAB is broken
        # on this machine -- and the two look identical in the output.
        swing_ok, swing_output = run_javac(SWING_SOURCE, SWING_CLASSES)
        if not swing_ok:
            print("=" * 78)
            print("the Swing control application did not compile")
            print("=" * 78)
            print(swing_output)
            print()
            print("NOT REACHED: without the control, a JAB failure on the JavaFX window "
                  "cannot be told")
            print("apart from JAB being broken on this machine.")
            return 2
        swing_process, swing_handle, swing_arguments = launch(
            jdk["java"], SWING_CLASSES, SWING_APP_CLASS, swing_title,
            REPO_ROOT / "swing-control.txt")        # no module path: it is plain Swing
        processes.append(swing_process)
        handles.append(swing_handle)
        print(f"launched the Swing control: {' '.join(swing_arguments)}")

        fx_process, fx_handle, fx_arguments = launch(
            jdk["java"], FX_CLASSES, FX_APP_CLASS, fx_title,
            REPO_ROOT / "javafx-app.txt", args.module_path)
        processes.append(fx_process)
        handles.append(fx_handle)
        print(f"launched the JavaFX application: {' '.join(fx_arguments)}")

        inventory, problem = wait_for_inventory(REPO_ROOT / "javafx-app.txt", fx_process,
                                                args.app_timeout)
        print()
        print("=" * 78)
        print("what the JavaFX application itself says it built (javafx-app.txt)")
        print("=" * 78)
        print(inventory.strip() or "(the application wrote nothing)")
        if problem is not None:
            print()
            print(f"NOT REACHED: {problem}")
            return 2

        # The Swing window needs a moment to appear before JAB is asked about it; the
        # JavaFX application has already answered, so at least that much has passed.
        time.sleep(3)

        jab, jab_problem = run_jab_section(swing_title, fx_title, args.timeout,
                                           JAB_SECTION_SECONDS)
        print_jab(jab or {}, jab_problem, swing_title, fx_title)

        uia = uia_side(fx_title, args.timeout)
        control = uia_control()
        print_uia(uia, control)

        exit_code = print_summary(jdk, jab or {}, jab_problem, uia, control,
                                  args.module_path)
        if args.json:
            print(json.dumps({
                "title": fx_title,
                "jdk": {key: value for key, value in jdk.items() if key != "modules"},
                "jab_problem": jab_problem,
                "jab": {key: {k: v for k, v in row.items() if k != "tree"}
                        for key, row in (jab or {}).items() if isinstance(row, dict)},
                "uia": {key: value for key, value in uia.items() if key != "tree"},
                "uia_control": None if isinstance(control, Unavailable) else control,
                "exit_code": exit_code,
            }, indent=2, default=str))
        return exit_code
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    sys.exit(main())
