from pyjab.common.logger import Logger
from pyjab.common.win32utils import Win32Utils


class ShortcutKeys(object):
    """This will provide generic common shortcut keys(combinations)
    with Win32 API.

    NOTICE: Most of the shortcut keys from Microsfot Windows Shortcut Keys.
    May not work in Java Application.
    """

    def __init__(self) -> None:
        self.logger = Logger("pyjab")
        self.win32_utils = Win32Utils()
        self.press_hold_release_key = self.win32_utils._press_hold_release_key
        self.press_key = self.win32_utils._press_key

    def cut(self) -> None:
        self.logger.debug("Send Shortcut Key 'Cut'(Ctrl+X)")
        self.win32_utils._press_hold_release_key("ctrl", "x")

    def copy(self) -> None:
        self.logger.debug("Send Shortcut Key 'Copy'(Ctrl+C)")
        self.win32_utils._press_hold_release_key("ctrl", "c")

    def paste(self) -> None:
        self.logger.debug("Send Shortcut Key 'Paste'(Ctrl+V)")
        self.win32_utils._press_hold_release_key("ctrl", "v")

    def undo(self) -> None:
        self.logger.debug("Send Shortcut Key 'Undo'(Ctrl+Z)")
        self.win32_utils._press_hold_release_key("ctrl", "z")

    def popup_menu(self) -> None:
        self.logger.debug("Send Shortcut Key 'Popup Menu'(Alt+Space)")
        self.win32_utils._press_hold_release_key("alt", "spacebar")

    def back(self) -> None:
        self.logger.debug("Send Shortcut Key 'Back'(Alt+Left Arrow)")
        self.win32_utils._press_hold_release_key("alt", "left_arrow")

    def forward(self) -> None:
        self.logger.debug("Send Shortcut Key 'Forward'(Alt+Right Arrow)")
        self.win32_utils._press_hold_release_key("alt", "right_arrow")

    def move_screen_up(self) -> None:
        self.logger.debug("Send Shortcut Key 'Move Screen Up'(Alt+Page Up)")
        self.win32_utils._press_hold_release_key("alt", "page_up")

    def move_screen_down(self) -> None:
        self.logger.debug("Send Shortcut Key 'Move Screen Down'(Alt+Page Down)")
        self.win32_utils._press_hold_release_key("alt", "page_down")

    def close_window(self) -> None:
        self.logger.debug("Send Shortcut Key 'Close Window'(Ctrl+F4)")
        self.win32_utils._press_hold_release_key("ctrl", "f4")

    def select_all(self) -> None:
        self.logger.debug("Send Shortcut Key 'Select All'(Ctrl+A)")
        self.win32_utils._press_hold_release_key("ctrl", "a")

    def delete(self) -> None:
        self.logger.debug("Send Shortcut Key 'Delete Selected'(Ctrl+D)")
        self.win32_utils._press_hold_release_key("ctrl", "d")

    def refresh(self) -> None:
        self.logger.debug("Send Shortcut Key 'Refresh'(Ctrl+R)")
        self.win32_utils._press_hold_release_key("ctrl", "r")

    def redo(self) -> None:
        self.logger.debug("Send Shortcut Key 'Redo'(Ctrl+Y)")
        self.win32_utils._press_hold_release_key("ctrl", "y")

    def to_next_word(self) -> None:
        self.logger.debug(
            "Send Shortcut Key 'Move Cursor to Next Word'(Ctrl+Right Arrow)"
        )
        self.win32_utils._press_hold_release_key("ctrl", "right_arrow")

    def to_previous_word(self) -> None:
        self.logger.debug(
            "Send Shortcut Key 'Move Cursor to Previous Word'(Ctrl+Left Arrow)"
        )
        self.win32_utils._press_hold_release_key("ctrl", "left_arrow")

    def to_next_paragraph(self) -> None:
        self.logger.debug(
            "Send Shortcut Key 'Move Cursor to Next Paragraph'(Ctrl+Down Arrow)"
        )
        self.win32_utils._press_hold_release_key("ctrl", "down_arrow")

    def to_previous_paragraph(self) -> None:
        self.logger.debug(
            "Send Shortcut Key 'Move Cursor to Previous Paragraph'(Ctrl+Up Arrow)"
        )
        self.win32_utils._press_hold_release_key("ctrl", "up_arrow")

    def to_end(self) -> None:
        self.logger.debug(
            "Send Shortcut Key 'Move Cursor to End of Document'(Ctrl+End)"
        )
        self.win32_utils._press_hold_release_key("ctrl", "end")

    def to_home(self) -> None:
        self.logger.debug(
            "Send Shortcut Key 'Move Cursor to Home of Document'(Ctrl+Home)"
        )
        self.win32_utils._press_hold_release_key("ctrl", "home")

    def select_to_end(self) -> None:
        self.logger.debug("Send Shortcut Key 'Select to End'(Ctrl+Shift+End)")
        self.win32_utils._press_hold_release_key("ctrl", "shift", "end")

    def select_to_home(self) -> None:
        self.logger.debug("Send Shortcut Key 'Select to Home'(Ctrl+Shift+Home)")
        self.win32_utils._press_hold_release_key("ctrl", "shift", "home")