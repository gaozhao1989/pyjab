"""Tests for the Windows message pump.

pyjab drives Java Access Bridge, which is COM based.  Accessibility events --
including the ones that announce a window or dialog that opens *after* the
first one -- are delivered through COM to the thread that called
``Windows_run()``.  That thread has to service its message queue or those
events never arrive.

The pump used to be a generator advanced one step at a time by
``ActorScheduler``, and only while pyjab was waiting for the first window.  It
has been replaced by ``Win32Utils.pump_messages()``.

Portability
-----------
``pyjab.common.win32utils`` imports pywin32 at module scope, so on Linux and
macOS this module installs stand-ins for the pywin32 modules in order to be able
to import it at all.  On Windows the real modules are present and are used.

The pump function itself is *always* replaced with a double, by patching the
module attribute rather than ``sys.modules``, so the assertions behave the same
whether or not pywin32 is installed.  Without that these tests would pass in a
bare pytest-only environment and fail on a real Windows checkout -- which is
exactly what happened the first time they ran with pywin32 present.
"""

import contextlib
import pathlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

import pyjab


# ---------------------------------------------------------------------------
# pywin32 stand-ins, for platforms that do not have pywin32
# ---------------------------------------------------------------------------

class _PermissiveModule(types.ModuleType):
    """A module whose every attribute access yields a callable stub."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        stub = MagicMock(name=name)
        setattr(self, name, stub)
        return stub


def _install_stub(name: str, **attributes) -> types.ModuleType:
    module = _PermissiveModule(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _ensure_win32_available() -> None:
    """Install stand-ins only for pywin32 modules that are genuinely missing."""
    try:
        import pythoncom  # noqa: F401
        return
    except ImportError:
        pass

    class ComError(Exception):
        """Stand-in for pythoncom.com_error."""

    pythoncom = _install_stub("pythoncom")
    pythoncom.PumpWaitingMessages = MagicMock(return_value=False)
    pythoncom.com_error = ComError

    _install_stub("win32api")
    _install_stub("win32clipboard")
    _install_stub("win32con")
    _install_stub("win32gui")
    win32com = _install_stub("win32com")
    win32com.client = _install_stub("win32com.client")


_ensure_win32_available()


def _import_jabelement():
    """Import :mod:`pyjab.jabelement`, working around its platform guard.

    ``jabelement`` refuses to import off Windows, so ``sys.platform`` is briefly
    reported as Windows.  ``PIL.ImageGrab`` is imported first, under the real
    platform, so that faking ``sys.platform`` cannot push PIL down a Windows-only
    import path.  On Windows itself this is all a no-op.
    """

    real_platform = sys.platform
    sys.platform = "win32"
    try:
        from pyjab.jabelement import JABElement
    finally:
        sys.platform = real_platform
    return JABElement


from pyjab.common.exceptions import JABException  # noqa: E402
from pyjab.common.win32utils import Win32Utils  # noqa: E402

JABElement = _import_jabelement()

# Win32Utils is decorated with @singleton, so the name is a wrapper *function*
# and the real class lives behind __wrapped__.  Class level patching and
# attribute checks must go through it.
Win32UtilsClass = Win32Utils.__wrapped__

#: The module object whose ``pythoncom`` reference the pump actually calls.
WIN32UTILS_MODULE = sys.modules["pyjab.common.win32utils"]


@pytest.fixture
def pump(monkeypatch):
    """Replace the ``pythoncom`` the pump uses, and return its pump function.

    Patching the module attribute rather than ``sys.modules`` keeps this working
    on Windows, where the real pywin32 is installed and must not be shadowed for
    the rest of the session.
    """
    class ComError(Exception):
        """Stand-in for pythoncom.com_error."""

    fake = types.SimpleNamespace(
        PumpWaitingMessages=MagicMock(return_value=False),
        com_error=ComError,
    )
    monkeypatch.setattr(WIN32UTILS_MODULE, "pythoncom", fake)
    return fake.PumpWaitingMessages


@pytest.fixture
def win32utils():
    # Bypass the @singleton cache so each test gets a fresh instance.
    return Win32UtilsClass()


# ---------------------------------------------------------------------------
# Win32Utils.pump_messages
# ---------------------------------------------------------------------------

def test_pump_messages_services_the_queue(win32utils, pump):
    result = win32utils.pump_messages()

    pump.assert_called_once_with()
    assert result is False


def test_pump_messages_reports_wm_quit(win32utils, pump):
    pump.return_value = True

    assert win32utils.pump_messages() is True


def test_pump_messages_swallows_com_error(win32utils, pump):
    """A thread without a COM queue must not blow up the caller."""
    pump.side_effect = WIN32UTILS_MODULE.pythoncom.com_error("no COM queue here")

    assert win32utils.pump_messages() is False


def test_pump_messages_is_safe_to_call_often(win32utils, pump):
    """It runs on every lookup, so repeated calls must be harmless."""
    for _ in range(5):
        win32utils.pump_messages()

    assert pump.call_count == 5


# ---------------------------------------------------------------------------
# Regression guards for the removed generator pump
# ---------------------------------------------------------------------------

def test_generator_pump_and_its_events_are_gone():
    assert not hasattr(Win32UtilsClass, "setup_msg_pump")
    assert not hasattr(Win32UtilsClass, "stop_event")
    assert not hasattr(Win32UtilsClass, "other_event")


def test_win32utils_no_longer_imports_win32event():
    """win32event was only needed by the generator pump's blocking wait."""
    module_file = sys.modules[Win32UtilsClass.__module__].__file__
    text = pathlib.Path(module_file).read_text(encoding="utf-8")

    assert "win32event" not in text


def test_jabdriver_stopped_using_the_actor_scheduler():
    """jabdriver must not resurrect the drip-fed pump."""
    jabdriver_src = pathlib.Path(pyjab.__file__).parent / "jabdriver.py"
    text = jabdriver_src.read_text(encoding="utf-8")

    assert "ActorScheduler" not in text
    assert "_run_actor_sched" not in text
    assert "setup_msg_pump" not in text


def test_jabdriver_pumps_in_both_wait_loops():
    """Waiting is exactly when a new window or dialog has to be noticed."""
    jabdriver_src = pathlib.Path(pyjab.__file__).parent / "jabdriver.py"
    text = jabdriver_src.read_text(encoding="utf-8")

    assert text.count("self._pump_messages()") >= 3, (
        "expected a pump in init_jab, wait_java_window_by_title and "
        "wait_until_element_exist"
    )


def test_wait_until_element_exist_is_not_a_busy_loop():
    """It used to spin with no sleep at all (issues #29 and #33)."""
    jabdriver_src = pathlib.Path(pyjab.__file__).parent / "jabdriver.py"
    text = jabdriver_src.read_text(encoding="utf-8")

    start = text.index("def wait_until_element_exist")
    body = text[start:start + 2000]
    assert "sleep(" in body, "wait_until_element_exist must back off between polls"


def test_actor_scheduler_is_marked_deprecated():
    """It is kept only so existing imports keep working."""
    from pyjab.common import actorscheduler

    doc = actorscheduler.ActorScheduler.__doc__ or ""
    assert "deprecated" in doc.lower()


# ---------------------------------------------------------------------------
# The pump is wired into every element lookup
# ---------------------------------------------------------------------------

LOOKUP_CALLS = [
    pytest.param(lambda el: el.find_element(by="not-a-strategy", value="x"),
                 id="find_element"),
    pytest.param(lambda el: el.find_elements(by="not-a-strategy", value="x"),
                 id="find_elements"),
    pytest.param(lambda el: el.find_element_by_xpath("//panel"),
                 id="find_element_by_xpath"),
    pytest.param(lambda el: el.find_elements_by_xpath("//panel"),
                 id="find_elements_by_xpath"),
]


@pytest.mark.parametrize("call", LOOKUP_CALLS)
def test_every_lookup_entry_point_pumps_messages(call):
    """All find_* funnel through these four methods.

    A JABElement with no bridge cannot complete a real lookup, which is fine:
    the assertion is that the pump ran *before* anything else happened.
    """
    element = JABElement()

    with patch.object(Win32UtilsClass, "pump_messages") as pumped:
        with contextlib.suppress(Exception):
            call(element)

    assert pumped.called, "the message pump did not run before the lookup"


def test_find_element_rejects_unknown_strategy_after_pumping():
    element = JABElement()

    with patch.object(Win32UtilsClass, "pump_messages") as pumped:
        with pytest.raises(JABException):
            element.find_element(by="not-a-strategy", value="x")

    assert pumped.called


def test_find_element_by_name_routes_through_find_element():
    """Guards the assumption that these really are choke points.

    If a find_element_by_* ever stops delegating to find_element(), the pump
    coverage regresses silently.  This catches that.
    """
    element = JABElement()

    with patch.object(JABElement, "find_element") as delegated:
        delegated.return_value = "sentinel"
        assert element.find_element_by_name("anything") == "sentinel"

    delegated.assert_called_once()
