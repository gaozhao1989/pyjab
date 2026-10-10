"""``getVisibleChildrenCount`` has no error sentinel, so this checks what the property does.

Issue #191 held two answers that could not both be true. ``JABElement.visible_children_count``
guarded the call with ``if not result:``, and the JAB header documents
``getVisibleChildrenCount`` as returning **``-1`` on error** -- so by that contract a refusal
returning ``-1`` is truthy and the property returns ``-1`` as a count, while a legitimate
``0`` is falsy and the property **raises** on an element that simply has no children.

This tool was written to read the raw number, because the property was what raised and the
raise hid it. It measured what settles the question:

* **"Painted panel"** -- the childless self-painting ``JPanel`` in
  ``tests/java/PyjabTestApp.java`` -- raw return **``0``**;
* **"Main panel"** -- the control, a panel that really does have children -- raw return
  ``171``.

**The bridge answers ``0`` for a refusal and never ``-1``**, so there is no sentinel, and
``if not result:`` was wrong in both directions: it raised on a legitimate zero and could not
have detected a refusal. ``visible_children_count`` now returns the bridge's number, ``0``
included, and does not raise; the readable signal is ``children_count``, whose
``getAccessibleContextInfo`` check is live.

So this tool's job is now to confirm that on a real JVM: it prints both raw returns, and
``visible_children_count`` has to equal its element's raw value and must not raise.

Windows, a JDK and an interactive desktop. Dispatched, never run locally:

    gh workflow run windows-gui.yml -f task=visible-children-count
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_SRC = REPO_ROOT / "tests" / "java"
JAVA_CLASSES = REPO_ROOT / "tests" / "java-classes"
APP_CLASS = "PyjabTestApp"
WINDOW_TITLE = "PyjabTestApp"

#: The element whose visible count the bridge refuses. Measured: the raw return is ``0``.
PAINTED_NAME = "Painted panel"
#: The control: a panel with children, so a raw number here has to be non-zero.
CONTROL_NAME = "Main panel"

#: The sentinel the JAB header documents and this JVM does not use. Named because seeing it
#: here would contradict the measurement #191 recorded.
DOCUMENTED_ERROR = -1


def compile_test_app() -> bool:
    javac = shutil.which("javac")
    if not javac:
        print("javac is not on the PATH. Run this from a JDK, not a JRE.")
        return False
    JAVA_CLASSES.mkdir(parents=True, exist_ok=True)
    sources = sorted(str(p) for p in JAVA_SRC.glob("*.java"))
    result = subprocess.run([javac, "-d", str(JAVA_CLASSES), *sources],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("compiling the test application failed:")
        print(result.stdout, result.stderr)
        return False
    return True


def launch() -> Optional[subprocess.Popen]:
    """Start the application with plain subprocess, so no pyjab call is involved.

    The same reason ``tools/verify_jvm_discovery.py`` gives: this measures what the bridge
    returns for a window pyjab attached to, and letting pyjab launch it would put its own
    code in the path being measured.
    """
    java = shutil.which("java")
    if not java:
        print("java is not on the PATH.")
        return None
    proc = subprocess.Popen(
        [java, "-cp", str(JAVA_CLASSES), APP_CLASS, f"--title={WINDOW_TITLE}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"  launched {APP_CLASS} (pid {proc.pid}) with plain subprocess, no pyjab")
    return proc


def wait_for_window(timeout: float = 60.0):
    """Wait for the window using Win32 only, so the control does not need JAB.

    If this cannot find the window, an empty result below means nothing at all.
    """
    from pyjab.common.win32utils import Win32Utils

    win32 = Win32Utils()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = win32.get_hwnds_by_title(f"*{WINDOW_TITLE}*")
        if matches:
            return matches
        time.sleep(0.5)
    return []


def behaviour(value, error: Optional[str]) -> str:
    """What one property did: the number it returned, or the exception it raised."""
    if error is not None:
        return f"raises {error}"
    return f"returns {value!r}"


def probe(element, label: str) -> dict:
    """Everything needed about one element, without anything raising out of here.

    **The raw call is made before ``visible_children_count``.** The raw return is what the
    property has to agree with, so it is read first and a failure there is reported rather
    than being confused with the property's own answer.
    """
    found = {
        "label": label,
        "role": None,
        "children_count": None,
        "raw": None,
        "raw_error": None,
        "visible": None,
        "visible_error": None,
    }

    found["role"] = element.role_en_us
    found["children_count"] = element.children_count

    # The bridge's own return, with the same arguments the property passes. Not
    # element.visible_children_count: that is the caller under test.
    try:
        found["raw"] = element.bridge.getVisibleChildrenCount(
            element.vmid, element.accessible_context
        )
    except Exception as error:                            # noqa: BLE001 - reported
        found["raw_error"] = f"{type(error).__name__}: {error}"

    try:
        found["visible"] = element.visible_children_count
    except Exception as error:                            # noqa: BLE001 - reported
        found["visible_error"] = f"{type(error).__name__}: {error}"

    return found


def report(found: dict) -> None:
    print(f"\n{found['label']}")
    print("-" * len(found["label"]))
    print(f"  role_en_us                  : {found['role']!r}")
    print(f"  children_count              : {found['children_count']!r}")
    if found["raw_error"] is not None:
        print(f"  raw getVisibleChildrenCount : raised {found['raw_error']}")
    else:
        print(f"  raw getVisibleChildrenCount : {found['raw']!r} "
              f"({type(found['raw']).__name__})")
    print(f"  visible_children_count      : "
          f"{behaviour(found['visible'], found['visible_error'])}")


def disagreement(found: dict) -> Optional[str]:
    """Whether the property returned the direct call's number, without raising.

    The contract since #191 is that ``visible_children_count`` is the raw return, ``0``
    included. A raise, or a different number, means the property is not the pass-through it
    is documented to be.
    """
    if found["raw_error"] is not None:
        return (f"the direct call for '{found['label']}' itself raised: "
                f"{found['raw_error']}")

    if found["visible_error"] is not None:
        return (f"'{found['label']}': visible_children_count raised "
                f"{found['visible_error']} for a raw return of {found['raw']!r}; it is "
                f"documented to return that number and not raise (#191)")

    if found["visible"] != found["raw"]:
        return (f"'{found['label']}': the property returned {found['visible']!r} while the "
                f"raw call returned {found['raw']!r}; they are not the same call")
    return None


def finding_for(raw) -> str:
    """What the painted panel's raw value says about the contract, in one sentence."""
    if raw == DOCUMENTED_ERROR:
        return ("the bridge answered -1, the documented error, which contradicts what #191 "
                "measured and means the property now returns -1 as a count -- a refusal a "
                "caller cannot see")
    if raw == 0:
        return ("the bridge answers 0 and never -1, so there is no sentinel to detect a "
                "refusal with: visible_children_count returns that 0 unchanged, and "
                "children_count is what says whether the read succeeded")
    return (f"the bridge answers {raw!r}, which is neither 0 nor the documented -1; the "
            f"property returns it unchanged, and what a refusal looks like on this JVM has "
            f"to be re-measured")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true",
                        help="the application is already running")
    parser.add_argument("--timeout", type=int, default=30,
                        help="How long to wait for the window, in seconds (default 30)")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("This needs Windows: it asks the Java Access Bridge about a live window.")
        return 2

    from pyjab.jabdriver import JABDriver

    proc = None
    failures: List[str] = []

    if not args.no_launch:
        if not compile_test_app():
            return 2
        proc = launch()
        if proc is None:
            return 2

    try:
        print("\nthe control: is there a window to measure at all?")
        print("-" * 49)
        windows = wait_for_window()
        if not windows:
            print("  INCONCLUSIVE no window appeared, so an empty answer below would mean")
            print("               nothing. Not evidence either way.")
            return 2
        print(f"  ok   found {len(windows)} window(s) without asking JAB anything")

        probes = []
        with JABDriver(title=WINDOW_TITLE, timeout=args.timeout) as driver:
            for name in (PAINTED_NAME, CONTROL_NAME):
                try:
                    element = driver.find_element_by_name(name)
                except Exception as error:                # noqa: BLE001 - reported
                    print(f"\n  INCONCLUSIVE '{name}' was not found: "
                          f"{type(error).__name__}: {error}")
                    print("               Nothing was measured. Not evidence either way.")
                    return 2
                probes.append(probe(element, name))

        painted, control = probes
        report(painted)
        report(control)

        print("\nthe control: does anything here report a non-zero visible count?")
        print("-" * 66)
        if isinstance(control["raw"], int) and control["raw"] > 0:
            print(f"  ok   {CONTROL_NAME!r} returned {control['raw']!r}, so a 0 for "
                  f"{PAINTED_NAME!r} is a real difference and not a bridge that always "
                  f"answers the same number")
        else:
            print(f"  FAIL {CONTROL_NAME!r} returned {control['raw']!r}; a control that "
                  f"cannot show a non-zero count makes the painted panel's value "
                  f"uninterpretable")
            failures.append(f"the control returned {control['raw']!r}, not a non-zero count")

        if painted["raw"] is not None and painted["raw"] == control["raw"]:
            failures.append("both elements returned the same raw value, so this run "
                            "distinguishes nothing")

        for found in probes:
            problem = disagreement(found)
            if problem is not None:
                failures.append(problem)

        print("\nthe one that matters: what did the bridge actually return?")
        print("-" * 57)
        if painted["raw"] is None:
            print(f"  INCONCLUSIVE the raw call failed: {painted['raw_error']}")
            return 2
        print(f"  {PAINTED_NAME!r:18} raw getVisibleChildrenCount -> {painted['raw']!r}")
        print(f"  {CONTROL_NAME!r:18} raw getVisibleChildrenCount -> {control['raw']!r}")
        finding = finding_for(painted["raw"])
        print(f"\n  FINDING: {finding} (#191)")

        print()
        if failures:
            print("FAILED: " + "; ".join(failures))
            return 1
        print(f"PASSED: visible_children_count matched the raw return for both elements and "
              f"did not raise -- {finding}")
        return 0
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
