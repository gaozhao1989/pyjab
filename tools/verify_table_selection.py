"""Drive a real Java table and report what it actually does.

Needs Windows and a JDK.  Run it against the test application:

    python tools/verify_table_selection.py

The unit tests in ``tests/test_table_selection.py`` check that pyjab asks the
bridge for the right things.  They cannot check what a real Swing table answers,
because GitHub runners have no interactive desktop and no Java table -- see
AGENTS.md 1.1.  This script exists for that half: it drives
``tests/java/PyjabTestApp.java``'s "Sports table" and prints what the application
reports, so the answers can be read rather than assumed.

**It reports, it does not judge.**  Every scenario prints what came back and
whether it matched what pyjab's documentation promises.  Some of the answers are
genuinely open questions -- whether Swing reports a whole *row* as selected after
its cells are added, for instance, which is #57 -- so a mismatch there is a fact
to look at rather than a bug to file.

The table in the test application is a plain ``JTable``, which defaults to
``rowSelectionAllowed=true`` and ``cellSelectionEnabled=false``.  That is worth
knowing while reading the output: with cell selection off, selecting one cell
selects the row it is in, because that is what Swing does.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# `python tools/verify_table_selection.py` puts tools/ on sys.path, not the
# checkout, so `import pyjab` fails unless pyjab happens to be installed.  The
# older scripts get away with that because the documented setup installs the
# package first; this works either way, which is what makes it runnable from a
# fresh clone.
sys.path.insert(0, str(REPO_ROOT))

JAVA_SRC = REPO_ROOT / "tests" / "java" / "PyjabTestApp.java"
JAVA_CLASSES = Path("/tmp/pyjab-verify-classes")

WINDOW_TITLE = "PyjabTestApp"
TABLE_NAME = "Sports table"

#: What the application's table holds, from tests/java/PyjabTestApp.java.
EXPECTED = [
    ["Kathy", "Snowboarding", "5", "false"],
    ["John", "Rowing", "3", "true"],
    ["Sue", "Knitting", "2", "true"],
    ["Jane", "Speed reading", "5", "false"],
    ["Joe", "Pool", "10", "true"],
]


class Report:
    """Collects scenarios, and remembers which ones did not match."""

    def __init__(self) -> None:
        self.mismatches: list[str] = []
        self.observations: list[str] = []

    def scenario(self, number: int, title: str) -> None:
        print(f"\n[{number}] {title}")

    def observed(self, label: str, value) -> None:
        print(f"    {label} = {value!r}")
        self.observations.append(f"{label} = {value!r}")

    def expect(self, label: str, actual, wanted) -> bool:
        """Record a mismatch without stopping -- later scenarios still matter."""
        if actual == wanted:
            print(f"    OK: {label} is {wanted!r}")
            return True
        print(f"    MISMATCH: {label} is {actual!r}, documentation promises {wanted!r}")
        self.mismatches.append(f"{label}: got {actual!r}, expected {wanted!r}")
        return False


def compile_test_app() -> Path:
    """Compile the application, so a stale class file cannot be reported on."""
    import shutil

    javac = shutil.which("javac")
    if not javac:
        print("javac is not on the PATH. Run this from a JDK, not a JRE.")
        raise SystemExit(2)

    JAVA_CLASSES.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [javac, "-d", str(JAVA_CLASSES), str(JAVA_SRC)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("compiling the test application failed:")
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(2)
    print(f"compiled {JAVA_SRC.name} -> {JAVA_CLASSES}")
    return JAVA_CLASSES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=30,
                        help="Per-step timeout in seconds (default 30)")
    parser.add_argument("--no-launch", action="store_true",
                        help="Use an application that is already running")
    args = parser.parse_args()

    try:
        import pyjab
        from pyjab.common.by import By
        from pyjab.common.exceptions import JABException
        from pyjab.jabdriver import JABDriver
    except ImportError as exc:
        # pyjab.jabdriver raises a descriptive ImportError off Windows, before it
        # touches pywin32.  Letting it out raw would bury that message in a
        # traceback, which is what it exists to avoid.
        print(f"This needs Windows.\n\n{exc}")
        return 2

    print(f"pyjab version : {pyjab.__version__}")
    print(f"python        : {sys.version.split()[0]} ({sys.platform})")

    classes = compile_test_app() if not args.no_launch else JAVA_CLASSES
    process = None
    if not args.no_launch:
        process = subprocess.Popen(
            ["java", "-cp", str(classes), "PyjabTestApp"],
        )
        time.sleep(3.0)

    report = Report()
    try:
        with JABDriver(title=WINDOW_TITLE, timeout=args.timeout) as driver:
            run(driver, report, args.timeout)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()

    print("\n" + "=" * 62)
    if report.mismatches:
        print(f"RESULT: {len(report.mismatches)} MISMATCH(ES)")
        for line in report.mismatches:
            print(f"  - {line}")
    else:
        print("RESULT: every scenario matched what the documentation promises")
    print("=" * 62)
    print("\nPaste this whole output back -- the observations are the point.")
    return 1 if report.mismatches else 0


def run(driver, report: Report, timeout: int) -> None:
    from pyjab.common.exceptions import JABException

    report.scenario(1, "Find the table")
    try:
        table = driver.find_element_by_name(TABLE_NAME)
        report.observed("role", table.role_en_us)
        report.observed("name", table.name)
    except JABException as exc:
        print(f"    FAILED: {exc}")
        report.mismatches.append(f"the table '{TABLE_NAME}' was not found: {exc}")
        return

    report.scenario(2, "What the table reports about itself")
    info = table.table
    report.observed("row_count", info["row_count"])
    report.observed("column_count", info["column_count"])
    report.expect("row_count", info["row_count"], len(EXPECTED))
    report.expect("column_count", info["column_count"], len(EXPECTED[0]))
    report.observed("accessible_selection", table.accessible_selection)
    report.observed("accessible_action", table.accessible_action)
    print("    (a table must expose selection -- that interface is the only way in)")
    report.expect("accessible_selection", table.accessible_selection, True)

    report.scenario(3, "get_cell() reads the cell list")
    for row in range(len(EXPECTED)):
        got = [table.get_cell(row, column).text for column in range(len(EXPECTED[0]))]
        report.expect(f"row {row}", got, EXPECTED[row])

    report.scenario(4, "Nothing is selected to begin with")
    report.observed("selected_rows", table.selected_rows)
    report.observed("selected_columns", table.selected_columns)
    report.observed("selected_row_count", table.selected_row_count)
    elements = table.get_selected_elements()
    report.observed("get_selected_elements()", [e.name for e in elements])
    for element in elements:
        element.release_jabelement()

    report.scenario(5, "select_row(1)  <-- the question #57 asks")
    print("    Swing defaults to row selection, so this should be the clean case.")
    table.select_row(1)
    time.sleep(0.3)
    report.observed("selected_rows", table.selected_rows)
    report.observed("selected_row_count", table.selected_row_count)
    report.observed("is_row_selected(1)", table.is_row_selected(1))
    report.observed("is_row_selected(0)", table.is_row_selected(0))
    report.observed("selected_columns", table.selected_columns)
    report.expect("is_row_selected(1)", table.is_row_selected(1), True)
    report.expect("is_row_selected(0)", table.is_row_selected(0), False)
    elements = table.get_selected_elements()
    report.observed("get_selected_elements()", [e.name for e in elements])
    report.observed("  their text", [e.text for e in elements])
    for element in elements:
        element.release_jabelement()

    report.scenario(6, "select_cell(2, 1)")
    print("    With cellSelectionEnabled=false Swing selects the whole row.")
    table.select_cell(2, 1)
    time.sleep(0.3)
    report.observed("selected_rows", table.selected_rows)
    report.observed("selected_columns", table.selected_columns)
    report.observed("is_row_selected(2)", table.is_row_selected(2))

    report.scenario(7, "select_column(0)  <-- Swing-only-column selection is off")
    table.select_column(0)
    time.sleep(0.3)
    report.observed("selected_rows", table.selected_rows)
    report.observed("selected_columns", table.selected_columns)
    report.observed("is_column_selected(0)", table.is_column_selected(0))
    print("    Not a failure if this selects nothing: with cell selection off a")
    print("    Swing table has no column selection to add cells to.")

    report.scenario(8, "select_all()")
    table.select_all()
    time.sleep(0.3)
    report.observed("selected_row_count", table.selected_row_count)
    report.observed("selected_rows", table.selected_rows)

    report.scenario(9, "clear_selection()")
    table.clear_selection()
    time.sleep(0.3)
    report.observed("selected_rows", table.selected_rows)
    report.expect("selected_rows", table.selected_rows, [])

    report.scenario(10, "get_visible_children()")
    children = table.get_visible_children()
    report.observed("count", len(children))
    report.observed("first five names", [c.name for c in children[:5]])
    report.expect("count", len(children), len(EXPECTED) * len(EXPECTED[0]))
    for child in children:
        child.release_jabelement()

    report.scenario(11, "select() on a table explains itself  <-- the old KeyError")
    try:
        table.select("Kathy")
        print("    FAILED: select() did not raise")
        report.mismatches.append("select() on a table did not raise")
    except JABException as exc:
        report.observed("JABException", str(exc))
        if "select_cell" not in str(exc):
            report.mismatches.append("select()'s message does not name select_cell()")
    except KeyError as exc:
        print(f"    FAILED: still a KeyError: {exc!r}")
        report.mismatches.append("select() on a table still raises KeyError")


if __name__ == "__main__":
    sys.exit(main())
