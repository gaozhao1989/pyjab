import ctypes
import fnmatch
import time
from ctypes.wintypes import HWND
from typing import Dict, List, Optional
import pythoncom
import win32api
import win32clipboard
import win32com.client
import win32con
import win32gui
from pyjab.common.logger import Logger
from pyjab.common.singleton import singleton
from pyjab.config import TIMEOUT


def double_click_gap() -> float:
    """Half the system double-click interval, in seconds.

    Half of it is safely inside the window whether the setting is 200ms or 900ms,
    which is why the division is by 2000 rather than 1000.

    Through ``ctypes`` and ``user32`` rather than ``win32api``.  ``GetDoubleClickTime``
    is a ``user32`` export and is always there; **``win32api`` does not expose it at
    all** on a current pywin32.  That is how this was found: the GUI suite failed on
    Windows with ``AttributeError: module 'win32api' has no attribute
    'GetDoubleClickTime'`` while CI stayed green, because CI never runs the GUI
    suite.

    Module level rather than a staticmethod so that it can be called without going
    through the ``@singleton`` wrapper -- ``functools.wraps`` copies the class
    dictionary onto that wrapper, and a ``staticmethod`` object is not callable
    there on Python 3.9.
    """
    return ctypes.windll.user32.GetDoubleClickTime() / 2000.0


@singleton
class Win32Utils(object):
    virtual_key_code = {
        "backspace": 0x08,
        "tab": 0x09,
        "clear": 0x0C,
        "enter": 0x0D,
        "shift": 0x10,
        "ctrl": 0x11,
        "alt": 0x12,
        "pause": 0x13,
        "caps_lock": 0x14,
        "esc": 0x1B,
        "spacebar": 0x20,
        "page_up": 0x21,
        "page_down": 0x22,
        "end": 0x23,
        "home": 0x24,
        "left_arrow": 0x25,
        "up_arrow": 0x26,
        "right_arrow": 0x27,
        "down_arrow": 0x28,
        "select": 0x29,
        "print": 0x2A,
        "execute": 0x2B,
        "print_screen": 0x2C,
        "ins": 0x2D,
        "del": 0x2E,
        "help": 0x2F,
        "0": 0x30,
        "1": 0x31,
        "2": 0x32,
        "3": 0x33,
        "4": 0x34,
        "5": 0x35,
        "6": 0x36,
        "7": 0x37,
        "8": 0x38,
        "9": 0x39,
        "a": 0x41,
        "b": 0x42,
        "c": 0x43,
        "d": 0x44,
        "e": 0x45,
        "f": 0x46,
        "g": 0x47,
        "h": 0x48,
        "i": 0x49,
        "j": 0x4A,
        "k": 0x4B,
        "l": 0x4C,
        "m": 0x4D,
        "n": 0x4E,
        "o": 0x4F,
        "p": 0x50,
        "q": 0x51,
        "r": 0x52,
        "s": 0x53,
        "t": 0x54,
        "u": 0x55,
        "v": 0x56,
        "w": 0x57,
        "x": 0x58,
        "y": 0x59,
        "z": 0x5A,
        "numpad_0": 0x60,
        "numpad_1": 0x61,
        "numpad_2": 0x62,
        "numpad_3": 0x63,
        "numpad_4": 0x64,
        "numpad_5": 0x65,
        "numpad_6": 0x66,
        "numpad_7": 0x67,
        "numpad_8": 0x68,
        "numpad_9": 0x69,
        "multiply_key": 0x6A,
        "add_key": 0x6B,
        "separator_key": 0x6C,
        "subtract_key": 0x6D,
        "decimal_key": 0x6E,
        "divide_key": 0x6F,
        "F1": 0x70,
        "F2": 0x71,
        "F3": 0x72,
        "F4": 0x73,
        "F5": 0x74,
        "F6": 0x75,
        "F7": 0x76,
        "F8": 0x77,
        "F9": 0x78,
        "F10": 0x79,
        "F11": 0x7A,
        "F12": 0x7B,
        "F13": 0x7C,
        "F14": 0x7D,
        "F15": 0x7E,
        "F16": 0x7F,
        "F17": 0x80,
        "F18": 0x81,
        "F19": 0x82,
        "F20": 0x83,
        "F21": 0x84,
        "F22": 0x85,
        "F23": 0x86,
        "F24": 0x87,
        "num_lock": 0x90,
        "scroll_lock": 0x91,
        "left_shift": 0xA0,
        # Was "right_shift " with a trailing space, so looking up the key by its
        # actual name raised KeyError.
        "right_shift": 0xA1,
        "left_control": 0xA2,
        "right_control": 0xA3,
        "left_menu": 0xA4,
        "right_menu": 0xA5,
        "browser_back": 0xA6,
        "browser_forward": 0xA7,
        "browser_refresh": 0xA8,
        "browser_stop": 0xA9,
        "browser_search": 0xAA,
        "browser_favorites": 0xAB,
        "browser_start_and_home": 0xAC,
        "volume_mute": 0xAD,
        "volume_Down": 0xAE,
        "volume_up": 0xAF,
        "next_track": 0xB0,
        "previous_track": 0xB1,
        "stop_media": 0xB2,
        "play/pause_media": 0xB3,
        "start_mail": 0xB4,
        "select_media": 0xB5,
        "start_application_1": 0xB6,
        "start_application_2": 0xB7,
        "attn_key": 0xF6,
        "crsel_key": 0xF7,
        "exsel_key": 0xF8,
        "play_key": 0xFA,
        "zoom_key": 0xFB,
        "clear_key": 0xFE,
        # VK_OEM_PLUS is the '='/ '+' key: '=' is the unshifted character, '+'
        # is shift plus it. Only '+' was in this table, so _send_keys()'s own
        # entry for '+' -- which expands to ('left_shift', '=') -- raised
        # KeyError, and typing a plus sign failed.
        "=": 0xBB,
        "+": 0xBB,
        ",": 0xBC,
        "-": 0xBD,
        ".": 0xBE,
        "/": 0xBF,
        "`": 0xC0,
        ";": 0xBA,
        "[": 0xDB,
        "\\": 0xDC,
        "]": 0xDD,
        "'": 0xDE,
    }

    def __init__(self) -> None:
        self.logger = Logger("pyjab")

    def pump_messages(self) -> bool:
        """Service every Windows/COM message currently queued for this thread.

        The Java Access Bridge is COM based, and COM callbacks -- including the
        accessibility events that announce newly opened windows and dialogs --
        are delivered to the thread that called ``Windows_run()``.  That thread
        must therefore service its message queue, or those events never arrive
        and pyjab cannot see a window that opens later.

        This is deliberately a plain, non-blocking call rather than the
        generator driven by :class:`~pyjab.common.actorscheduler.ActorScheduler`
        that it replaces:

        * the old pump only ran while pyjab was waiting for the *first* window,
          so nothing was serviced once element lookups started;
        * it blocked for up to 200ms per invocation, even when idle;
        * every call built a fresh generator that was discarded immediately, so
          no pump state survived between calls, and each discarded generator
          signalled the shared stop event -- which made every second call a
          no-op.

        Call it as often as convenient; with an empty queue it is very cheap.

        Returns:
            bool: True if a WM_QUIT was seen, otherwise False.
        """
        try:
            return bool(pythoncom.PumpWaitingMessages())
        except pythoncom.com_error:
            # No COM message queue on this thread -- COM was never initialised
            # here, which happens when the caller is not the thread that ran
            # Windows_run().  Nothing to service; not an error.
            self.logger.debug("no COM message queue on this thread, nothing to pump")
            return False

    @staticmethod
    def enum_windows() -> Dict[HWND, str]:
        dict_hwnd = dict()

        def get_all_hwnds(hwnd, _):
            if (
                win32gui.IsWindow(hwnd)
                and win32gui.IsWindowEnabled(hwnd)
                and win32gui.IsWindowVisible(hwnd)
            ):
                dict_hwnd.update({hwnd: win32gui.GetWindowText(hwnd)})

        win32gui.EnumWindows(get_all_hwnds, 0)
        return dict_hwnd

    def get_hwnd_by_title(self, title: str) -> Optional[HWND]:
        if possible_matches := self.get_hwnds_by_title(title):
            return possible_matches[0]
        return None

    def get_hwnds_by_title(self, title: str) -> List[HWND]:
        dict_hwnd = self.enum_windows()
        return [hwnd for hwnd, win_title in dict_hwnd.items() if fnmatch.fnmatch(win_title, title)]

    @staticmethod
    def get_title_by_hwnd(hwnd: HWND) -> str:
        return win32api.GetWindowText(hwnd)

    def wait_hwnd_by_title(self, title: str, timeout: int = TIMEOUT) -> HWND:
        latest_log = ""
        start = time.time()
        while True:
            if hwnd := self.get_hwnd_by_title(title):
                return hwnd
            error_log = f"no hwnd found by win title =>'{title}'"
            if latest_log != error_log:
                self.logger.debug(error_log)
                latest_log = error_log
            current = time.time()
            elapsed = round(current - start)
            if elapsed >= timeout:
                raise TimeoutError(
                    f"no hwnd found by title '{title}' in '{timeout}' seconds"
                )

    @staticmethod
    def _get_foreground_window() -> HWND:
        return win32gui.GetForegroundWindow()

    def _set_window_foreground(self, hwnd: HWND) -> None:
        if hwnd == self._get_foreground_window():
            return
        win32com.client.Dispatch("WScript.Shell").SendKeys(' ')
        win32gui.SetForegroundWindow(hwnd)

    @staticmethod
    def _set_window_maximize(hwnd: HWND) -> None:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

    @staticmethod
    def _set_window_minimize(hwnd: HWND) -> None:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

    @staticmethod
    def _set_window_size(hwnd: HWND, width: int, height: int) -> None:
        left, top, _, _ = win32gui.GetWindowRect(hwnd)
        win32gui.MoveWindow(hwnd, left, top, width, height, True)

    @staticmethod
    def _set_window_position(hwnd: HWND, left: int, top: int) -> None:
        """Move the window to (left, top), keeping its current size."""
        # The current position has to be kept, not discarded: the size is the
        # distance between the *existing* edges. This previously computed
        # left - right and top - bottom from the requested position, which is
        # negative for any real window, so MoveWindow was asked for a negative
        # width and height.
        current_left, current_top, right, bottom = win32gui.GetWindowRect(hwnd)
        win32gui.MoveWindow(
            hwnd, left, top, right - current_left, bottom - current_top, True
        )

    @staticmethod
    def _get_window_position(hwnd: HWND) -> tuple:
        left, top, _, _ = win32gui.GetWindowRect(hwnd)
        return left, top

    @staticmethod
    def _click_mouse(x: int, y: int, hold: int = 0, button: str = "left") -> None:
        mouse_down_act = win32con.MOUSEEVENTF_LEFTDOWN if button == "left" else win32con.MOUSEEVENTF_RIGHTDOWN
        mouse_up_act = win32con.MOUSEEVENTF_LEFTUP if button == "left" else win32con.MOUSEEVENTF_RIGHTUP
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(mouse_down_act, x, y, 0, 0)
        if hold:
            time.sleep(hold)
        win32api.mouse_event(mouse_up_act, x, y, 0, 0)

    @staticmethod
    def _double_click_mouse(x: int, y: int) -> None:
        """Two clicks at the same place, close enough to count as one double click.

        The gap has to fall inside the system's double-click interval, which is
        configurable and therefore not a constant; see :func:`double_click_gap`.
        """
        gap = double_click_gap()
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
        time.sleep(gap)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    @staticmethod
    def _get_clipboard() -> str:
        win32clipboard.OpenClipboard()
        data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return data

    @staticmethod
    def _set_clipboard(text: str) -> None:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        # TODO: error occurs when set clipboard
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        win32clipboard.CloseClipboard()

    @staticmethod
    def _empty_clipboard() -> None:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.CloseClipboard()

    def _press_key(self, *keys) -> None:
        """
        one press, one release.\n
        accepts as many arguments as you want. e.g. press_key('left_arrow', 'a','b').
        """
        for key in keys:
            win32api.keybd_event(self.virtual_key_code[key], 0, 0, 0)
            win32api.keybd_event(
                self.virtual_key_code[key], 0, win32con.KEYEVENTF_KEYUP, 0
            )

    def _press_and_hold_key(self, *keys) -> None:
        """
        press and hold. Do NOT release.\n
        accepts as many arguments as you want.\n
        e.g. press_and_hold_key('left_arrow', 'a','b').
        """
        for key in keys:
            win32api.keybd_event(self.virtual_key_code[key], 0, 0, 0)

    def _press_hold_release_key(self, *keys) -> None:
        """
        press and hold passed in strings. Once held, release\n
        accepts as many arguments as you want.\n
        e.g. press_hold_release_key('left_arrow', 'a','b').\n

        this is useful for issuing shortcut command or shift commands.\n
        e.g. press_hold_release_key('ctrl', 'alt', 'del'), press_hold_release_key('shift','a')
        """
        for key in keys:
            win32api.keybd_event(self.virtual_key_code[key], 0, 0, 0)
            time.sleep(0.05)
        for key in keys:
            win32api.keybd_event(
                self.virtual_key_code[key], 0, win32con.KEYEVENTF_KEYUP, 0
            )
            time.sleep(0.1)

    def _release_key(self, *keys) -> None:
        """
        release depressed keys\n
        accepts as many arguments as you want.\n
        e.g. release_key('left_arrow', 'a','b').
        """
        for key in keys:
            win32api.keybd_event(
                self.virtual_key_code[key], 0, win32con.KEYEVENTF_KEYUP, 0
            )

    def _send_keys(self, text: str) -> None:
        """Simulate keyboard type for specific text.

        Characters will be typed one by one.

        None-ASCII characters will directly paste to the field(check the security option before).

        NOT RECOMMEND use this func for the text field which support auto complete.

        Args:
            text (str): text need type
        """
        if not text.isascii():
            self._paste_text(text=text)
            return
        sp_key = {
            " ": {"func": self._press_key, "keys": ["spacebar"]},
            "~": {"func": self._press_hold_release_key, "keys": ["left_shift", "`"]},
            "!": {"func": self._press_hold_release_key, "keys": ["left_shift", "1"]},
            "@": {"func": self._press_hold_release_key, "keys": ["left_shift", "2"]},
            "#": {"func": self._press_hold_release_key, "keys": ["left_shift", "3"]},
            "$": {"func": self._press_hold_release_key, "keys": ["left_shift", "4"]},
            "%": {"func": self._press_hold_release_key, "keys": ["left_shift", "5"]},
            "^": {"func": self._press_hold_release_key, "keys": ["left_shift", "6"]},
            "&": {"func": self._press_hold_release_key, "keys": ["left_shift", "7"]},
            "*": {"func": self._press_hold_release_key, "keys": ["left_shift", "8"]},
            "(": {"func": self._press_hold_release_key, "keys": ["left_shift", "9"]},
            ")": {"func": self._press_hold_release_key, "keys": ["left_shift", "0"]},
            "_": {"func": self._press_hold_release_key, "keys": ["left_shift", "-"]},
            "+": {"func": self._press_hold_release_key, "keys": ["left_shift", "="]},
            "{": {"func": self._press_hold_release_key, "keys": ["left_shift", "["]},
            "}": {"func": self._press_hold_release_key, "keys": ["left_shift", "]"]},
            "|": {"func": self._press_hold_release_key, "keys": ["left_shift", "\\"]},
            ":": {"func": self._press_hold_release_key, "keys": ["left_shift", ";"]},
            '"': {"func": self._press_hold_release_key, "keys": ["left_shift", "'"]},
            "<": {"func": self._press_hold_release_key, "keys": ["left_shift", ","]},
            ">": {"func": self._press_hold_release_key, "keys": ["left_shift", "."]},
            "?": {"func": self._press_hold_release_key, "keys": ["left_shift", "/"]},
            "A": {"func": self._press_hold_release_key, "keys": ["left_shift", "a"]},
            "B": {"func": self._press_hold_release_key, "keys": ["left_shift", "b"]},
            "C": {"func": self._press_hold_release_key, "keys": ["left_shift", "c"]},
            "D": {"func": self._press_hold_release_key, "keys": ["left_shift", "d"]},
            "E": {"func": self._press_hold_release_key, "keys": ["left_shift", "e"]},
            "F": {"func": self._press_hold_release_key, "keys": ["left_shift", "f"]},
            "G": {"func": self._press_hold_release_key, "keys": ["left_shift", "g"]},
            "H": {"func": self._press_hold_release_key, "keys": ["left_shift", "h"]},
            "I": {"func": self._press_hold_release_key, "keys": ["left_shift", "i"]},
            "J": {"func": self._press_hold_release_key, "keys": ["left_shift", "j"]},
            "K": {"func": self._press_hold_release_key, "keys": ["left_shift", "k"]},
            "L": {"func": self._press_hold_release_key, "keys": ["left_shift", "l"]},
            "M": {"func": self._press_hold_release_key, "keys": ["left_shift", "m"]},
            "N": {"func": self._press_hold_release_key, "keys": ["left_shift", "n"]},
            "O": {"func": self._press_hold_release_key, "keys": ["left_shift", "o"]},
            "P": {"func": self._press_hold_release_key, "keys": ["left_shift", "p"]},
            "Q": {"func": self._press_hold_release_key, "keys": ["left_shift", "q"]},
            "R": {"func": self._press_hold_release_key, "keys": ["left_shift", "r"]},
            "S": {"func": self._press_hold_release_key, "keys": ["left_shift", "s"]},
            "T": {"func": self._press_hold_release_key, "keys": ["left_shift", "t"]},
            "U": {"func": self._press_hold_release_key, "keys": ["left_shift", "u"]},
            "V": {"func": self._press_hold_release_key, "keys": ["left_shift", "v"]},
            "W": {"func": self._press_hold_release_key, "keys": ["left_shift", "w"]},
            "X": {"func": self._press_hold_release_key, "keys": ["left_shift", "x"]},
            "Y": {"func": self._press_hold_release_key, "keys": ["left_shift", "y"]},
            "Z": {"func": self._press_hold_release_key, "keys": ["left_shift", "z"]},
        }
        for txt in str(text):
            key_map = sp_key.get(txt, dict(func=self._press_key, keys=[txt]))
            func = key_map.get("func")
            keys = key_map.get("keys")
            func(*keys)

    def _paste_text(self, text: str) -> None:
        """Simulates typing text with paste from clipboard.

        RECOMMEND use this for text field directly typing or another launage typing support.

        Args:
            text (str): text need type
        """
        self._set_clipboard(text=str(text))
        self._press_hold_release_key("ctrl", "v")
        self._empty_clipboard()
