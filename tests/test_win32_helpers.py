"""Tests for the Win32 helper logic in pyjab.common.win32utils.

Only pure logic is covered here -- key lookup and geometry. Anything that needs
a real window, a real desktop or a real JAB connection belongs in the GUI suite.
"""

import string
import sys
from unittest.mock import patch

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import
from pyjab.common.win32utils import Win32Utils

# Win32Utils is @singleton, so class-level access goes through __wrapped__.
Win32UtilsClass = Win32Utils.__wrapped__

#: The module whose pywin32 names the code under test actually calls.
WIN32UTILS_MODULE = sys.modules["pyjab.common.win32utils"]


@pytest.fixture
def utils():
    return Win32UtilsClass()


# ---------------------------------------------------------------------------
# The virtual key table
# ---------------------------------------------------------------------------

def test_no_key_name_is_padded_with_whitespace(utils):
    """Regression: the map held "right_shift " with a trailing space.

    Nothing could look that up, so the right shift key was unreachable.
    """
    padded = [name for name in utils.virtual_key_code if name != name.strip()]

    assert padded == [], f"key names with stray whitespace: {padded}"


def test_both_shift_keys_are_reachable(utils):
    assert "left_shift" in utils.virtual_key_code
    assert "right_shift" in utils.virtual_key_code


def test_every_keystroke_send_keys_asks_for_is_mapped(utils):
    """Every key name _send_keys requests must exist in the virtual key table.

    Regression: the character '+' expands to ('left_shift', '='), but '=' was
    not in the table, so typing a plus sign raised KeyError.
    """
    printable = string.ascii_letters + string.digits + string.punctuation + " "
    requested = []

    def record(*keys):
        requested.extend(keys)

    with patch.object(Win32UtilsClass, "_press_key", side_effect=record), \
            patch.object(Win32UtilsClass, "_press_hold_release_key", side_effect=record):
        utils._send_keys(printable)

    assert requested, "the character table produced no keystrokes at all"
    missing = sorted({k for k in requested if k not in utils.virtual_key_code})
    assert missing == [], f"_send_keys asks for unmapped keys: {missing}"


def test_plus_sign_is_reachable(utils):
    """The specific character that used to fail."""
    requested = []

    with patch.object(Win32UtilsClass, "_press_key",
                      side_effect=lambda *k: requested.extend(k)), \
            patch.object(Win32UtilsClass, "_press_hold_release_key",
                         side_effect=lambda *k: requested.extend(k)):
        utils._send_keys("+")

    assert requested == ["left_shift", "="]


def test_non_ascii_text_is_pasted_instead_of_typed(utils):
    with patch.object(Win32UtilsClass, "_paste_text") as paste:
        utils._send_keys("中文")

    paste.assert_called_once()


# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------

def test_set_window_position_keeps_the_current_size(utils):
    """Regression: the size was computed as left - right and top - bottom.

    Those are negative for any window of non-zero size, so MoveWindow was asked
    to make the window a negative number of pixels wide.
    """
    with patch.object(WIN32UTILS_MODULE, "win32gui") as win32gui:
        win32gui.GetWindowRect.return_value = (100, 200, 500, 700)

        utils._set_window_position(hwnd=1234, left=10, top=20)

    assert win32gui.MoveWindow.call_args.args == (1234, 10, 20, 400, 500, True)


def test_set_window_size_uses_the_requested_size(utils):
    with patch.object(WIN32UTILS_MODULE, "win32gui") as win32gui:
        win32gui.GetWindowRect.return_value = (100, 200, 500, 700)

        utils._set_window_size(hwnd=1234, width=300, height=400)

    assert win32gui.MoveWindow.call_args.args == (1234, 100, 200, 300, 400, True)
