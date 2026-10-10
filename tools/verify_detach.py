"""Does detach really let go without killing, and does exiting still kill?

The requirement — pyjab-mcp's `detach` — is one sentence: release a bound window **without
terminating its process**. `__exit__` sends `SIGTERM` to the bound pid, which is right for an
application pyjab launched and wrong for one it only attached to.

`hasattr(JABDriver, "detach")` would prove nothing, so the check is behavioural and needs
**two** applications:

* attach to one, detach, and assert **it is still running** — the requirement;
* attach to another, leave the block without detaching, and assert **it is gone** — which is
  what makes the first assertion mean something. Without it, "still running" would pass just
  as well if `__exit__` had stopped killing anything at all.

Two instances rather than one because the second assertion kills its subject.

Both applications are launched with **plain subprocess**, so pyjab only ever attaches. A
driver pyjab launched itself is the case `__exit__` was already right for, and testing that
would not be testing this.
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


def compile_test_app() -> bool:
    javac = shutil.which("javac")
    if not javac:
        print("javac is not on the PATH. Run this from a JDK, not a JRE.")
        return False
    JAVA_CLASSES.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [javac, "-d", str(JAVA_CLASSES), *sorted(str(p) for p in JAVA_SRC.glob("*.java"))],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("compiling the test application failed:")
        print(result.stdout, result.stderr)
        return False
    return True


def launch(title: str) -> Optional[subprocess.Popen]:
    java = shutil.which("java")
    if not java:
        print("java is not on the PATH.")
        return None
    return subprocess.Popen(
        [java, "-cp", str(JAVA_CLASSES), APP_CLASS, f"--title={title}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def alive(process: subprocess.Popen) -> bool:
    """Whether the process is still running, reaping it if it has exited."""
    return process.poll() is None


def wait_for_window(title: str, timeout: float = 60.0):
    from pyjab.common.win32utils import Win32Utils

    win32 = Win32Utils()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if matches := win32.get_hwnds_by_title(f"*{title}*"):
            return matches
        time.sleep(0.5)
    return []


def settle(seconds: float = 2.0) -> None:
    """Give a terminated process time to actually be terminated.

    `SIGTERM` is delivered, not synchronised: asserting "gone" immediately after leaving a
    `with` block is a race, and a flaky check is worse than none.
    """
    time.sleep(seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true",
                        help="both applications are already running")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("This needs Windows: it sends real signals to real processes.")
        return 2

    from pyjab.jabdriver import JABDriver

    failures: List[str] = []
    processes: List[subprocess.Popen] = []

    print("\nthe API exists")
    print("-" * 14)
    print(f"  {'ok  ' if hasattr(JABDriver, 'detach') else 'FAIL'} JABDriver.detach")
    if not hasattr(JABDriver, "detach"):
        failures.append("no detach")

    if not args.no_launch:
        if not compile_test_app():
            return 2
        for title in ("PyjabDetach", "PyjabExit"):
            if (process := launch(title)) is None:
                return 2
            processes.append(process)
    if len(processes) != 2 and not args.no_launch:
        return 2

    try:
        print("\nthe control: both applications are up")
        print("-" * 37)
        for title, process in zip(("PyjabDetach", "PyjabExit"), processes):
            windows = wait_for_window(title)
            if not windows or not alive(process):
                print(f"  INCONCLUSIVE {title} did not come up. Not evidence either way.")
                return 2
            print(f"  ok   {title}: pid {process.pid}, window {windows[0]}")

        print("\nthe requirement: detach leaves the process running")
        print("-" * 48)
        detach_pid = processes[0].pid
        driver = JABDriver(title="PyjabDetach")
        print(f"  attached to PyjabDetach (pid {detach_pid}); driver.pid={driver.pid}")
        driver.detach()
        print(f"  called detach(); driver.pid={driver.pid}")
        # Leaving the block afterwards must not kill either -- that is what forgetting the
        # pid buys, and it is the part a caller actually relies on.
        driver.__exit__(None, None, None)
        settle()
        still = alive(processes[0])
        print(f"  {'ok  ' if still else 'FAIL'} PyjabDetach is still running after "
              f"detach() and __exit__(): {still}")
        if not still:
            failures.append("detach, or the exit after it, terminated the process")

        print("\nthe counter-example: exiting without detaching still kills")
        print("-" * 55)
        exit_pid = processes[1].pid
        with JABDriver(title="PyjabExit") as other:
            print(f"  attached to PyjabExit (pid {exit_pid}); driver.pid={other.pid}")
        settle()
        gone = not alive(processes[1])
        print(f"  {'ok  ' if gone else 'FAIL'} PyjabExit is gone after leaving the with "
              f"block: {gone}")
        if not gone:
            failures.append(
                "exiting without detaching no longer terminates the process, so the test "
                "above proves nothing"
            )

        print()
        if failures:
            print("FAILED: " + "; ".join(failures))
            return 1
        print("PASSED: detach released the window and left the application running, while "
              "an ordinary exit still terminated its own")
        return 0
    finally:
        for process in processes:
            if alive(process):
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    sys.exit(main())
