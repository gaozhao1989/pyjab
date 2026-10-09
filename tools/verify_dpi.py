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
import contextlib
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

#: The PROCESS_DPI_AWARENESS members that mean "this process does its own scaling".
PROCESS_DPI_SYSTEM_AWARE = 2
PROCESS_DPI_PER_MONITOR_AWARE = 3
PROCESS_DPI_PER_MONITOR_AWARE_V2 = 4

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
    # GetProcessDpiAwareness takes a process HANDLE, not a process id, and says so
    # in its signature: "[in] HANDLE hprocess -- handle of the process that is being
    # queried". Passing the id raised E_INVALIDARG (0x80070057), which is how the
    # first version of this failed on a real run -- and it is worth recording that
    # the failure looked like a fact about the application rather than a bug here.
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    k32 = ctypes.windll.kernel32

    facts = {}
    handle = None
    try:
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            facts["GetProcessDpiAwareness(pid)"] = (
                f"OpenProcess failed (error {ctypes.get_last_error() or k32.GetLastError()}); "
                "the target may be running elevated"
            )
            facts["_aware"] = None
            return facts

        awareness = ctypes.c_int()
        hresult = ctypes.windll.shcore.GetProcessDpiAwareness(
            ctypes.c_void_p(handle), ctypes.byref(awareness)
        )
        if hresult == 0:
            name = DPI_AWARENESS.get(awareness.value, f"unknown ({awareness.value})")
            facts["GetProcessDpiAwareness(pid)"] = name
            # By value, not by name. The name in DPI_AWARENESS is "PER_MONITOR_AWARE"
            # while the enum member is PROCESS_PER_MONITOR_DPI_AWARE, and a check
            # written against the latter never matched -- so an aware target was
            # reported as unaware, which is the one answer this must not get wrong.
            facts["_aware"] = awareness.value in (
                PROCESS_DPI_SYSTEM_AWARE,
                PROCESS_DPI_PER_MONITOR_AWARE,
                PROCESS_DPI_PER_MONITOR_AWARE_V2,
            )
        else:
            unsigned = hresult & 0xFFFFFFFF
            known = {
                0x80070057: "E_INVALIDARG -- the handle or the pointer was not valid",
                0x80070005: "E_ACCESSDENIED -- pyjab is not privileged enough to ask",
            }
            facts["GetProcessDpiAwareness(pid)"] = (
                f"failed: {decode_hresult(hresult)}"
                + (f" ({known[unsigned]})" if unsigned in known else "")
            )
            facts["_aware"] = None
    except Exception as exc:  # pragma: no cover - platform dependent
        facts["GetProcessDpiAwareness(pid)"] = f"unavailable ({exc})"
        facts["_aware"] = None
    finally:
        if handle:
            k32.CloseHandle(ctypes.c_void_p(handle))

    return facts


def decode_hresult(hresult: int) -> str:
    """`0x80070057`, `0x80070057/87`, and the signed form, for a human reading it.

    The first run of the target-awareness check reported ``-0x7ff8ffa9``, which is
    ``0x80070057`` -- E_INVALIDARG, ERROR_INVALID_PARAMETER 87. Printing the signed
    value alone made a bug here look like a fact about the application, so the
    unsigned form, the facility and the code are all in the string.
    """
    unsigned = hresult & 0xFFFFFFFF
    facility = (unsigned >> 16) & 0x1FFF
    code = unsigned & 0xFFFF
    return f"HRESULT {hresult} (0x{unsigned:08X}, facility {facility}, code {code})"


#: Pseudo-handles for SetThreadDpiAwarenessContext.  Passing -4 selects per-monitor
#: v2 for the calling thread only, which is what makes the real display DPI
#: readable from a process that is itself unaware.
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
MDT_EFFECTIVE_DPI = 0
MONITOR_DEFAULTTONEAREST = 2


def display_dpi(hwnd: int) -> dict:
    """The display's real DPI, read from a thread that is temporarily aware.

    Both ``GetDpiForWindow`` and ``GetDpiForMonitor`` answer **96** when the calling
    process is DPI unaware -- Microsoft documents this for each of them, and it
    says "DPI awareness" rather than "the display" in the return table.  So an
    unaware process cannot see a 150% display by asking either one, and this script
    previously computed its scale from ``GetDpiForWindow()`` and therefore reported
    1.0 on every machine where pyjab is unaware -- which is every machine, since
    pyjab declares no awareness at all.

    The value that matters is the display's real DPI, and the only way to get it
    from an unaware process is to become aware for the length of the call.
    ``SetThreadDpiAwarenessContext`` changes the calling thread only, so this reads
    the answer and hands the thread back exactly as it found it.  That is the
    "sub-process DPI awareness" pattern from Microsoft's mixed-mode DPI guidance.

    See https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-improvements-for-desktop-applications
    """
    user32 = ctypes.windll.user32
    facts: dict = {}

    try:
        monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    except Exception as exc:  # pragma: no cover - platform dependent
        return {"display DPI": f"unavailable ({exc})"}

    previous = None
    try:
        user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        previous = user32.GetThreadDpiAwarenessContext()
        user32.SetThreadDpiAwarenessContext(
            ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        )
    except Exception as exc:  # pragma: no cover - Windows 10 1607 and older
        facts["display DPI"] = f"unavailable ({exc})"
        return facts

    try:
        dpi_x, dpi_y = ctypes.c_uint(), ctypes.c_uint()
        hresult = ctypes.windll.shcore.GetDpiForMonitor(
            ctypes.c_void_p(monitor), MDT_EFFECTIVE_DPI,
            ctypes.byref(dpi_x), ctypes.byref(dpi_y),
        )
        if hresult == 0:
            facts["display DPI"] = dpi_x.value
            facts["display scale"] = f"{dpi_x.value / 96.0:.4f}"
        else:
            facts["display DPI"] = f"failed (HRESULT {hresult:#x})"
    except Exception as exc:  # pragma: no cover - platform dependent
        facts["display DPI"] = f"unavailable ({exc})"
    finally:
        try:
            user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(previous))
        except Exception:  # pragma: no cover - restoring must not raise
            pass

    return facts


def describe_window(hwnd: int) -> dict:
    """The window's rect as Win32 sees it, and what this process can see of the DPI.

    Everything here answers in the calling process's own DPI context, which is the
    point: these are the coordinates and the scale that ``SetCursorPos`` will use.
    ``display_dpi`` separately reports the display's real DPI, which is not the
    same number and is not visible from here.
    """
    user32 = ctypes.windll.user32
    facts: dict = {}

    try:
        dpi = user32.GetDpiForWindow(hwnd)
        # 96 for an unaware window by definition, not because the display is at 100%.
        facts["GetDpiForWindow()"] = dpi
        facts["implied scale as this process sees it"] = f"{dpi / 96.0:.4f}"
    except Exception as exc:  # pragma: no cover - Windows 10 1607 and older
        facts["GetDpiForWindow()"] = f"unavailable ({exc})"

    facts.update(display_dpi(hwnd))

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


@contextlib.contextmanager
def thread_dpi_awareness(context: int):
    """Run a block with this thread's DPI awareness switched, then put it back.

    Only the calling thread is affected, so the application is untouched and the
    switch is undone in a finally. This is what lets one run reproduce issue #62 on
    demand: an unaware process has its mouse coordinates virtualised, so clicking at
    a logical position lands; the same click issued from an aware thread is taken as
    physical, and then it does not.
    """
    user32 = ctypes.windll.user32
    # Signatures declared, per AGENTS.md 2.8: without restype ctypes assumes c_int
    # and truncates the returned handle to 32 bits, and without argtypes it masks
    # the argument the same way. The pseudo-handles are small negatives so it
    # happens to work, and "happens to work" is how the next one is written.
    user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p

    previous = user32.GetThreadDpiAwarenessContext()
    user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(context))
    try:
        yield
    finally:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(previous))


def decisive_check(driver, scale: float, aware: bool = False) -> dict:
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
        # Everything below this line is issued from the thread whose awareness the
        # caller asked for; SetCursorPos is interpreted in that context.
        if aware:
            with thread_dpi_awareness(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
                driver.win32utils._click_mouse(x=x, y=y)
        else:
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
        print("\nwhat this process can see of the display")
        for key in ("GetDpiForWindow()", "implied scale as this process sees it"):
            if key in measurement["win32"]:
                print(f"  {key}: {measurement['win32'][key]}")

        # The display's real scale, not the one this unaware process is allowed to
        # see -- see display_dpi(). Reading it from GetDpiForWindow() made this 1.0
        # on every machine, so the scaled-position half of the check never ran.
        display = measurement["win32"].get("display DPI", 96)
        scale = display / 96.0 if isinstance(display, (int, float)) and display else 1.0
        print(f"\ndisplay scale, read from a temporarily aware thread: {scale:g}")
        if scale != 1.0:
            print("  This process is unaware, so GetDpiForWindow() above reports 96 by")
            print("  definition -- it is not evidence that the display is at 100%.")

        print("\nthe decisive check, as this process is now (DPI unaware)")
        outcome = decisive_check(driver, scale)
        for key, value in outcome.items():
            print(f"  {key}: {value}")

        # The same clicks again, from a thread that IS DPI aware. This is the half
        # that reproduces issue #62: the target's coordinates are logical because
        # the target is unaware, and an aware caller has its mouse coordinates
        # taken as physical, so the two stop agreeing.
        print("\nthe same check from a DPI-aware thread (issue #62's configuration)")
        aware_outcome = decisive_check(driver, scale, aware=True)
        for key, value in aware_outcome.items():
            print(f"  {key}: {value}")

        print("\n" + "=" * 68)
        print("VERDICT")
        print("=" * 68)
        aware_raw = aware_outcome.get("clicked at the JAB position") == "the click landed"
        aware_scaled = any(
            key.startswith("clicked at the JAB position x")
            and value == "the click landed"
            for key, value in aware_outcome.items()
        )

        if landed_raw and not aware_raw:
            print("  #62 REPRODUCED, and the shape of it is now clear:")
            print("  unaware, the JAB position lands; DPI aware, it does not"
                  + (" and the scaled position does." if aware_scaled else "."))
            print("  So the mismatch is not about the display or the target alone --")
            print("  it is about the two processes being in different coordinate")
            print("  spaces. Please paste everything above into #62.")
            return 1

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
