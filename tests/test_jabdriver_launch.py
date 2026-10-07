"""Tests for JABDriver's process and launch handling.

None of this needs a Java application: it covers what JABDriver does with a
pid, and how it builds the command line. ``JABDriver.__new__`` is used to get an
instance without running ``__init__``, which connects to the bridge and writes
``~/.accessibility.properties``.
"""

import signal
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

JABDriver = _win32stubs.import_jabdriver()

#: The module whose names JABDriver's own module calls.
JABDRIVER_MODULE = sys.modules["pyjab.jabdriver"]


def driver_without_connecting() -> "JABDriver":
    """An instance that never ran __init__, so nothing was connected or written."""
    return JABDriver.__new__(JABDriver)


# ---------------------------------------------------------------------------
# __exit__ and the process it terminates
# ---------------------------------------------------------------------------

def test_exit_terminates_the_bound_process():
    driver = driver_without_connecting()
    driver._pid = 4321

    with patch.object(JABDRIVER_MODULE, "os") as os_module:
        driver.__exit__(None, None, None)

    os_module.kill.assert_called_once_with(4321, signal.SIGTERM)


def test_exit_is_a_no_op_when_nothing_was_bound():
    """Regression: a None pid reached os.kill.

    self.pid stays None when init_jab() fails before it resolves the window --
    the common case, since it is what happens when the window never appears.
    os.kill(None, ...) then raised TypeError, which replaced the real exception
    with a misleading one and hid the actual failure.
    """
    driver = driver_without_connecting()
    driver._pid = None

    with patch.object(JABDRIVER_MODULE, "os") as os_module:
        driver.__exit__(None, None, None)

    os_module.kill.assert_not_called()


def test_exit_lets_the_original_exception_propagate_when_unbound():
    """A failing with-block must report its own error, not a TypeError."""
    driver = driver_without_connecting()
    driver._pid = None

    with patch.object(JABDRIVER_MODULE, "os") as os_module:
        with pytest.raises(RuntimeError, match="window never appeared"):
            try:
                raise RuntimeError("window never appeared")
            finally:
                driver.__exit__(RuntimeError, RuntimeError("x"), None)

    os_module.kill.assert_not_called()


# ---------------------------------------------------------------------------
# open_application builds an argv list, not a shell string
# ---------------------------------------------------------------------------

def test_open_application_passes_an_argv_list():
    """Regression: the path went through cmd.exe because of shell=True.

    A path containing a space -- "C:\\Program Files\\Java\\...\\javacpl.exe" --
    was split by the shell and never launched.
    """
    driver = driver_without_connecting()
    driver.file_path = Path(r"C:\Program Files\Java\jdk1.8.0_311\jre\bin\javacpl.exe")

    with patch.object(JABDRIVER_MODULE, "Popen") as popen:
        driver.open_application()

    args, kwargs = popen.call_args
    assert args == ([r"C:\Program Files\Java\jdk1.8.0_311\jre\bin\javacpl.exe"],)
    assert "shell" not in kwargs or not kwargs["shell"]


def test_open_application_uses_javaws_for_jnlp():
    driver = driver_without_connecting()
    driver.file_path = Path("demo.jnlp")

    with patch.object(JABDRIVER_MODULE, "Popen") as popen:
        driver.open_application()

    assert popen.call_args.args == (["javaws", "demo.jnlp"],)


def test_open_application_does_not_wait_for_the_process():
    """p.wait() used to block until the application exited.

    JABDriver needs to bind to the window, which only exists while the
    application runs, so waiting meant the bind could never succeed.
    """
    driver = driver_without_connecting()
    driver.file_path = Path("demo.jnlp")

    with patch.object(JABDRIVER_MODULE, "Popen") as popen:
        driver.open_application()

    assert not popen.return_value.wait.called
