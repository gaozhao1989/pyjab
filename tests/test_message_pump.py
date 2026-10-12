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

import ast
import contextlib
import pathlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


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
    # pyjab.jabdriver imports win32process at module scope, so without this stub the
    # file could not be collected on its own off Windows: `pytest
    # tests/test_message_pump.py` raised "No module named 'win32process'" while the
    # whole-suite run passed, because an earlier module had already stubbed it.
    _install_stub("win32process")
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


def _import_jabdriver():
    """Import :class:`pyjab.jabdriver.JABDriver`, past its platform guard."""

    real_platform = sys.platform
    sys.platform = "win32"
    try:
        from pyjab.jabdriver import JABDriver
    finally:
        sys.platform = real_platform
    return JABDriver


from pyjab.common.exceptions import JABException  # noqa: E402
from pyjab.common.win32utils import Win32Utils  # noqa: E402

JABElement = _import_jabelement()
JABDriver = _import_jabdriver()

# Win32Utils is decorated with @singleton, so the name is a wrapper *function*
# and the real class lives behind __wrapped__.  Class level patching and
# attribute checks must go through it.
Win32UtilsClass = Win32Utils.__wrapped__

#: The module object whose ``pythoncom`` reference the pump actually calls.
WIN32UTILS_MODULE = sys.modules["pyjab.common.win32utils"]

#: ``pyjab.jabdriver`` and its file, for the structural checks below.
JABDRIVER_MODULE = sys.modules["pyjab.jabdriver"]
JABDRIVER_SRC = pathlib.Path(JABDRIVER_MODULE.__file__)


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
    """win32event was only needed by the generator pump's blocking wait.

    Asserted on the module object rather than on the text of the file.  The text
    version went red when a *comment* mentioning ``win32event`` was added, which
    is a false alarm; this one goes red when the import comes back, which is the
    thing that would actually matter.  The removed pump imported it at module
    scope, so a module attribute is the name this checks.
    """
    assert not hasattr(WIN32UTILS_MODULE, "win32event")


def test_jabdriver_stopped_using_the_actor_scheduler():
    """jabdriver must not resurrect the drip-fed pump.

    Three names, each checked where it would live if it came back: the import is a
    module attribute of ``pyjab.jabdriver``, and ``_run_actor_sched`` was a method
    on ``JABDriver``.  ``setup_msg_pump`` was a ``Win32Utils`` method, and
    ``test_generator_pump_and_its_events_are_gone`` already covers it.

    The text version this replaces went red if the word appeared anywhere in the
    file -- including a comment explaining why the scheduler was removed.
    """
    assert not hasattr(JABDRIVER_MODULE, "ActorScheduler")
    assert not hasattr(JABDriver, "_run_actor_sched")


def _pump_is_called(method) -> bool:
    """True when *method* calls ``self._pump_messages(...)`` in its own body.

    A call nested inside another function does not count: a pump in a callback that
    the loop happens never to invoke is not a pump in the loop.
    """
    def walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            yield child
            yield from walk(child)

    for node in walk(method):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "_pump_messages"
            and isinstance(func.value, ast.Name)
            and func.value.id == "self"
        ):
            return True
    return False


def test_every_jabdriver_wait_loop_pumps_messages():
    """Waiting is exactly when a new window or dialog has to be noticed.

    Read from the syntax tree, not from the text: a comment naming
    ``self._pump_messages()`` satisfies a substring check while the loop no longer
    pumps anything, which is a false pass.  An AST call node cannot be faked by
    prose.

    Every ``wait_*`` method is required, not a remembered list of three, so a wait
    loop added later is covered the moment it is named ``wait_*`` -- and the pump
    cannot be dropped from one loop while another keeps the count up, which is what
    the counted-substring version allowed.  ``init_jab`` is named explicitly
    because its first pump has to follow ``Windows_run()``, which is what arms COM
    delivery on this thread; it is not a ``wait_*`` and nothing else would cover it.
    """
    source = JABDRIVER_SRC.read_text(encoding="utf-8")
    methods = {
        node.name: node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    wait_loops = [name for name in methods if name.startswith("wait_")]
    assert wait_loops, "no wait_* method in jabdriver.py; has it been renamed?"
    assert "init_jab" in methods, "init_jab is gone from jabdriver.py; has it been renamed?"

    missing = [
        name for name in wait_loops + ["init_jab"] if not _pump_is_called(methods[name])
    ]
    assert not missing, (
        f"{', '.join(missing)} never call self._pump_messages(), so accessibility "
        "events delivered through COM are not serviced there"
    )


def test_wait_until_element_exist_backs_off_between_polls(monkeypatch):
    """It used to spin with no sleep at all (issues #29 and #33).

    Behavioural, not textual.  The driver is built with ``__new__`` so ``__init__``
    never runs -- that connects to the bridge and writes
    ``~/.accessibility.properties`` -- and its lookup is made to always miss.  The
    clock and ``sleep`` are the module's own names, replaced here, so a wait that
    polls without backing off shows up as a missing sleep call rather than as a
    fixed number of characters read out of the file.

    The window a text check anchored also broke on ``sleep(`` appearing anywhere in
    the first 2000 characters, which ~4 lines of docstring was enough to do.
    """
    driver = JABDriver.__new__(JABDriver)
    driver.find_element = MagicMock(side_effect=JABException("not found"))
    driver._pump_messages = MagicMock()
    driver.logger = MagicMock()
    driver.latest_log = None

    # start=0.0; first poll's elapsed check 0.0 -> sleep; second poll's 5.0 -> timeout.
    ticks = iter([0.0, 0.0, 5.0])
    monkeypatch.setattr(JABDRIVER_MODULE, "time", lambda: next(ticks, 5.0))
    slept = MagicMock()
    monkeypatch.setattr(JABDRIVER_MODULE, "sleep", slept)

    with pytest.raises(JABException):
        driver.wait_until_element_exist(
            by="name", value="gone", timeout=1, poll_interval=0.25
        )

    slept.assert_called_once_with(0.25)
    assert driver._pump_messages.call_count == 2, (
        "every poll has to service the message queue"
    )


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
