from ctypes.wintypes import HWND
import re
from pyjab.config import (
    ACCESSIBLE_ALT_GRAPH_KEYSTROKE,
    ACCESSIBLE_ALT_KEYSTROKE,
    ACCESSIBLE_BUTTON1_KEYSTROKE,
    ACCESSIBLE_BUTTON2_KEYSTROKE,
    ACCESSIBLE_BUTTON3_KEYSTROKE,
    ACCESSIBLE_CONTROL_KEYSTROKE,
    ACCESSIBLE_META_KEYSTROKE,
    ACCESSIBLE_SHIFT_KEYSTROKE,
)
from pyjab.globalargs import BRIDGE
from pyjab.jabhandler import JABHandler
from pyjab.common.logger import Logger
from pyjab.accessibleinfo import AccessibleContextInfo, AccessibleTextInfo
from pyjab.jabcontext import JABContext

# jab roles
JAB_ROLE_ALERT = "alert"
JAB_ROLE_CANVAS = "canvas"
JAB_ROLE_COLUMN_HEADER = "column header"
JAB_ROLE_COMBO_BOX = "combo box"
JAB_ROLE_DESKTOP_ICON = "desktop icon"
JAB_ROLE_INTERNAL_FRAME = "internal frame"
JAB_ROLE_OPTION_PANE = "option pane"
JAB_ROLE_WINDOW = "window"
JAB_ROLE_FRAME = "frame"
JAB_ROLE_DIALOG = "dialog"
JAB_ROLE_COLOR_CHOOSER = "color chooser"
JAB_ROLE_DIRECTORY_PANE = "directory pane"
JAB_ROLE_FILE_CHOOSER = "file chooser"
JAB_ROLE_FILLER = "filler"
JAB_ROLE_HYPERLINK = "hyperlink"
JAB_ROLE_ICON = "icon"
JAB_ROLE_LABEL = "label"
JAB_ROLE_ROOT_PANE = "root pane"
JAB_ROLE_GLASS_PANE = "glass pane"
JAB_ROLE_LAYERED_PANE = "layered pane"
JAB_ROLE_LIST = "list"
JAB_ROLE_LIST_ITEM = "list item"
JAB_ROLE_MENU_BAR = "menu bar"
JAB_ROLE_POPUP_MENU = "popup menu"
JAB_ROLE_MENU = "menu"
JAB_ROLE_MENU_ITEM = "menu item"
JAB_ROLE_SEPARATOR = "separator"
JAB_ROLE_PAGE_TAB_LIST = "page tab list"
JAB_ROLE_PAGE_TAB = "page tab"
JAB_ROLE_PANEL = "panel"
JAB_ROLE_PROGRESS_BAR = "progress bar"
JAB_ROLE_PASSWORD_TEXT = "password text"
JAB_ROLE_PUSH_BUTTON = "push button"
JAB_ROLE_TOGGLE_BUTTON = "toggle button"
JAB_ROLE_CHECK_BOX = "check box"
JAB_ROLE_RADIO_BUTTON = "radio button"
JAB_ROLE_ROW_HEADER = "row header"
JAB_ROLE_SCROLL_PANE = "scroll pane"
JAB_ROLE_SCROLL_BAR = "scroll bar"
JAB_ROLE_VIEW_PORT = "view port"
JAB_ROLE_SLIDER = "slider"
JAB_ROLE_SPLIT_PANE = "split pane"
JAB_ROLE_TABLE = "table"
JAB_ROLE_TEXT = "text"
JAB_ROLE_TREE = "tree"
JAB_ROLE_TOOL_BAR = "tool bar"
JAB_ROLE_TOOL_TIP = "tool tip"
JAB_ROLE_STATUS_BAR = "status bar"
JAB_ROLE_STATUSBAR = "statusbar"
JAB_ROLE_DATE_EDITOR = "date editor"
JAB_ROLE_SPIN_BOX = "spin box"
JAB_ROLE_FONT_CHOOSER = "font chooser"
JAB_ROLE_GROUP_BOX = "group box"
JAB_ROLE_HEADER = "header"
JAB_ROLE_FOOTER = "footer"
JAB_ROLE_PARAGRAPH = "paragraph"
JAB_ROLE_RULER = "ruler"
JAB_ROLE_EDIT_BAR = "edit bar"
JAB_ROLE_UNKNOWN = "unknown"
# jab states
JAB_STATES_BUSY = "busy"
JAB_STATES_CHECKED = "checked"
JAB_STATES_FOCUSED = "focused"
JAB_STATES_SELECTED = "selected"
JAB_STATES_PRESSED = "pressed"
JAB_STATES_EXPANDED = "expanded"
JAB_STATES_COLLAPSED = "collapsed"
JAB_STATES_ICONIFIED = "iconified"
JAB_STATES_MODAL = "modal"
JAB_STATES_MULTI_LINE = "multi_line"
JAB_STATES_FOCUSABLE = "focusable"
JAB_STATES_EDITABLE = "editable"
JAB_STATES_UNKNOWN = "unknown"


class JABElement(object):

    xml_tag_pattern = re.compile(r"\<[^>]+\>")

    def __init__(self, hwnd: HWND = None, jab_context: JABContext = None) -> None:
        self.log = Logger(self.__class__.__name__)
        self.handler = JABHandler(BRIDGE)
        if jab_context is None:
            self.handler.init_jab_context()
        self.ac = JABContext(jab_context.hwnd, jab_context.vmid, jab_context.ac)
        self._role = None
        super(JABElement, self).__init__(hwnd=hwnd)
        self._ac_info = self._get_accessible_context_info()

    @property
    def role(self) -> str:
        if not self._role:
            self._role = self._get_jab_role()
        return self._role

    @property
    def ac_info(self) -> AccessibleContextInfo:
        return self._ac_info

    @ac_info.setter
    def ac_info(self, ac_info: AccessibleContextInfo) -> None:
        self._ac_info = ac_info

    def _get_accessible_context_info(self) -> AccessibleContextInfo:
        return self.handler.get_accessible_context_info()

    def _get_text_info(self) -> AccessibleTextInfo:
        is_eligible = self.ac_info.accessibleText and self.role not in [
            JAB_ROLE_PUSH_BUTTON,
            JAB_ROLE_MENU_ITEM,
            JAB_ROLE_MENU,
            JAB_ROLE_LIST_ITEM,
        ]
        if is_eligible:
            return JABText
        # TODO: fix missing self.text_info
        return super(JABElement, self).text_info

    def _is_equal(self, other: JABContext) -> bool:
        try:
            return self.ac == other.ac
        except Exception as exc:
            self.log.error(
                "jab context not equal",
                exc_info=exc,
            )
            return False

    def _get_keyboard_shortcut(self) -> str:
        bindings = self.handler.get_accessible_key_bindings()
        bindings_count = bindings.keyBindingsCount
        if not bindings or bindings_count < 1:
            return ""
        shortcut_list = []
        key_list = []
        for index in range(bindings_count):
            binding_info = bindings.keyBindingInfo[index]
            if binding_info.modifiers and (
                ACCESSIBLE_META_KEYSTROKE
                or ACCESSIBLE_ALT_GRAPH_KEYSTROKE
                or ACCESSIBLE_BUTTON1_KEYSTROKE
                or ACCESSIBLE_BUTTON2_KEYSTROKE
                or ACCESSIBLE_BUTTON3_KEYSTROKE
            ):
                continue
            key_list.clear()
            if (binding_info.modifiers and ACCESSIBLE_ALT_KEYSTROKE) or (
                not binding_info.modifiers and self.role != JAB_ROLE_MENU_ITEM
            ):
                key_list.append("alt")
            if binding_info.modifiers and ACCESSIBLE_CONTROL_KEYSTROKE:
                key_list.append("control")
            if binding_info.modifiers and ACCESSIBLE_SHIFT_KEYSTROKE:
                key_list.append("shift")
            key_list.append(binding_info.character)
        shortcut_list.append("+".join(key_list))
        return ", ".join(shortcut_list)

    def _get_name(self) -> str:
        return self.xml_tag_pattern.sub(" ", self.ac_info.name)

    def _get_description(self) -> str:
        return self.xml_tag_pattern.sub(" ", self.ac_info.description)

    def _get_role(self) -> str:
        role = self.ac_info.role_en_US
        return role if role else JAB_ROLE_UNKNOWN

    def _get_status(self) -> str:
        states = self.ac_info.states_en_US
        return states if states else JAB_STATES_UNKNOWN

    def _get_bounds(self) -> dict:
        x = self.ac_info.X
        y = self.ac_info.Y
        width = self.ac_info.Width
        height = self.ac_info.Height
        return {"x": x, "y": y, "width": width, "height": height}

    def _get_children_count(self) -> int:
        return self.ac_info.childrenCount

    def _get_index_in_parent(self) -> int:
        return self.ac_info.indexInParent

    def _get_accessible_component_support(self) -> bool:
        return self.ac_info.accessibleComponent

    def _get_accessible_action_support(self) -> bool:
        return self.ac_info.accessibleAction

    def _get_accessible_selection_support(self) -> bool:
        return self.ac_info.accessibleSelection

    def _get_accessible_text_support(self) -> bool:
        return self.ac_info.accessibleText

    def _get_accessible_interfaces_support(self) -> bool:
        return self.ac_info.accessibleInterfaces
    
    def _get_value(self)->str:
        is_eligible = self.role not in [JAB_ROLE_CHECK_BOX, JAB_ROLE_MENU, JAB_ROLE_MENU_ITEM,JAB_ROLE_RADIO_BUTTON, JAB_ROLE_PUSH_BUTTON] and not self.ac_info.accessibleText
        if is_eligible:
            return self.handler.get_current_accessible_value_from_context()
        
    def _has_focus(self)->bool:
        return JAB_STATES_FOCUSED in self.states

    def _get_position_info(self):
        info = super(JABElement, self).position_info or {}
        # If tree view item, try to retrieve the level via JABElement
        if self.role == JAB_ROLE_TREE:
            tree = self.handler.get_parent_with_role(JAB_ROLE_TREE)
            if tree:
                tree_depth = tree.get_object_depth()
                self_depth = self.ac.get_object_depth()