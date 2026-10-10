"""Does the bridge answer ``0`` or ``-1`` when it refuses ``getVisibleChildrenCount``?

Issue #191 asks one question and holds two answers that cannot both be true.

``JABElement.visible_children_count`` refuses the count when the bridge refuses the call,
with the check ``if not result:``. The JAB header documents ``getVisibleChildrenCount`` as
returning **``-1`` on error**, which makes that check wrong in both directions:

* a refusal returning ``-1`` is **truthy**, so ``if not result:`` lets it through and the
  property **returns ``-1`` as a count** rather than raising;
* a **legitimate count of ``0``** is falsy, so ``if not result:`` **raises** on an element
  that simply has no children.

A GUI run measured one half of that: a ``JPanel`` that paints its own content and has no
child components made ``visible_children_count`` **raise**. Under the current code a raise
means the return was falsy -- i.e. ``0``, not ``-1``. So an inference from a raise contradicts
the documented sentinel, and **nobody has read the raw number**, because the property is
what raises and the raise is what hides it.

So this tool calls the bridge function **directly** -- the same symbol with the same
arguments the property passes, through the ``getVisibleChildrenCount`` registration in
``pyjab/jabfixedfunc.py`` -- and prints the raw return for two elements:

1. **"Painted panel"** -- the childless self-painting ``JPanel`` in
   ``tests/java/PyjabTestApp.java``, the element whose ``visible_children_count`` raises
   today. What matters is the number underneath, so this never goes through the property.
2. **"Main panel"** -- the **control**, a panel that really does have children. Without it,
   a bridge that answered one number for everything would look exactly like an answer.

It also prints ``children_count`` beside the raw value, and whether
``visible_children_count`` returned a number or raised, so one run says everything #191
needs: the total the bridge reports, the visible count it refuses to report, and the raw
return the refusal is made of.

**This measures and does not fix.** ``pyjab/jabelement.py`` is deliberately untouched: which
of the two checks is the wrong one depends on the number this prints.

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

#: The element whose visible count is refused (or is a genuine zero -- that is the question).
PAINTED_NAME = "Painted panel"
#: The control: a panel with children, so a raw number here has to be non-zero.
CONTROL_NAME = "Main panel"

#: The two sentinels #191 is choosing between. ``-1`` is what the JAB header documents;
#: ``0`` is what the raise on the painted panel implies.
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
    """Everything #191 needs about one element, without anything raising out of here.

    **The raw call is made before ``visible_children_count``.** That property is the thing
    under test and it raises, so asking it first would let the raise hide the number this
    tool exists to read.
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
    """Whether the property and the direct call can be the same call.

    ``visible_children_count`` raises exactly when the raw return is falsy, because its
    check is ``if not result:``. If the two disagree about one element, this tool is not
    measuring the call the property makes and the run says nothing.
    """
    if found["raw_error"] is not None:
        return (f"the direct call for '{found['label']}' itself raised: "
                f"{found['raw_error']}")

    if found["visible_error"] is not None:
        if found["raw"]:
            return (f"'{found['label']}': the raw value {found['raw']!r} is truthy, so "
                    f"visible_children_count's 'if not result:' should not have raised, "
                    f"but it did")
    elif found["visible"] != found["raw"]:
        return (f"'{found['label']}': the property returned {found['visible']!r} while the "
                f"raw call returned {found['raw']!r}; they are not the same call")
    return None


def finding_for(raw) -> str:
    """What the painted panel's raw value decides, in one sentence."""
    if raw == DOCUMENTED_ERROR:
        return ("the bridge answers -1 for the childless panel, so the header contract is "
                "what this JVM does and 'if not result:' would return -1 as a count instead "
                "of raising")
    if raw == 0:
        return ("the bridge answers 0 and never -1, so 'if not result:' cannot tell a "
                "refusal from a legitimate zero -- and the childless panel is the "
                "legitimate zero it raises on")
    return (f"the bridge answers {raw!r}, which is neither documented sentinel, so neither "
            f"guard is right about this element")


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
        print(f"PASSED: the raw return was measured for both elements, and it settles "
              f"#191 -- {finding}")
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
