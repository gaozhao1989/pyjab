"""Binding to a Java window with an explicit bridge DLL.

The previous version of this file hardcoded four absolute paths from one
developer's machine (``C:\\Users\\garygao\\scoop\\...``), so it could only ever
pass there.  These tests ask pyjab where the DLL actually is instead, and skip
when the machine does not have the bitness being exercised.

They run against the Swing application in ``tests/java``, which the ``test_app``
fixture compiles and launches, so nothing here downloads or installs anything.
"""

import pytest

from pyjab.config import find_bridge_dll, get_dll_bit
from pyjab.jabdriver import JABDriver

pytestmark = pytest.mark.gui


def _dll_or_skip(bitness: int):
    path = find_bridge_dll(bitness)
    if path is None:
        pytest.skip(f"no {bitness}-bit WindowsAccessBridge DLL on this machine")
    return str(path)


class TestBridgeDll(object):
    def test_bridge_by_discovery(self, test_app) -> None:
        """No explicit path: discovery alone binds successfully."""
        assert test_app
        assert test_app.hwnd

    def test_explicit_bridge_dll(self, test_app) -> None:
        """An explicit bridge_dll= path is honoured.

        The application is already running (test_app), so this only exercises
        loading the DLL from a path we name ourselves.
        """
        dll = _dll_or_skip(get_dll_bit())

        # The title comes from the running fixture rather than the constant:
        # every launch gets its own title so a window from an earlier run
        # cannot be matched instead.
        #
        # Deliberately not a context manager: __exit__ terminates the bound
        # process by pid, which would tear down the test_app fixture's
        # application and break its teardown.
        driver = JABDriver(title=test_app.title, bridge_dll=dll)

        assert driver
        assert driver.hwnd

    def test_other_bitness_is_not_substituted(self, test_app) -> None:
        """Asking for the bitness we do not run must fail, not silently succeed.

        This is the regression guard for the wrong-architecture DLL case: before
        1.2.0 the error message did not say which architecture was found.
        """
        other = 32 if get_dll_bit() == 64 else 64
        if find_bridge_dll(other) is None:
            pytest.skip(f"this machine has no {other}-bit DLL to be confused by")

        wrong = _dll_or_skip(other)
        if wrong == _dll_or_skip(get_dll_bit()):
            pytest.skip("the two bitnesses resolve to the same file here")

        with pytest.raises(OSError):
            JABDriver(title=test_app.title, bridge_dll=wrong)
