#!/usr/bin/env python
"""Manual verification for the 1.3.0 message pump rewrite.

Run this on Windows, with a JDK installed and pyjab 1.3.0 in the environment.

Why this exists
---------------
CI covers the pump logic and proves the real ``pythoncom.PumpWaitingMessages()``
call works, but the default matrix never drives a live Swing application -- the
GUI suite runs only in ``.github/workflows/windows-gui.yml``, which is dispatched
by hand.  So this script is still the way to check the pump against a *particular*
application, and against the Java Control Panel below in particular.  What changed
in 1.3.0 is "does pyjab notice a window or dialog that opens *after* the first
window is bound", and that only shows up end to end.

This reproduces the scenario from issue #56 ("Java Control Panel -> Open about;
try to found new About window, but failed") using the Java Control Panel, which
ships with JDK 8 as ``<JAVA_HOME>\\jre\\bin\\javacpl.exe``.

Usage
-----
    python tools/verify_message_pump.py
    python tools/verify_message_pump.py --javacpl "C:\\path\\to\\javacpl.exe"
    python tools/verify_message_pump.py --hold      # leave the panel open

Expected result before 1.3.0: step 4 fails.  The newly opened dialog is not
found, because the message queue was never serviced once the first window had
been bound.

Expected result from 1.3.0: every step passes.

The script terminates the Java Control Panel on exit, unless ``--hold`` is given.
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import time

import pyjab
from pyjab.common.by import By
from pyjab.common.exceptions import JABException
from pyjab.jabdriver import JABDriver

PANEL_TITLE = "Java Control Panel"
ABOUT_TITLES = ("About", "About...", "About Java")


def find_javacpl() -> str | None:
    """Best-effort search for javacpl.exe in the usual places."""
    candidates: list[str] = []

    for env_var in ("JAVA_HOME", "JDK_HOME", "JRE_HOME"):
        home = os.environ.get(env_var)
        if home:
            candidates += glob.glob(
                os.path.join(home, "**", "javacpl.exe"), recursive=True
            )

    for root in (r"C:\Program Files\Java", r"C:\Program Files (x86)\Java"):
        candidates += glob.glob(os.path.join(root, "**", "javacpl.exe"), recursive=True)

    return candidates[0] if candidates else None


def find_about_button(driver: JABDriver, timeout: int):
    """Return the About button, trying a few spellings before giving up."""
    last_error: Exception | None = None
    for title in ABOUT_TITLES:
        try:
            return driver.wait_until_element_exist(By.NAME, title, timeout=timeout)
        except JABException as exc:
            last_error = exc

    # Self-diagnose: say what the panel actually offers.
    print("    Could not find an About button. Push buttons present on the panel:")
    try:
        for button in driver.find_elements_by_role("push button"):
            print(f"      name={button.name!r} role={button.role!r}")
    except JABException as exc:  # pragma: no cover - diagnostic path
        print(f"      (could not enumerate buttons either: {exc})")

    raise AssertionError(f"no About button found, last error: {last_error}")


def run_checks(driver: JABDriver, timeout: int) -> list[str]:
    """Run the steps and return a list of failure descriptions."""
    failures: list[str] = []

    print(f"\n[1] Bound to '{PANEL_TITLE}'")
    print(f"    hwnd = {driver.hwnd}")

    print("\n[2] Finding the About button")
    try:
        about_button = find_about_button(driver, timeout)
        print(f"    found: name={about_button.name!r} role={about_button.role!r}")
    except Exception as exc:  # noqa: BLE001 - report, do not mask
        failures.append(f"step 2: {exc}")
        print(f"    FAILED: {exc}")
        return failures

    print("\n[3] Clicking About -- this opens a NEW window")
    about_button.click()
    time.sleep(1.0)

    print("\n[4] Looking for the newly opened dialog  <-- the 1.3.0 fix")
    try:
        dialog = driver.wait_until_element_exist(By.ROLE, "dialog", timeout=timeout)
        print(f"    found dialog: name={dialog.name!r} role={dialog.role!r}")
    except JABException as exc:
        failures.append(f"step 4: dialog not found -- {exc}")
        print(f"    FAILED: {exc}")

    print("\n[5] Reading elements inside the new window")
    try:
        labels = driver.find_elements_by_role("label")
        print(f"    {len(labels)} label(s) found")
    except JABException as exc:
        failures.append(f"step 5: no labels found -- {exc}")
        print(f"    FAILED: {exc}")

    print("\n[6] get_focused_element() (added in 1.2.1)")
    try:
        focused = driver.get_focused_element()
        print(f"    focused = {focused!r}")
    except Exception as exc:  # noqa: BLE001 - report, do not mask
        failures.append(f"step 6: get_focused_element raised -- {exc!r}")
        print(f"    FAILED: {exc!r}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--javacpl", help="Path to javacpl.exe")
    parser.add_argument("--timeout", type=int, default=30, help="Per-step timeout (seconds)")
    parser.add_argument(
        "--hold",
        action="store_true",
        help="Do not terminate the Java Control Panel on exit",
    )
    args = parser.parse_args()

    javacpl = args.javacpl or find_javacpl()
    if not javacpl:
        print("Could not find javacpl.exe. Pass --javacpl explicitly.")
        print(r"It ships with JDK 8 at <JAVA_HOME>\jre\bin\javacpl.exe")
        return 2

    print(f"pyjab version : {pyjab.__version__}")
    print(f"javacpl       : {javacpl}")
    print(f"python        : {sys.version.split()[0]} ({sys.platform})")

    subprocess.Popen([javacpl])

    # JABDriver has no quit() method; __exit__ terminates the bound Java process
    # by pid, which is exactly what this script wants.
    if args.hold:
        driver = JABDriver(title=PANEL_TITLE, timeout=args.timeout)
        failures = run_checks(driver, args.timeout)
    else:
        with JABDriver(title=PANEL_TITLE, timeout=args.timeout) as driver:
            failures = run_checks(driver, args.timeout)

    print("\n" + "=" * 62)
    if failures:
        print("RESULT: FAILED")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nIf step 4 or 5 failed, COM is still not being serviced on this\n"
            "thread. Please paste the output above on the issue tracker."
        )
        return 1

    print("RESULT: PASSED")
    print("The pump noticed a window opened after the first one was bound.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
