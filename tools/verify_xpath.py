"""Verify the xpath locators on a real Java application, on Windows.

    python tools/verify_xpath.py

The locators themselves are already tested against the real application's
accessibility tree (tests/test_xpath_real_tree.py), and that runs everywhere. What it
cannot cover is the **transport**: it reads the tree from the application's own
accessibility API, so it says nothing about what Java Access Bridge reports, how many
round trips a locator costs, or whether a click lands.

Those need this, and this needs Windows with a desktop session:

* **what JAB reports**, not what the application says about itself. The roles are
  ``role_en_us`` and the attribute values -- ``indexinparent``, ``childrencount``,
  ``objectdepth`` -- are JAB's, and no amount of reading the JVM-side tree proves
  they agree;
* **``getAccessibleParentFromContext``**, which `..` uses and which the fake bridge
  can only pretend to implement;
* **the click landing**, which needs a real desktop;
* **the cost**, in actual cross-process calls, of a path that walks a real tree.

Nothing here modifies the application. It exits non-zero if a scenario does not do
what it should, so the output can be pasted back as evidence.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_SRC = REPO_ROOT / "tests" / "java"
JAVA_CLASSES = JAVA_SRC / "classes"
APP_CLASS = "PyjabTestApp"
WINDOW_TITLE = "PyjabTestApp"


class Report:
    """Counts what did not hold, and prints everything either way."""

    def __init__(self) -> None:
        self.checks = 0
        self.failures = []

    def section(self, title: str) -> None:
        print(f"\n{title}")
        print("-" * len(title))

    def check(self, label: str, actual, expected, why: str = "") -> bool:
        self.checks += 1
        held = actual == expected
        mark = "ok  " if held else "FAIL"
        print(f"  {mark} {label}")
        print(f"       actual   {actual!r}")
        if not held:
            print(f"       expected {expected!r}")
        if why:
            print(f"       {why}")
        if not held:
            self.failures.append(label)
        return held

    def holds(self, label: str, condition: bool, detail: str, why: str = "") -> bool:
        self.checks += 1
        print(f"  {'ok  ' if condition else 'FAIL'} {label}")
        print(f"       {detail}")
        if why:
            print(f"       {why}")
        if not condition:
            self.failures.append(label)
        return condition


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


def run(driver, report: Report) -> None:
    from pyjab.common.exceptions import JABException, XpathParserException

    # ------------------------------------------------------------------
    report.section("1. the transport works at all")
    # ------------------------------------------------------------------
    button = driver.find_element_by_xpath("//push button[@name='Disable middle button']")
    report.check("//push button[@name='Disable middle button'] finds it",
                 f"{button.role_en_us}:{button.name}",
                 "push button:Disable middle button",
                 "role_en_us is JAB's spelling, not the application's; the real-tree "
                 "test compares the application's own dump and cannot see this")

    # ------------------------------------------------------------------
    report.section("2. the attribute values are JAB's, and they are numbers")
    # ------------------------------------------------------------------
    buttons = driver.find_elements_by_xpath("//push button")
    report.holds("there is more than one push button in the window",
                 len(buttons) > 3, f"{len(buttons)} found",
                 "the rest of this section needs more than one")

    indexes = {b.index_in_parent for b in buttons}
    report.holds("index_in_parent comes back as ints, not strings",
                 all(isinstance(b.index_in_parent, int) for b in buttons),
                 f"types seen: {sorted({type(b.index_in_parent).__name__ for b in buttons})}",
                 "the numeric comparison rests on this; if JAB reported strings then "
                 "[@indexinparent>9] would have to be a string comparison")

    # A comparison the real values decide. `>=0` is always true for a real index, so
    # if it returns nothing the comparison is not being applied at all.
    every = driver.find_elements_by_xpath("//push button[@indexinparent>=0]")
    report.check("//push button[@indexinparent>=0] finds every button",
                 len(every), len(buttons),
                 "an index is never negative, so this has to match all of them; a "
                 "smaller number means the comparison is dropping some")

    # ------------------------------------------------------------------
    report.section("3. [n] counts within each parent")
    # ------------------------------------------------------------------
    firsts = driver.find_elements_by_xpath("//push button[1]")
    report.holds("//push button[1] returns fewer than //push button",
                 len(firsts) < len(buttons),
                 f"{len(firsts)} vs {len(buttons)}",
                 "if they are equal then no parent holds more than one button and "
                 "this window cannot show the difference -- say so rather than "
                 "reading it as a pass")
    report.holds("//push button[1] returns more than one",
                 len(firsts) > 1, f"{len(firsts)} found",
                 "one would mean the counter runs across the whole search instead of "
                 "per parent, which is the bug the unit test guards")

    # ------------------------------------------------------------------
    report.section("4. unions, without duplicates")
    # ------------------------------------------------------------------
    merged = driver.find_elements_by_xpath("//push button | //label")
    twice = driver.find_elements_by_xpath("//push button | //push button")
    report.holds("a union of two roles finds both",
                 len(merged) > len(buttons), f"{len(merged)} found")
    report.check("//push button | //push button is the same size as //push button",
                 len(twice), len(buttons),
                 "a node-set has no duplicates; larger means the same button came "
                 "back more than once")

    # ------------------------------------------------------------------
    report.section("5. .. uses getAccessibleParentFromContext")
    # ------------------------------------------------------------------
    parents = driver.find_elements_by_xpath("//label/..")
    report.holds("//label/.. finds at least one parent",
                 len(parents) > 0, f"{len(parents)} found",
                 "this is a real JAB call, not the fake bridge's bookkeeping")

    named = driver.find_elements_by_xpath(
        "//push button[@name='Disable middle button']/.."
    )
    report.holds("the parent of a known button is not itself a button",
                 all(p.role_en_us != "push button" for p in named),
                 f"roles: {[p.role_en_us for p in named]}",
                 "Disable middle button sits inside the Button column panel, so its "
                 "parent should be a panel -- a button here would mean the step went "
                 "sideways rather than up")

    # ------------------------------------------------------------------
    report.section("6. the cost of a real lookup")
    # ------------------------------------------------------------------
    start = time.monotonic()
    for _ in range(20):
        driver.find_element_by_xpath("//push button[@name='Disable middle button']")
    elapsed = (time.monotonic() - start) / 20
    report.holds("twenty lookups average under 100ms each",
                 elapsed < 0.1, f"{elapsed * 1000:.1f}ms each",
                 "a number worth having rather than passing or failing on: the walk "
                 "is the thing #33 was about")

    # ------------------------------------------------------------------
    report.section("7. the rejected forms are rejected before any JAB call")
    # ------------------------------------------------------------------
    for locator in ["//push button[0]", "//push button[last()]",
                    "//push button[position()=2]"]:
        try:
            driver.find_elements_by_xpath(locator)
            report.holds(f"{locator} is rejected", False, "it was accepted",
                         "a locator that cannot work must say so")
        except XpathParserException:
            report.holds(f"{locator} is rejected", True, "XpathParserException")

    # ------------------------------------------------------------------
    report.section("8. a locator that matches nothing fails as not-found")
    # ------------------------------------------------------------------
    try:
        driver.find_elements_by_xpath("//push button[@name='No Such Button']")
        report.holds("a missing element raises JABException", False, "nothing raised")
    except JABException:
        report.holds("a missing element raises JABException", True, "JABException")

    # ------------------------------------------------------------------
    report.section("9. the click lands, which needs a real desktop")
    # ------------------------------------------------------------------
    try:
        target = driver.find_element_by_xpath("//push button[@name='Middle button']")
        before = target.states_en_us
        disable = driver.find_element_by_xpath(
            "//push button[@name='Disable middle button']"
        )
        disable.click(simulate=True)
        time.sleep(0.5)
        after = target.states_en_us
        report.holds("clicking Disable changes the middle button's state",
                     before != after, f"{before} -> {after}",
                     "simulate=True moves the real mouse, so this is the only check "
                     "here that needs an actual desktop")
    except Exception as exc:                                  # pragma: no cover
        report.holds("the click scenario ran", False, f"{type(exc).__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true",
                        help="attach to an application that is already running")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    import pyjab

    print(f"pyjab version : {pyjab.__version__}")
    print(f"python        : {sys.version.split()[0]} ({sys.platform})")

    try:
        from pyjab.jabdriver import JABDriver
    except ImportError as exc:
        print(f"\nThis needs Windows.\n\n{exc}")
        return 2

    process = None
    if args.no_launch:
        print(f"\nattaching to a running {APP_CLASS} ...")
    else:
        if not compile_test_app():
            return 2
        # Launch it, which this tool used to announce without doing: it printed
        # "launching ..." and then waited for a window that nothing had started,
        # so the default path could only ever time out.  Only --no-launch
        # worked.  No --title is passed on purpose -- the default title is what
        # WINDOW_TITLE holds, and "--title NAME" is silently ignored because the
        # application matches the "--title=" prefix.
        print(f"\nlaunching {APP_CLASS} ...")
        process = subprocess.Popen(["java", "-cp", str(JAVA_CLASSES), APP_CLASS])
        time.sleep(3.0)

    report = Report()
    try:
        if args.no_launch:
            driver = JABDriver(title=WINDOW_TITLE, timeout=args.timeout)
            try:
                run(driver, report)
            finally:
                driver.__exit__(None, None, None)
        else:
            with JABDriver(title=WINDOW_TITLE, timeout=args.timeout) as driver:
                run(driver, report)
    finally:
        # The driver stops a process it is bound to, but it only exists once the
        # window was found.  On the failure path -- the interesting one -- this
        # is the only thing that stops the JVM this tool started.
        if process is not None and process.poll() is None:
            process.terminate()

    print("\n" + "=" * 62)
    if report.failures:
        print(f"RESULT: {len(report.failures)} FAILURE(S) out of {report.checks}")
        for line in report.failures:
            print(f"  - {line}")
    else:
        print(f"RESULT: all {report.checks} checks held")
    print("=" * 62)
    print("\nPaste this whole output back -- the numbers in it are the point.")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
