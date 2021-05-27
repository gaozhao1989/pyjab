from pyjab.common.logger import Logger
from pyjab.common.win32utils import Win32Utils


class ShortcutKeys(object):
    def __init__(self) -> None:
        super().__init__()
        self.logger = Logger(self.__class__.__name__)
        self.win32_utils = Win32Utils()
        self.press_hold_release_key = self.win32_utils._press_hold_release_key
        self.press_key = self.win32_utils._press_key

    # Common shortcut keys
    def clear_text(self) -> None:
        self.logger.debug("send shortcut command clear text")
        self.press_key("home")
        self.press_hold_release_key("ctrl", "shift", "end")
        # TODO: need find out method to clear text for JABElement
        for _ in range(100):
            self.press_key("backspace")

    def paste(self) -> None:
        self.logger.debug("paste text from clipboard")
        self.press_hold_release_key("ctrl", "v")

    # Oracle Form shortcut keys
    def block_menu(self) -> None:
        self.logger.debug("send shortcut command block menu")
        self.press_hold_release_key("ctrl", "b")

    def clear_block(self) -> None:
        self.logger.debug("send shortcut command clear block")
        self.press_key("F7")

    def clear_field(self) -> None:
        self.logger.debug("send shortcut command clear field")
        self.press_key("F5")

    def clear_form(self) -> None:
        self.logger.debug("send shortcut command clear form")
        self.press_key("F8")

    def clear_record(self) -> None:
        self.logger.debug("send shortcut command clear record")
        self.press_key("F6")

    def commit(self) -> None:
        self.logger.debug("send shortcut command commit")
        self.press_hold_release_key("ctrl", "s")

    def count_query(self) -> None:
        self.logger.debug("send shortcut command count query")
        self.press_key("F12")

    def delete_record(self) -> None:
        self.logger.debug("send shortcut command delete record")
        self.press_hold_release_key("ctrl", "up_arrow")

    def display_error(self) -> None:
        self.logger.debug("send shortcut command display error")
        self.press_hold_release_key("shift", "ctrl", "e")

    def down(self) -> None:
        self.logger.debug("send shortcut command down")
        self.press_key("down_arrow")

    def duplicate_field(self) -> None:
        self.logger.debug("send shortcut command duplicate field")
        self.press_hold_release_key("shift", "F5")

    def duplicate_record(self) -> None:
        self.logger.debug("send shortcut command duplicate record")
        self.press_hold_release_key("shift", "F6")

    def edit(self) -> None:
        self.logger.debug("send shortcut command edit")
        self.press_hold_release_key("ctrl", "e")

    def enter_query(self) -> None:
        self.logger.debug("send shortcut command enter query")
        self.press_key("F11")

    def execute_query(self) -> None:
        self.logger.debug("send shortcut command execute query")
        self.press_hold_release_key("ctrl", "F11")

    def _exit(self) -> None:
        self.logger.debug("send shortcut command exit")
        self.press_key("F4")

    def _help(self) -> None:
        self.logger.debug("send shortcut command help")
        self.press_hold_release_key("ctrl", "h")

    def insert_record(self) -> None:
        self.logger.debug("send shortcut command insert record")
        self.press_hold_release_key("ctrl", "down_arrow")

    def list_of_values(self) -> None:
        self.logger.debug("send shortcut command list of values")
        self.press_hold_release_key("ctrl", "l")

    def list_tab_pages(self) -> None:
        self.logger.debug("send shortcut command list tab pages")
        self.press_key("F2")

    def next_block(self) -> None:
        self.logger.debug("send shortcut command next block")
        self.press_hold_release_key("shift", "page_down")

    def next_field(self) -> None:
        self.logger.debug("send shortcut command next field")
        self.press_key("tab")

    def next_primary_key(self) -> None:
        self.logger.debug("send shortcut command next primary key")
        self.press_hold_release_key("shift", "F7")

    def next_record(self) -> None:
        self.logger.debug("send shortcut command next record")
        self.press_key("down_arrow")

    def next_set_of_records(self) -> None:
        self.logger.debug("send shortcut command next set of records")
        self.press_key("shift", "F8")

    def previous_block(self) -> None:
        self.logger.debug("send shortcut command previous block")
        self.press_key("shift", "page_up")

    def previous_field(self) -> None:
        self.logger.debug("send shortcut command previous field")
        self.press_key("shift", "tab")

    def previous_record(self) -> None:
        self.logger.debug("send shortcut command previous record")
        self.press_key("shift", "up_arrow")

    def _print(self) -> None:
        self.logger.debug("send shortcut command print")
        self.press_key("ctrl", "p")

    def _return(self) -> None:
        self.logger.debug("send shortcut command return")
        self.press_key("clear")

    def scroll_down(self) -> None:
        self.logger.debug("send shortcut command scroll down")
        self.press_key("page_down")

    def scroll_up(self) -> None:
        self.logger.debug("send shortcut command scroll up")
        self.press_key("page_up")

    def show_keys(self) -> None:
        self.logger.debug("send shortcut command show keys")
        self.press_key("ctrl", "k")

    def up(self) -> None:
        self.logger.debug("send shortcut command up")
        self.press_key("up_arrow")

    def update_record(self) -> None:
        self.logger.debug("send shortcut command update record")
        self.press_key("ctrl", "u")
