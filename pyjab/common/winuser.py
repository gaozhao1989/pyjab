from ctypes import WinDLL, windll
from ctypes.wintypes import HWND
from pyjab.common.logger import Logger


class WinUser(object):
    def __init__(self, user32: WinDLL) -> None:
        self.log = Logger(self.__class__.__name__)
        self._user32 = user32 if user32 else windll.user32

    @property
    def user32(self) -> WinDLL:
        return self._user32

    @user32.setter
    def user32(self, user32: WinDLL) -> None:
        self._user32 = user32

    def is_descendant_window(self, parent_hwnd: HWND, child_hwnd: HWND) -> bool:
        is_descendant = parent_hwnd == child_hwnd or self.user32.IsChild(
            parent_hwnd, child_hwnd
        )
        return is_descendant

    def get_foreground_window(self):
        return self.user32.GetForegroundWindow()

    def set_foreground_window(self, hwnd: HWND) -> None:
        self.user32.SetForegroundWindow(hwnd)
    
    
