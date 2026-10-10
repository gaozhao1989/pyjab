"""Does pyjab find a running JVM's own bridge DLL, before it loads any DLL?

The feature this checks (see the changelog for 1.9.0) exists for one case: an application
bundled with its own private JRE, in a directory no install-location search would guess.
That application is running, so it can be asked.

**The ordering is the whole point, and it is why this script must not use pyjab to start
the application.** The DLL has to be located *before* it is loaded, because loading it is
what makes `isJavaWindow` possible -- so a script that let pyjab launch the app would have
loaded a DLL already and would be testing nothing. The app is started with plain subprocess
here, exactly as it would be in real life, and only then is pyjab asked where the JVM is.

**A control, because an empty answer has two meanings.** `java_process_image_paths()`
returning nothing could mean "the search is broken" or "there was no window to find". The
M0 verification in this repository shipped without a control once and reported the answer
that flattered the feature; this one asserts the window was found *first*, so an empty
result is a failure rather than a shrug.
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
    """Wait for the window using Win32 only. No JAB, and therefore no DLL.

    This is the same call the feature itself uses, which is the point: if this cannot find
    the window, neither can the feature, and the run is inconclusive rather than passing.
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true",
                        help="the application is already running")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("This needs Windows: it asks Win32 about running processes.")
        return 2

    from pyjab.common.win32utils import Win32Utils
    from pyjab.config import bridge_dirs_from_image

    proc = None
    failures: List[str] = []

    if not args.no_launch:
        if not compile_test_app():
            return 2
        proc = launch()
        if proc is None:
            return 2

    try:
        print("\nthe control: is there a window to find at all?")
        print("-" * 46)
        windows = wait_for_window()
        if not windows:
            print("  INCONCLUSIVE no window appeared, so an empty result below would mean")
            print("               nothing. Not evidence either way.")
            return 2
        print(f"  ok   found {len(windows)} window(s) without loading any DLL")

        print("\nthe feature: which JVMs can be seen?")
        print("-" * 26)
        images = Win32Utils().java_process_image_paths()
        print(f"  {'ok  ' if images else 'FAIL'} java_process_image_paths() -> {images}")
        if not images:
            failures.append("no JVM image paths")
        for image in images:
            if not image.lower().endswith(("\\java.exe", "\\javaw.exe")):
                failures.append(f"not a JVM executable: {image}")

        print("\nthe directories those JVMs imply")
        print("-" * 34)
        dirs: List[Path] = []
        for image in images:
            for directory in bridge_dirs_from_image(image):
                if directory not in dirs:
                    dirs.append(directory)
        for directory in dirs:
            dll = directory / "WindowsAccessBridge-64.dll"
            print(f"  {'ok  ' if dll.is_file() else '..  '} {directory}")
            print(f"       bridge DLL present: {dll.is_file()}")

        if not any((d / "WindowsAccessBridge-64.dll").is_file() for d in dirs):
            failures.append("none of the derived directories holds the bridge DLL")

        print("\nthe pairing: is it the JVM we actually started?")
        print("-" * 44)
        # The launched process's own image path, from the pid. If the feature found the
        # right JVM, its answer contains this.
        launched = Win32Utils()._process_image_path(proc.pid) if proc else None
        print(f"  the process we started: {launched}")
        if launched:
            matched = any(
                str(d).lower() == str(Path(launched).parent).lower() for d in dirs
            )
            print(f"  {'ok  ' if matched else 'FAIL'} that JVM's own bin is among the "
                  f"candidates: {matched}")
            if not matched:
                failures.append("the started JVM's own directory was not among the results")

        print()
        if failures:
            print("FAILED: " + "; ".join(failures))
            return 1
        print("PASSED: a running JVM's own bridge directory was found without loading a DLL")
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
