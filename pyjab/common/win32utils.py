import time
from ctypes.wintypes import HWND
from typing import Dict, Generator
import pythoncom
import win32api
import win32clipboard
import win32con
import win32event
import win32gui
from pyjab.common.logger import Logger
from pyjab.config import TIMEOUT


class Win32Utils(object):
    stop_event = win32event.CreateEvent(None, 0, 0, None)
    other_event = win32event.CreateEvent(None, 0, 0, None)
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
        "right_shift ": 0xA1,
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
        self.logger = Logger(self.__class__.__name__)

    # @contextlib.contextmanager
    def setup_msg_pump(self) -> Generator:
        waitables = self.stop_event, self.other_event
        self.logger.debug("setup message pumpup")
        while True:
            rc = win32event.MsgWaitForMultipleObjects(
                waitables,
                0,  # Wait for all = false, so it waits for anyone
                200,  # Timeout, ms (or win32event.INFINITE)
                win32event.QS_ALLEVENTS,  # Accepts all input
            )
            if rc == win32event.WAIT_OBJECT_0:
                self.logger.debug(
                    "first event listed, the StopEvent, was triggered, must exit"
                )
                break
            elif rc == win32event.WAIT_OBJECT_0 + 1:
                # Our second event listed, "OtherEvent", was set. Do whatever needs
                # to be done -- you can wait on as many kernel-waitable objects as
                # needed (events, locks, processes, threads, notifications, and so on).
                self.logger.debug("second event listed was set")
            elif rc == win32event.WAIT_OBJECT_0 + len(waitables):
                # A windows message is waiting - take care of it. (Don't ask me
                # why a WAIT_OBJECT_MSG isn't defined < WAIT_OBJECT_0...!).
                # This message-serving MUST be done for COM, DDE, and other
                # Windowsy things to work properly!
                self.logger.debug("windows message is waiting")
                if pythoncom.PumpWaitingMessages():
                    self.logger.debug("received a wm_quit message")
                    break
            elif rc == win32event.WAIT_TIMEOUT:
                # Our timeout has elapsed.
                # Do some work here (e.g, poll something you can't thread)
                # or just feel good to be alive.
                self.logger.debug("timeout")
            else:
                raise RuntimeError("unexpected win32wait return value")

            # call functions here, if txtt doesn't take too long. It will
            # be executed at least every 200ms -- possibly a lot more often,
            # depending on the number of Windows messages received.
            try:
                yield
            finally:
                self.logger.debug("teardown message pumpup")
                win32event.SetEvent(self.stop_event)

    def enum_windows(self) -> Dict[HWND, str]:
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

    def get_hwnd_by_title(self, title: str) -> HWND:
        dict_hwnd = self.enum_windows()
        try:
            return list(dict_hwnd.keys())[list(dict_hwnd.values()).index(title)]
        except ValueError:
            self.logger.error("no hwnd found by win title =>'{}'".format(title))
            return None

    def get_title_by_hwnd(self, hwnd: HWND) -> str:
        return win32api.GetWindowText(hwnd)

    def wait_hwnd_by_title(self, title: str, timeout: int = TIMEOUT) -> HWND:
        start = time.time()
        while True:
            hwnd = self.get_hwnd_by_title(title)
            if hwnd:
                return hwnd
            current = time.time()
            elapsed = round(current - start)
            if elapsed >= timeout:
                raise TimeoutError(
                    "no hwnd found by title '{}' in '{}'seconds".format(title, timeout)
                )

    def _set_window_foreground(self, hwnd: HWND) -> None:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(hwnd)

    def _set_window_maximize(self, hwnd: HWND) -> None:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

    def _set_window_minimize(self, hwnd: HWND) -> None:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

    def _set_window_size(self, hwnd: HWND, width: int, height: int) -> None:
        left, top, _, _ = win32gui.GetWindowRect(hwnd)
        win32gui.MoveWindow(hwnd, left, top, width, height, True)

    def _set_window_position(self, hwnd: HWND, left: int, top: int) -> None:
        _, _, right, bottom = win32gui.GetWindowRect(hwnd)
        win32gui.MoveWindow(hwnd, left, top, left - right, top - bottom, True)

    def _get_window_position(self, hwnd: HWND) -> tuple:
        left, top, _, _ = win32gui.GetWindowRect(hwnd)
        return left, top

    def _click_mouse(self, x: int, y: int) -> None:
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def _get_clipboard(self) -> str:
        win32clipboard.OpenClipboard()
        data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return data

    def _set_clipboard(self, text: str) -> None:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        # TODO: error occurs when set clipboard
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        win32clipboard.CloseClipboard()

    def _empty_clipboard(self) -> None:
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
        for key in keys:
            win32api.keybd_event(
                self.virtual_key_code[key], 0, win32con.KEYEVENTF_KEYUP, 0
            )

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
        """simulate keyboard type for specific text.\n
        characters will typed one by one.\n
        NOT RECOMMEND use this func since most of oracle form text field support auto complete\n

        Args:
            text (str): text need type
        """
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
        """Simulates typing text with paste from clipboard.\n
        RECOMMEND use this for oracle form text field typeing.

        Args:
            text (str): text need type
        """
        self._set_clipboard(text=text)
        self._press_hold_release_key("ctrl", "v")
        self._empty_clipboard()
