"""End-to-end tests for the 1.3.0 message pump rewrite.

These drive real Java Swing applications and therefore need Windows, a JDK, an
interactive desktop session and network access to fetch the Oracle demo
applications.  They are part of the opt-in GUI suite:

    set PYJAB_RUN_GUI_TESTS=1
    pytest tests/test_message_pump_gui.py -v

What is being checked
---------------------
Java Access Bridge is COM based.  The accessibility events that announce a
window or dialog are delivered through the COM message queue of the thread that
called ``Windows_run()``.  Before 1.3.0 pyjab only serviced that queue while
waiting for the *first* window, and every second servicing call was a no-op, so
anything opening later could go unnoticed.

The headline test is
``test_new_window_is_found_after_a_plain_click``.  The pre-1.3.0 comment in
``test_components.py`` says it best:

    "Doesn't seem to recognise the new window unless click is simulated"

That workaround should no longer be necessary.
"""

import time

import pytest

from pyjab.common.by import By
from pyjab.common.exceptions import JABException
from pyjab.common.role import Role
from pyjab.common.states import States
from pyjab.jabdriver import JABDriver
from tests.conftest import OracleApp

pytestmark = pytest.mark.gui

# The dialog opened by Oracle's DialogDemo.
DIALOG_WINDOW_TITLE = "Message"


@pytest.fixture(autouse=True, scope="module")
def _fetch_demo_applications(test_jnlp_files):
    """Every test here drives an Oracle demo, so download them once."""
    return test_jnlp_files


def _first_showing_push_button(driver: JABDriver):
    """The button Oracle's demos use to open their popup."""
    for element in driver.find_elements_by_role(Role.PUSH_BUTTON):
        if States.SHOWING in element.states:
            return element
    raise AssertionError("the demo window has no showing push button")


# ---------------------------------------------------------------------------
# The pump itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("oracle_app", [OracleApp.BUTTON], indirect=True)
def test_pump_messages_is_safe_to_call(oracle_app: JABDriver):
    """Servicing the queue must be harmless and repeatable on a live app."""
    for _ in range(5):
        oracle_app._pump_messages()


@pytest.mark.parametrize("oracle_app", [OracleApp.BUTTON], indirect=True)
def test_repeated_lookups_do_not_alternate(oracle_app: JABDriver):
    """Regression: every second pump used to be a silent no-op.

    The old pump built a fresh generator per call and discarded it, and the
    discarded generator set the shared stop event.  The next call therefore saw
    a signalled event and returned without pumping.  Interleaving a pump with a
    lookup is the pattern that exposed it.
    """
    for attempt in range(6):
        oracle_app._pump_messages()
        element = oracle_app.find_element_by_role(Role.PUSH_BUTTON)
        assert element is not None, f"lookup failed on attempt {attempt}"


# ---------------------------------------------------------------------------
# Issue #29 / #33: waiting must not spin the CPU
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("oracle_app", [OracleApp.BUTTON], indirect=True)
def test_wait_until_element_exist_backs_off(oracle_app: JABDriver):
    """wait_until_element_exist used to be a tight loop with no sleep.

    It re-walked the whole accessibility tree as fast as the CPU allowed.
    Comparing process CPU time against wall-clock time distinguishes sleeping
    from spinning, which a wall-clock assertion alone cannot do.
    """
    wall_start = time.time()
    cpu_start = time.process_time()

    with pytest.raises(JABException):
        oracle_app.wait_until_element_exist(
            By.NAME, "pyjab-definitely-not-here", timeout=3
        )

    wall = time.time() - wall_start
    cpu = time.process_time() - cpu_start

    assert wall >= 2.5, f"the wait returned after only {wall:.2f}s of a 3s timeout"
    assert cpu < wall * 0.5, (
        f"the wait burned {cpu:.2f}s of CPU in {wall:.2f}s of wall-clock time, "
        "so it is still spinning instead of backing off"
    )


@pytest.mark.parametrize("oracle_app", [OracleApp.BUTTON], indirect=True)
def test_wait_until_element_exist_finds_an_existing_element(oracle_app: JABDriver):
    """The common path must still return promptly."""
    wall_start = time.time()
    element = oracle_app.wait_until_element_exist(By.ROLE, Role.PUSH_BUTTON, timeout=10)
    wall = time.time() - wall_start

    assert element is not None
    assert wall < 5, f"finding an element that is already present took {wall:.2f}s"


# ---------------------------------------------------------------------------
# Issues #56 / #74: a window that opens later has to be noticed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("oracle_app", [OracleApp.DIALOG], indirect=True)
def test_new_window_is_found_after_a_plain_click(oracle_app: JABDriver):
    """The 1.3.0 fix, stated directly.

    Clicking with the default ``simulate=False`` goes through the Java Access
    Bridge accessibility action rather than the mouse.  Before 1.3.0 that was
    not enough to make the newly opened dialog discoverable -- hence the
    "unless click is simulated" workaround -- because the COM queue was never
    serviced once lookups had started.

    The dialog is a separate top-level window, so it is bound by title, which
    exercises ``wait_java_window_by_title()`` -- one of the places that now
    pumps.
    """
    button = _first_showing_push_button(oracle_app)
    button.click()  # simulate=False on purpose: this is the assertion

    try:
        popup = JABDriver(title=DIALOG_WINDOW_TITLE, timeout=15)
    except TimeoutError as exc:
        pytest.fail(
            "the dialog opened by a non-simulated click was not found within "
            f"15s: {exc}\n"
            "This is the behaviour 1.3.0 set out to fix. Please report it with "
            "the output of tools/verify_message_pump.py."
        )

    assert popup.find_element_by_role(Role.DIALOG) is not None


@pytest.mark.parametrize("oracle_app", [OracleApp.DIALOG], indirect=True)
def test_dialog_is_reachable_after_pumping(oracle_app: JABDriver):
    """After an explicit pump, a freshly opened dialog must be enumerable.

    This is the low-level counterpart to the test above: it does not depend on
    whether the accessibility action itself triggers the dialog.
    """
    button = _first_showing_push_button(oracle_app)
    button.click()

    # Give the dialog a moment, servicing the queue as we go -- exactly what
    # wait_until_element_exist does in production.
    deadline = time.time() + 15
    found = False
    while time.time() < deadline:
        oracle_app._pump_messages()
        if oracle_app.get_java_window_hwnd(title=DIALOG_WINDOW_TITLE):
            found = True
            break
        time.sleep(0.1)

    assert found, (
        f"'{DIALOG_WINDOW_TITLE}' never appeared in the window list within 15s, "
        "even though the message queue was being pumped"
    )


# ---------------------------------------------------------------------------
# 1.2.1 feature, exercised on Windows
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("oracle_app", [OracleApp.BUTTON], indirect=True)
def test_get_focused_element_on_a_live_window(oracle_app: JABDriver):
    """get_focused_element() must return an element or None, never raise."""
    focused = oracle_app.get_focused_element()

    if focused is not None:
        assert focused.role
        assert focused.hwnd == oracle_app.hwnd
