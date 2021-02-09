from ctypes.wintypes import HWND
from pyjab.globalargs import BRIDGE
from pyjab.jabhandler import JABHandler
from pyjab.common.logger import Logger
from pyjab.accessibleinfo import AccessibleContextInfo, AccessibleTextInfo
from pyjab.jabcontext import JABContext


class JABElement(object):

    # jab element roles
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
    # jab element states
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

    def __init__(self, hwnd: HWND = None, jab_context: JABContext = None) -> None:
        self.log = Logger(self.__class__.__name__)
        self.handler = JABHandler(BRIDGE)
        if jab_context is None:
            self.handler.init_jab_context()
        self.ac = JABContext(jab_context.hwnd, jab_context.vmid, jab_context.ac)
        self._role = None
        super(JABElement, self).__init__(hwnd=hwnd)
        self.ac_info = self._get_accessible_context_info()
    
    @property
    def role(self)->str:
        return self._role
    
    @role.setter
    def role(self, role:str)->str:
        self._role = role

    def _get_accessible_context_info(self) -> AccessibleContextInfo:
        return self.handler.get_accessible_context_info()
    
    def _get_text_info(self)-> AccessibleTextInfo:
        is_eligible =  self.ac_info.accessibleText and self.role
