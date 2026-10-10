from __future__ import annotations

import itertools
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pyjab.jabdriver import JABDriver

# The GUI test modules import :mod:`pyjab.jabdriver` at module scope, which pulls
# in pywin32, and they need a real JDK, a real Swing application and an
# interactive desktop session.  They are therefore opt-in everywhere:
#
#     PYJAB_RUN_GUI_TESTS=1 pytest tests/
#
# Without that variable only the platform independent tests get collected.
GUI_TEST_MODULES = [
    "test_bridge_dll.py",
    "test_bug_fix.py",
    "test_components.py",
    "test_message_pump_gui.py",
    "test_regression_gaps.py",
]

collect_ignore: list[str] = []
if sys.platform != "win32" or os.environ.get("PYJAB_RUN_GUI_TESTS") != "1":
    collect_ignore += GUI_TEST_MODULES

# ---------------------------------------------------------------------------
# The Swing application the GUI tests drive
# ---------------------------------------------------------------------------
#
# These tests used to download 27 demo applets from docs.oracle.com and drive
# those.  That made the suite depend on a third party staying online and on the
# exact widget names inside somebody else's demos, and it needed an interactive
# Java Web Start.  The application is now in this repository, in tests/java, and
# is compiled on demand with the JDK's javac.

JAVA_SRC_DIR = Path(__file__).resolve().parent / "java"
JAVA_CLASSES_DIR = JAVA_SRC_DIR / "classes"

TEST_APP_CLASS = "PyjabTestApp"
TEST_APP_TITLE = "PyjabTestApp"

#: Makes each launch's window title unique, so a window left behind by an
#: earlier run can never be bound by mistake.  See the test_app fixture.
_TITLE_COUNTER = itertools.count(1)

#: Pinned so that assertions on component names do not depend on the language of
#: the machine running the tests.
#:
#: Swing builds some labels from resource bundles.  A colour chooser's page tabs
#: are ``HSV``, ``HSL``, ``RGB``, ``CMYK`` under an English locale, and
#: ``HSV(H)``, ``HSL(L)``, ``RGB(G)``, ``CMYK`` plus a localised ``Swatches``
#: under any other -- verified on this project by running the same probe with and
#: without these arguments.  A locator written as ``@name='HSV'`` therefore
#: passes or fails depending on where the test runs, which is not a property
#: anybody wants to debug.
JAVA_LOCALE_ARGS = ["-Duser.language=en", "-Duser.country=US"]


def find_java_tool(name: str) -> str:
    """Locate ``javac`` or ``java``.

    ``JAVA_HOME`` first, then the PATH.  Raises with something actionable rather
    than letting a bare FileNotFoundError surface, because the usual cause is
    "a JRE is installed, not a JDK", which looks identical from the outside.
    """
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / (name + (".exe" if os.name == "nt" else ""))
        if candidate.exists():
            return str(candidate)

    found = shutil.which(name)
    if found:
        return found

    raise RuntimeError(
        f"could not find '{name}'.\n"
        "  The GUI tests need a JDK (not just a JRE) on the PATH or in JAVA_HOME.\n"
        "  On Windows the Temurin or Oracle JDK installers both provide it.\n"
        f"  JAVA_HOME is currently {java_home!r}."
    )


def java_sources() -> list[Path]:
    return sorted(JAVA_SRC_DIR.glob("*.java"))


def needs_compiling() -> bool:
    """True when any source is newer than the compiled class, or missing."""
    compiled = JAVA_CLASSES_DIR / (TEST_APP_CLASS + ".class")
    if not compiled.exists():
        return True
    newest_source = max(source.stat().st_mtime for source in java_sources())
    return newest_source > compiled.stat().st_mtime


@pytest.fixture(scope="session")
def test_application_classes() -> Path:
    """Compile tests/java/*.java and return the directory holding the classes."""
    sources = java_sources()
    if not sources:
        pytest.fail(f"no Java sources found in {JAVA_SRC_DIR}")

    if not needs_compiling():
        return JAVA_CLASSES_DIR

    javac = find_java_tool("javac")
    JAVA_CLASSES_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [javac, "-d", str(JAVA_CLASSES_DIR)] + [str(source) for source in sources],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            "compiling the test application failed\n"
            f"  command: {javac} -d {JAVA_CLASSES_DIR} {' '.join(s.name for s in sources)}\n"
            f"  stdout:\n{result.stdout}\n"
            f"  stderr:\n{result.stderr}"
        )
    return JAVA_CLASSES_DIR


@pytest.fixture(scope="session")
def test_application(test_application_classes: Path) -> str:
    """Launch the test application once for the whole GUI run.

    It used to be launched per test, and starting a JVM and waiting for its
    window dominates a run that is otherwise a few seconds of work.  One
    application now serves every test; the fixture yields its window title.

    The application is started here rather than through ``JABDriver(file_path=)``
    because that parameter takes a single executable path and cannot express
    ``java -cp <dir> PyjabTestApp``.  Starting the process and binding to it by
    title is also the arrangement the documentation recommends.

    The title is unique per run.  Binding by a fixed title means a window left
    behind by an earlier run can be matched instead of this one, and the tests
    then inspect a window whose buttons are already in whatever state the
    previous run left them.
    """
    java = find_java_tool("java")
    title = "{}-{}".format(TEST_APP_TITLE, next(_TITLE_COUNTER))
    process = subprocess.Popen(
        [java] + JAVA_LOCALE_ARGS
        + ["-cp", str(test_application_classes), TEST_APP_CLASS, "--title=" + title],
    )
    try:
        yield title
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                process.kill()


@pytest.fixture
def test_app(test_application: str) -> "JABDriver":
    """Bind a driver to the application the session started.

    A fresh driver per test, but *not* a fresh JVM.  Deliberately not a context
    manager: ``JABDriver.__exit__`` stops the bound process by pid, which would
    kill the application every later test is still using.  The session fixture
    owns the process and stops it once, at the end.

    Naming a pyjab test after this fixture is what keeps it in the GUI layer --
    every test that uses it needs the application, and therefore needs a JDK.
    """
    from pyjab.jabdriver import JABDriver

    return JABDriver(title=test_application, timeout=60)
