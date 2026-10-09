#!/usr/bin/env python
"""Work out what coordinate space ``simulate=True`` needs on this display.

Run this on Windows, with a JDK installed.  It is the measurement behind issue
#62, and it exists because the answer cannot be reasoned out from the source.

Why this is needed
------------------
``click(simulate=True)`` takes the element's position from JAB and hands it to
``SetCursorPos``.  Two things can make those different numbers:

* the **target** JVM may not be per-monitor DPI aware, in which case JAB reports
  the application's logical coordinates rather than physical pixels;
* the **pyjab process** may or may not be DPI aware, which decides whether
  Windows scales what ``SetCursorPos`` receives or takes it literally.

Only the second is ours to observe directly, and the two together decide whether
a conversion is needed at all.  Rather than assume, this measures.

The decisive check
------------------
The test application couples one button to another's enabled state: clicking
"Disable middle button" disables "Middle button".  So a click either lands on it
or it does not, and the state says which -- which is a direct answer to "are
these the right coordinates on this display".

Usage
-----
    python tools/verify_dpi.py
    python tools/verify_dpi.py --no-launch     # attach to an already running app
    python tools/verify_dpi.py --hold          # leave the application open

Read the VERDICT at the end.  If it says a conversion is needed, that is a bug in
pyjab rather than in your setup, and the numbers above it are what is needed to
fix it -- please paste them into issue #62.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_DIR = REPO_ROOT / "tests" / "java"
APP_CLASS = "PyjabTestApp"
APP_TITLE = "PyjabTestApp"

# The buttons the decisive check uses.
DISABLE_BUTTON = "Disable middle button"
ENABLE_BUTTON = "Enable middle button"
MIDDLE_BUTTON = "Middle button"

DPI_AWARENESS = {
    0: "DPI_AWARENESS_INVALID",
    1: "UNAWARE (Windows scales coordinates for us)",
    2: "SYSTEM_AWARE",
    3: "PER_MONITOR_AWARE",
    4: "PER_MONITOR_AWARE_V2",
    5: "UNAWARE_GDISCALED",
}


def find_tool(name: str) -> str:
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / (name + ".exe")
        if candidate.exists():
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    sys.exit(
        f"could not find '{name}'.\n"
        "  A JDK (not just a JRE) is needed, on the PATH or in JAVA_HOME."
    )


def describe_process_dpi() -> dict:
    """What this process declares, by both APIs, because they disagree in practice."""
    user32 = ctypes.windll.user32
    facts = {}

    try:
        facts["IsProcessDPIAware()"] = bool(user32.IsProcessDPIAware())
    except Exception as exc:  # pragma: no cover - platform dependent
        facts["IsProcessDPIAware()"] = f"unavailable ({exc})"

    try:
        awareness = ctypes.c_int()
        hresult = ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(awareness))
        if hresult == 0:
            facts["GetProcessDpiAwareness()"] = DPI_AWARENESS.get(
                awareness.value, f"unknown ({awareness.value})"
            )
        else:
            facts["GetProcessDpiAwareness()"] = f"failed (HRESULT {hresult:#x})"
    except Exception as exc:  # pragma: no cover - Windows 8 and older
        facts["GetProcessDpiAwareness()"] = f"unavailable ({exc})"

    return facts


def describe_target_dpi(pid: int) -> dict:
    """What the *target* JVM declares, which is the half that decides this.

    Issue #62 turns on two processes, not one: the target decides whether the
    coordinates JAB reports are logical or physical, and pyjab decides whether
    ``SetCursorPos`` receives physical pixels or a space Windows scales for it.
    Only the target's answer tells you whether a conversion is needed at all --
    which is why guessing has a real chance of moving a click that used to land
    correctly.

    This read was missing. Without it, "the JAB position is already right here" has
    two possible causes that look identical -- the display is at 100%, or the
    application is DPI aware and its coordinates were physical all along -- and the
    script could not tell them apart.
    """
    facts = {}
    try:
        awareness = ctypes.c_int()
        hresult = ctypes.windll.shcore.GetProcessDpiAwareness(
            ctypes.c_void_p(pid), ctypes.byref(awareness)
        )
        if hresult == 0:
            facts["GetProcessDpiAwareness(pid)"] = DPI_AWARENESS.get(
                awareness.value, f"unknown ({awareness.value})"
            )
            facts["_aware"] = DPI_AWARENESS.get(awareness.value) in (
                "PROCESS_SYSTEM_DPI_AWARE", "PROCESS_PER_MONITOR_DPI_AWARE"
            )
        else:
            facts["GetProcessDpiAwareness(pid)"] = f"failed (HRESULT {hresult:#x})"
            facts["_aware"] = None
    except Exception as exc:  # pragma: no cover - platform dependent
        facts["GetProcessDpiAwareness(pid)"] = f"unavailable ({exc})"
        facts["_aware"] = None
    return facts


def describe_window(hwnd: int) -> dict:
    """The window's DPI, and its rect as Win32 sees it."""
    user32 = ctypes.windll.user32
    facts: dict = {}

    try:
        dpi = user32.GetDpiForWindow(hwnd)
        facts["GetDpiForWindow()"] = dpi
        facts["implied scale"] = f"{dpi / 96.0:.4f}"
    except Exception as exc:  # pragma: no cover - Windows 10 1607 and older
        facts["GetDpiForWindow()"] = f"unavailable ({exc})"

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    rect = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        facts["GetWindowRect()"] = {
            "x": rect.left,
            "y": rect.top,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top,
        }
    else:
        facts["GetWindowRect()"] = "failed"

    return facts


def launch_application() -> subprocess.Popen:
    javac = find_tool("javac")
    java = find_tool("java")
    classes = JAVA_DIR / "classes"
    classes.mkdir(parents=True, exist_ok=True)

    sources = sorted(str(p) for p in JAVA_DIR.glob("*.java"))
    subprocess.run([javac, "-Xlint:all", "-d", str(classes)] + sources, check=True)

    return subprocess.Popen(
        [java, "-Duser.language=en", "-Duser.country=US",
         "-cp", str(classes), APP_CLASS, "--title=" + APP_TITLE],
    )


def wait_for_binding(title: str, timeout: float = 60.0):
    from pyjab.common.exceptions import JABException
    from pyjab.jabdriver import JABDriver

    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            return JABDriver(title=title, timeout=10)
        except JABException as exc:  # window not up yet
            last = exc
            time.sleep(1)
    raise SystemExit(f"could not bind to {title!r} within {timeout}s: {last}")


def measure(driver) -> dict:
    """Compare the JAB position of the frame with what Win32 reports for it."""
    frame = driver.root_element
    jab_bounds = frame.bounds
    win32_bounds = describe_window(frame.hwnd)

    result = {"jab frame bounds": jab_bounds, "win32": win32_bounds}

    rect = win32_bounds.get("GetWindowRect()")
    if isinstance(rect, dict) and jab_bounds.get("width"):
        # The two are never identical -- JAB may report the client area, Win32 the
        # decorated window -- so the ratio is approximate. What matters is whether
        # it is near 1 or near the monitor scale.
        ratio_w = rect["width"] / jab_bounds["width"]
        ratio_h = rect["height"] / jab_bounds["height"]
        result["width ratio (win32 / JAB)"] = round(ratio_w, 4)
        result["height ratio (win32 / JAB)"] = round(ratio_h, 4)

    return result


def decisive_check(driver, scale: float) -> dict:
    """Click the coupled button and see whether the click landed.

    Returns which coordinate space the click had to be in for the state to change.
    """
    from pyjab.common.states import States

    disable = driver.find_element_by_name(DISABLE_BUTTON)
    enable = driver.find_element_by_name(ENABLE_BUTTON)
    middle = driver.find_element_by_name(MIDDLE_BUTTON)

    def middle_enabled() -> bool:
        return States.ENABLED in middle.states_en_us

    def restore() -> None:
        if not middle_enabled():
            enable.click()

    outcome: dict = {}

    def attempt(label: str, x: int, y: int) -> bool:
        restore()
        if not middle_enabled():
            outcome[label] = "could not re-enable the middle button; skipped"
            return False
        # driver.win32utils, no underscore.  JABDriver names it without and
        # JABElement names it with -- element.win32_utils -- and using the
        # element's spelling here raised AttributeError on the one machine that
        # can run this, at the point of the decisive click, after the JDK had
        # compiled and the measurements had been taken.
        driver.win32utils._set_window_foreground(hwnd=disable.hwnd)
        driver.win32utils._click_mouse(x=x, y=y)
        time.sleep(0.5)
        changed = not middle_enabled()
        outcome[label] = "the click landed" if changed else "nothing happened"
        return changed

    raw_x, raw_y = disable._click_point()
    outcome["JAB position (as reported)"] = (raw_x, raw_y)
    if attempt("clicked at the JAB position", raw_x, raw_y):
        restore()
        return outcome

    scaled_x, scaled_y = round(raw_x * scale), round(raw_y * scale)
    outcome["scaled position"] = (scaled_x, scaled_y)
    if scale != 1.0:
        attempt(f"clicked at the JAB position x{scale:g}", scaled_x, scaled_y)

    restore()
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true",
                        help="attach to an application that is already running")
    parser.add_argument("--hold", action="store_true",
                        help="leave the application running on exit")
    args = parser.parse_args()

    if not sys.platform.startswith("win"):
        sys.exit("this needs Windows: it is about DPI awareness and the Win32 mouse APIs")

    process = None
    if not args.no_launch:
        print(f"launching {APP_CLASS} ...")
        process = launch_application()

    try:
        driver = wait_for_binding(APP_TITLE)
        print(f"bound to {APP_TITLE!r} (hwnd {driver.root_element.hwnd})\n")

        print("this process's DPI awareness")
        process_facts = describe_process_dpi()
        for key, value in process_facts.items():
            print(f"  {key}: {value}")

        print("\nthe target application's DPI awareness (this is the half that decides)")
        target_facts = describe_target_dpi(driver.pid)
        target_aware = target_facts.pop("_aware", None)
        for key, value in target_facts.items():
            print(f"  {key}: {value}")

        print("\nthe window")
        measurement = measure(driver)
        for key in ("jab frame bounds",):
            print(f"  {key}: {measurement[key]}")
        for key, value in measurement["win32"].items():
            print(f"  {key}: {value}")
        for key in ("width ratio (win32 / JAB)", "height ratio (win32 / JAB)"):
            if key in measurement:
                print(f"  {key}: {measurement[key]}")

        scale = measurement["win32"].get("GetDpiForWindow()", 96) / 96.0
        if isinstance(scale, str) or not scale:
            scale = 1.0
        print(f"\nmonitor scale from GetDpiForWindow: {scale:g}")

        print("\nthe decisive check")
        outcome = decisive_check(driver, scale)
        for key, value in outcome.items():
            print(f"  {key}: {value}")

        print("\n" + "=" * 68)
        print("VERDICT")
        print("=" * 68)
        landed_raw = outcome.get("clicked at the JAB position") == "the click landed"
        landed_scaled = any(
            key.startswith("clicked at the JAB position x") and value == "the click landed"
            for key, value in outcome.items()
        )

        if landed_raw:
            print("  The JAB position is the right one on this display.")
            if scale == 1.0:
                print("  The scale is 1.0, so there is nothing here for DPI to get")
                print("  wrong. To test issue #62 this has to run on a display set to")
                print("  125% or 150%.")
            elif target_aware is True:
                print(f"  The scale is {scale:g} and the target declares itself DPI")
                print("  aware, so the coordinates JAB reports were already physical.")
                print("  That is the reason this case works, and it is why converting")
                print("  unconditionally would move a click that lands correctly now.")
            elif target_aware is False:
                print(f"  The scale is {scale:g} and the target is NOT DPI aware, so its")
                print("  coordinates are logical -- and the JAB position still landed.")
                print("  That is unexpected and worth reporting: it means the conversion")
                print("  issue #62 asks for is not needed even in this configuration.")
            else:
                print(f"  The scale is {scale:g}, so DPI matters here. Could not read")
                print("  the target's awareness; that value is the one that would say")
                print("  whether the coordinates were logical or physical.")
            print("  Nothing to fix for this configuration. Thank you -- knowing this")
            print("  case works is as useful as knowing the other one does not.")
        elif landed_scaled:
            print("  THE JAB POSITION IS WRONG; SCALING IT FIXES IT.")
            print("  This is issue #62. simulate=True is clicking at the wrong place")
            print("  on this display, and nothing reports an error -- the click simply")
            print("  lands elsewhere. Please paste everything above into #62.")
            return 1
        else:
            print("  NEITHER position worked, so the cause is not DPI scaling.")
            print("  Check that the application window is actually in the foreground")
            print("  and not covered; if it is, this is a different bug and the")
            print("  output above is what is needed to look into it.")
            return 1

        print("\nPlease paste the output above into issue #62 either way.")
        return 0
    finally:
        if process is not None and not args.hold:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                    process.kill()


if __name__ == "__main__":
    sys.exit(main())
