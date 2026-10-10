"""Does the GDI screen grab actually return the screen?

The failure this exists for is not an exception. ``grab_rect`` replaces Pillow's
``ImageGrab``, and the way it goes wrong is by returning a buffer of zeroes: a **black
image that opens perfectly**. That is indistinguishable from a window that happens to be
black, which is why it needs a check rather than a review.

So the assertion is not "the bytes decode" -- that would pass on an all-black frame -- but
"the bytes decode **and are not uniform**". A real window has a title bar, text and borders,
so its pixels vary. The decoder is ``pyjab.common.png.decode_png``, which is the same
standard-library-only path the feature itself uses.
"""

from __future__ import annotations

import argparse
import ctypes
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

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
    result = subprocess.run(
        [javac, "-d", str(JAVA_CLASSES), *sorted(str(p) for p in JAVA_SRC.glob("*.java"))],
        capture_output=True, text=True,
    )
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
    return subprocess.Popen(
        [java, "-cp", str(JAVA_CLASSES), APP_CLASS, f"--title={WINDOW_TITLE}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def wait_for_window(timeout: float = 60.0):
    from pyjab.common.win32utils import Win32Utils

    win32 = Win32Utils()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = win32.get_hwnds_by_title(f"*{WINDOW_TITLE}*")
        if matches:
            return matches
        time.sleep(0.5)
    return []


def window_rect(hwnd) -> Tuple[int, int, int, int]:
    """The window's rectangle, through plain Win32.

    Not through JAB: this is checking GDI, and taking the rectangle from the same layer
    would make a failure in that layer look like a failure in this one.
    """
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    rect = RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError(f"GetWindowRect failed for {hwnd}")
    return (rect.left, rect.top,
            rect.right - rect.left, rect.bottom - rect.top)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("This needs Windows: it reads the screen through GDI.")
        return 2

    from pyjab.common.png import decode_png
    from pyjab.common.win32utils import Win32Utils

    proc = None
    failures: List[str] = []
    if not args.no_launch:
        if not compile_test_app():
            return 2
        proc = launch()
        if proc is None:
            return 2

    try:
        print("\nthe control: is there a window to grab?")
        print("-" * 39)
        windows = wait_for_window()
        if not windows:
            print("  INCONCLUSIVE no window appeared. Not evidence either way.")
            return 2
        hwnd = windows[0]
        x, y, width, height = window_rect(hwnd)
        print(f"  ok   window {hwnd}, rectangle {x},{y} {width}x{height}")

        print("\nthe grab")
        print("-" * 14)
        buffer = Win32Utils().grab_rect(x, y, width, height)
        expected = width * height * 4
        print(f"  {'ok  ' if len(buffer) == expected else 'FAIL'} "
              f"grab_rect returned {len(buffer)} bytes, expected {expected}")
        if len(buffer) != expected:
            failures.append("wrong buffer length")

        print("\nthe encode")
        print("-" * 16)
        png = None
        try:
            from pyjab.common.png import bgra_to_png
            png = bgra_to_png(buffer, width, height)
            decoded_w, decoded_h, rows = decode_png(png)
            print(f"  ok   {len(png)} bytes decoded back to {decoded_w}x{decoded_h}")
            if (decoded_w, decoded_h) != (width, height):
                failures.append("decoded size differs from the requested rectangle")
        except Exception as error:                       # noqa: BLE001 - reported
            print(f"  FAIL {type(error).__name__}: {error}")
            failures.append("the grab did not encode")

        print("\nthe one that matters: is it actually a picture?")
        print("-" * 47)
        if png is not None:
            colours = {pixel for row in rows for pixel in row}
            print(f"  distinct colours in the grabbed rectangle: {len(colours)}")
            if len(colours) <= 1:
                print("  FAIL every pixel is identical. An all-black buffer is what a "
                      "failed GDI call returns, and it is indistinguishable from a black "
                      "window -- which is the whole reason this check exists.")
                failures.append("the image is uniform, so the grab probably failed silently")
            else:
                print("  ok   the rectangle varies, so pixels really came back")
                # A black frame plus one stray pixel would pass the check above; a real
                # window has far more than a handful.
                if len(colours) < 5:
                    print("  FAIL too few distinct colours to be a rendered window")
                    failures.append("too few colours")

        print()
        if failures:
            print("FAILED: " + "; ".join(failures))
            return 1
        print("PASSED: GDI returned a real, varying rectangle and it encoded to a PNG "
              "with no third-party image library")
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
