"""Check that the GUI suite's locators resolve in the test application.

The GUI suite can only run on Windows with a desktop session, so on every other
machine -- and in CI -- nothing checked whether the components it looks for
actually exist with the names and roles it expects.  That gap let a whole batch
of locators reach a user's machine broken: they named components through
``setName()``, which is not the property Java Access Bridge reads, so a lookup
found nothing or found a label that happened to carry the same text.

This closes the gap.  ``PyjabTestApp --dump-accessibility`` prints the
accessibility name and role of every element, and the accessibility layer is a
JVM-side API -- identical on every platform -- so what it prints here is what
Java Access Bridge will report on Windows.  Run this before running the suite.

    python tools/verify_test_app.py

Only a JDK is needed, found through ``JAVA_HOME`` or the PATH.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_DIR = REPO_ROOT / "tests" / "java"
APP_CLASS = "PyjabTestApp"

#: (name, expected role) for everything the GUI suite locates by name or role.
#: Keep this in step with tests/test_components.py, test_bug_fix.py and
#: test_message_pump_gui.py -- it is the contract between them and the app.
REQUIRED = [
    ("A Label", "label"),
    ("Disable middle button", "push button"),
    ("Middle button", "push button"),
    ("Enable middle button", "push button"),
    ("Show dialog", "push button"),
    ("Show alert", "push button"),
    ("Show color chooser", "push button"),
    ("Show popup", "push button"),
    ("Toolbar Button", "push button"),
    ("Chin", "check box"),
    ("Hair", "check box"),
    ("Cat", "radio button"),
    ("Dog", "radio button"),
    ("Animals combo box", "combo box"),
    ("Names list", "list"),
    ("1122233455", "text"),
    ("Text area contents", "text"),
    ("password", "password text"),
    ("Sports table", "table"),
    ("Tree", "tree"),
    ("First slider", "slider"),
    ("Second slider", "slider"),
    ("Year", "spinbox"),
    ("Progress bar", "progress bar"),
    ("A Menu", "menu"),
    ("Another Menu", "menu"),
    ("Another one", "menu item"),
    ("A check box menu item", "check box"),
    ("Last one", "menu item"),
    ("Third item", "menu item"),
    # Tree rows are named from the model, not by setName, so they are worth
    # checking too -- naming the shared cell renderer silently flattens them all.
    ("Root", "label"),
    ("Child one", "label"),
    ("Child one leaf A", "label"),
    ("Child two", "label"),
]

ROLES_ONLY = [
    "frame",
    "root pane",
    "layered pane",
    "panel",
    "internal frame",
    "split pane",
    "tool bar",
    "progress bar",
    # pyjab spells this role as one word, matching what Swing reports.
    "viewport",
    "scroll pane",
    "menu bar",
    "separator",
]

#: Locators that only exist once a dialog is open, so they cannot appear in a
#: dump of the startup window.  Listed so the omission is deliberate and
#: visible rather than an accident.
DIALOG_ONLY = [
    ("A Dialog", "dialog"),
    ("Dialog label", "label"),
    ("Close dialog", "push button"),
    ("An Alert", "dialog"),
    ("Alert message", "label"),
    ("A Color Chooser", "dialog"),
    # Roles the dialog tests look up instead of names.
    "alert",
    "color chooser",
    "page tab list",
]

ENTRY = re.compile(r"^\s*name=(?P<name>.*?)\s\srole=(?P<role>.*?)\s*$")


def find_tool(name: str) -> str:
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / (name + (".exe" if os.name == "nt" else ""))
        if candidate.exists():
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    sys.exit(
        f"could not find '{name}'.\n"
        "  A JDK (not just a JRE) is needed, on the PATH or in JAVA_HOME."
    )


def compile_app(javac: str, out_dir: Path) -> None:
    sources = sorted(JAVA_DIR.glob("*.java"))
    if not sources:
        sys.exit(f"no Java sources in {JAVA_DIR}")
    result = subprocess.run(
        [javac, "-Xlint:all", "-d", str(out_dir)] + [str(s) for s in sources],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stderr.strip():
        print("compiling the test application failed:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)


def dump(java: str, classes: Path) -> str:
    result = subprocess.run(
        [java, "-Duser.language=en", "-Duser.country=US",
         "-cp", str(classes), APP_CLASS, "--dump-accessibility"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print("the application refused to dump its accessibility tree:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
    return result.stdout


def parse(text: str):
    """Return {(name, role)} and {role} from a dump."""
    named, roles = set(), set()
    for line in text.splitlines():
        match = ENTRY.match(line)
        if match:
            named.add((match.group("name"), match.group("role")))
            roles.add(match.group("role"))
    return named, roles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true",
                        help="keep the compiled classes instead of using a temp dir")
    args = parser.parse_args()

    javac, java = find_tool("javac"), find_tool("java")

    if args.keep:
        classes = JAVA_DIR / "classes"
        classes.mkdir(parents=True, exist_ok=True)
        cleanup = None
    else:
        cleanup = tempfile.TemporaryDirectory()
        classes = Path(cleanup.name)

    try:
        compile_app(javac, classes)
        named, roles = parse(dump(java, classes))
    finally:
        if cleanup is not None:
            cleanup.cleanup()

    print(f"{len(named)} named elements, {len(roles)} distinct roles\n")

    problems = []
    for name, role in REQUIRED:
        if (name, role) in named:
            continue
        found_roles = sorted(r for n, r in named if n == name)
        if found_roles:
            problems.append(f"{name!r} exists but with role {found_roles}, expected {role!r}")
        else:
            problems.append(f"{name!r} is not present at all")

    for role in ROLES_ONLY:
        if role not in roles:
            problems.append(f"no element reports role {role!r}")

    if problems:
        print("FAILED")
        for problem in problems:
            print(f"  - {problem}")
        print(
            "\nEvery one of these is a locator used by the GUI suite, so the suite\n"
            "will fail on Windows for the same reasons. Fix the application's\n"
            "accessibility names (see applyAccessibleNames in PyjabTestApp.java),\n"
            "or change the locator."
        )
        return 1

    print("PASSED")
    print(f"  checked {len(REQUIRED)} names with their roles, "
          f"and {len(ROLES_ONLY)} roles by themselves")
    print("\n  Not checked here, because they only exist once a dialog is open:")
    for entry in DIALOG_ONLY:
        print(f"    {entry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
