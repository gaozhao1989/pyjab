"""The two things pyjab-mcp waits on, implemented to the shape it asked for.

Both requirements came from the dependent project rather than from here: its readiness
check names `list_java_windows` and `detach`, says what each unblocks, and probes for them.
Writing to that spec rather than to a guess is the point of the probe existing.

The interesting assertions are about the **contract**, not the implementation: that
`pyjab.list_java_windows` is reachable without Windows (because `import pyjab` has to stay
harmless), and that `detach` leaves a driver that will not kill the process it let go of.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import _win32stubs  # noqa: F401

import pyjab
from pyjab.common.service import Service
from tests._fakejab import bind, node

JABDriver = _win32stubs.import_jabdriver()

#: The stubs helper returns the *class*, not the module -- its name is `import_jabdriver`
#: and its docstring says `Return JABDriver`.
REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# list_java_windows
# ---------------------------------------------------------------------------

def test_the_package_exposes_it_everywhere():
    """`hasattr` is how the dependent probes for it, and that has to work off Windows.

    `pyjab/__init__.py` is deliberately free of a platform guard, so the function has to
    exist there as a wrapper whose Windows body is only reached when it is called. A
    plain import at module scope would make `import pyjab` fail on macOS, which the whole
    portable suite depends on not happening.
    """
    assert hasattr(pyjab, "list_java_windows")


@pytest.mark.skipif(sys.platform == "win32", reason="this is the off-Windows path")
def test_calling_it_off_windows_explains_itself():
    """Not a bare `No module named 'win32process'`.

    In a **subprocess**, because other tests in this file fake `sys.platform` to import the
    Windows-only modules, and the fake outlives them: in the same process `pyjab.jabdriver`
    imports, the DLL search then fails, and the caller sees a `FileNotFoundError` about the
    bridge instead of the sentence about Windows. That is a property of the test process,
    not of the API, and running it here is the only way to assert the real thing.
    """
    result = subprocess.run(
        [sys.executable, "-c",
         "import pyjab, sys\n"
         "try:\n"
         "    pyjab.list_java_windows()\n"
         "except ImportError as exc:\n"
         "    print(exc)\n"
         "    sys.exit(0)\n"
         "sys.exit(1)\n"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )

    assert result.returncode == 0, f"no ImportError; stderr: {result.stderr[-400:]}"
    assert "Windows" in result.stdout


def test_it_returns_mappings_with_the_fields_the_requirement_names():
    """The shape asked for: mappings with `hwnd`, `title` and an optional `pid`."""
    import pyjab.jabdriver as jabdriver

    fake_bridge = type("B", (), {
        "Windows_run": lambda self: None,
        "isJavaWindow": lambda self, hwnd: hwnd in (10, 20),
    })()

    #  on both, because Win32Utils is one of the five singletons (AGENTS.md
    # 2.2): patching  sets an attribute on the wrapper *function*
    # and the real method runs. This test was written that way first, and passed nothing.
    with patch.object(Service.__wrapped__, "load_library", return_value=fake_bridge), \
         patch("pyjab.common.win32utils.Win32Utils.__wrapped__.enum_windows",
               return_value={10: "One", 20: "Two", 30: "NotJava", 40: ""}), \
         patch.object(jabdriver, "_pid_of_hwnd", return_value=99), \
         patch.object(jabdriver, "_vmid_of_hwnd", return_value=7), \
         patch("pyjab.jabfixedfunc.JABFixedFunc", autospec=True):
        found = jabdriver.list_java_windows()

    assert [w["hwnd"] for w in found] == [10, 20]
    for window in found:
        assert set(window) == {"hwnd", "title", "pid", "vmid"}


# ---------------------------------------------------------------------------
# detach
# ---------------------------------------------------------------------------

def a_driver():
    """A driver bound to a fake element, with a pid set."""
    element, _bridge = bind(node("frame", name="app"))
    driver = JABDriver.__new__(JABDriver)
    driver.root_element = element
    driver.accessible_context = 12345
    driver.hwnd = 4321
    driver.vmid = 7
    driver.pid = 4242
    return driver


def test_detach_forgets_everything_it_bound():
    driver = a_driver()

    driver.detach()

    assert driver.root_element is None
    assert driver.accessible_context is None
    assert driver.hwnd is None
    assert driver.vmid is None
    assert driver.pid is None


def test_detach_does_not_kill_the_process():
    """The whole requirement. `__exit__` sends SIGTERM; a detach must not."""
    driver = a_driver()

    with patch("os.kill") as killer:
        driver.detach()
        # And exiting afterwards must not either -- that is what forgetting the pid buys.
        driver.__exit__(None, None, None)

    assert not killer.called, "detach, or leaving the block after one, terminated the process"


def test_detach_is_idempotent():
    driver = a_driver()

    driver.detach()
    driver.detach()

    assert driver.root_element is None


def test_detach_on_a_driver_that_never_bound_anything_is_fine():
    """`init_jab` can raise before it resolves a window, and the caller may still detach.

    Note the construction: `JABDriver.__new__(JABDriver)`, **not** `__wrapped__`. JABDriver
    is not one of the five singletons (AGENTS.md 2.2), so it has no wrapper to unwrap --
    and reaching for one is exactly the mistake that section warns about, made here first.
    """
    driver = JABDriver.__new__(JABDriver)

    driver.detach()

    assert driver.pid is None
