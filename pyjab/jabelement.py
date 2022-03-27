from __future__ import annotations

from time import time

from pyjab.common.logger import Logger
from pyjab.common.role import Role
from pyjab.common.states import States
from pyjab.common.textreader import TextReader
import re
from ctypes import Array, byref, CDLL, c_char, c_long, create_string_buffer
from ctypes.wintypes import HWND
from typing import Any, Generator, Optional, Union
from PIL import Image, ImageGrab
from pyjab.common.by import By
from pyjab.common.exceptions import JABException
from pyjab.common.types import jint, JOBJECT64
from pyjab.common.win32utils import Win32Utils
from pyjab.common.xpathparser import XpathParser
from pyjab.accessibleinfo import (
    AccessibleActions,
    AccessibleActionsToDo,
    AccessibleContextInfo,
    AccessibleTableCellInfo,
    AccessibleTableInfo,
    AccessibleTextInfo,
    VisibleChildrenInfo,
)


class JABElement(object):
    int_func_err_msg = "Java Access Bridge func '{}' error"
    win32_utils = Win32Utils()
    xpath_parser = XpathParser()

    def __init__(
            self,
            bridge: CDLL = None,
            hwnd: HWND = None,
            vmid: c_long = None,
            accessible_context: JOBJECT64 = None,
    ) -> None:
        self.logger = Logger("pyjab")
        self._bridge = bridge
        # jab context attributes
        self._hwnd = hwnd
        self._vmid = vmid
        self._accessible_context = accessible_context
        self._acc_info = self._get_accessible_context_info

    @property
    def bridge(self) -> CDLL:
        return self._bridge

    @bridge.setter
    def bridge(self, bridge: CDLL) -> None:
        self._bridge = bridge

    @property
    def hwnd(self) -> HWND:
        return self._hwnd

    @hwnd.setter
    def hwnd(self, hwnd: HWND) -> None:
        self._hwnd = hwnd

    @property
    def vmid(self) -> c_long:
        return self._vmid

    @vmid.setter
    def vmid(self, vmid: c_long) -> None:
        self._vmid = vmid

    @property
    def accessible_context(self) -> JOBJECT64:
        return self._accessible_context

    @accessible_context.setter
    def accessible_context(self, accessible_context: JOBJECT64) -> None:
        self._accessible_context = accessible_context

    @property
    def name(self) -> str:
        return self._acc_info().name

    @property
    def description(self) -> str:
        return self._acc_info().description

    @property
    def role(self) -> str:
        return self._acc_info().role

    @property
    def role_en_us(self) -> str:
        return self._acc_info().role_en_US

    @property
    def states(self) -> str:
        return self._acc_info().states.split(",")

    @property
    def states_en_us(self) -> str:
        return self._acc_info().states_en_US.split(",")

    @property
    def object_depth(self) -> int:
        return self._get_object_depth()

    @property
    def index_in_parent(self) -> int:
        return self._acc_info().indexInParent

    @property
    def children_count(self) -> int:
        return self._acc_info().childrenCount

    @property
    def bounds(self) -> dict:
        return {
            "x": self._acc_info().x,
            "y": self._acc_info().y,
            "height": self._acc_info().height,
            "width": self._acc_info().width,
        }

    @property
    def accessible_component(self) -> bool:
        return bool(self._acc_info().accessibleComponent)

    @property
    def accessible_action(self) -> bool:
        return bool(self._acc_info().accessibleAction)

    @property
    def accessible_selection(self) -> bool:
        return bool(self._acc_info().accessibleSelection)

    @property
    def accessible_text(self) -> bool:
        return bool(self._acc_info().accessibleText)

    @property
    def accessible_interfaces(self) -> bool:
        # TODO: need handle acc interface
        return False

    @property
    def text(self) -> str:
        if self.accessible_text:
            txt_info = self._get_accessible_text_info()
            chars_start = 0
            chars_end = txt_info.charCount - 1
            chars_len = chars_end + 1 - chars_start
            buffer = create_string_buffer((chars_len + 1) * 2)
            self._get_accessible_text_range(chars_start, chars_end, buffer, chars_len)
            return TextReader().get_text_from_raw_bytes(
                buffer=buffer, chars_len=chars_len, encoding="utf_16"
            )
        else:
            self.logger.warning("current JABElement does not support Accessible Text")

    @property
    def table(self) -> dict:
        if self.role_en_us == Role.TABLE:
            info = self._get_accessible_table_info()
            tb = {
                "row_count": info.rowCount,
                "column_count": info.columnCount,
            }
            info = self._get_accessible_table_row_header()
            tb["row_headers"] = {
                "row_count": info.rowCount,
                "column_count": info.columnCount,
            }
            info = self._get_accessible_table_column_header()
            tb["column_headers"] = {
                "row_count": info.rowCount,
                "column_count": info.columnCount,
            }
            row_count = self._get_accessible_table_row_selection_count()
            column_count = self._get_accessible_table_column_selection_count()
            tb["selected"] = {
                "row_count": row_count,
                "column_count": column_count,
            }
            return tb
        else:
            self.logger.warning("current JABElement does not Accessible Table")

    # Jab Element actions
    def _generate_all_childs(
            self, jabelement: JABElement = None, visible: bool = False
    ) -> Generator[JABElement]:
        """generate all child jab elements from a jab element.

        Args:
            jabelement (JABElement, optional): The parent jab element to generate child jab elements.
            Defaults to None use current element.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Yields:
            Generator: Generator of all child jab elements from this parent jab element.
        """
        jabelement = jabelement or JABElement(
            self.bridge, self.hwnd, self.vmid, self.accessible_context
        )

        for _jabelement in self._generate_childs_from_element(
                jabelement=jabelement, visible=visible
        ):
            if _jabelement.children_count:
                yield from self._generate_all_childs(
                    jabelement=_jabelement, visible=visible
                )
            yield _jabelement

    def _generate_childs_from_element(
            self, jabelement: JABElement = None, visible: bool = False
    ) -> Generator[JABElement]:
        """generate child jab elements from a jab element.

        Args:
            jabelement (JABElement, optional): The parent jab element to generate child jab elements.
            Defaults to None use current element.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Yields:
            Generator: Generator of child jab elements from this parent jab element.
        """
        jabelement = jabelement or JABElement(
            self.bridge, self.hwnd, self.vmid, self.accessible_context
        )

        if visible:
            children_count = self._get_visible_children_count(
                jabelement.accessible_context
            )
            info = self._get_visible_children(jabelement.accessible_context)
            for index in range(children_count):
                yield JABElement(
                    jabelement.bridge,
                    jabelement.hwnd,
                    jabelement.vmid,
                    info.children[index],
                )
        else:
            for index in range(jabelement.children_count):
                child_acc = jabelement.bridge.getAccessibleChildFromContext(
                    jabelement.vmid, jabelement.accessible_context, index
                )
                yield JABElement(
                    jabelement.bridge, jabelement.hwnd, jabelement.vmid, child_acc
                )

    # JAB apis
    def release_jabelement(self, jabelement: JABElement = None) -> None:
        """Release the memory used by the Java object object,
        where object is an object returned to you by Java Access Bridge.
        Java Access Bridge automatically maintains a reference
        to all Java objects that it returns to you in the JVM
        so they are not garbage collected. To prevent memory leaks,
        you must call ReleaseJavaObject on all Java objects returned
        to you by Java Access Bridge once you are finished with them.
        See JavaFerret.c for an illustration of how to do this.

        Args:
            jabelement (JABElement): The JABElement need to release
        """
        accessible_context = (
            jabelement.accessible_context if jabelement else self.accessible_context
        )
        self.bridge.releaseJavaObject(self.vmid, accessible_context)

    def _request_focus(self, accessible_context: JOBJECT64 = None) -> None:
        """Request focus for a component. Returns whether successful."""
        accessible_context = accessible_context or self.accessible_context
        self.bridge.requestFocus(self.vmid, accessible_context)

    def _get_accessible_selection_from_context(
            self, accessible_context: JOBJECT64 = None
    ) -> JOBJECT64:
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleSelectionFromContext(
            self.vmid, accessible_context, 0
        )

    def _add_accessible_selection_from_context(
            self, index: int, accessible_context: JOBJECT64 = None
    ) -> None:
        accessible_context = accessible_context or self.accessible_context
        self.bridge.addAccessibleSelectionFromContext(
            self.vmid, accessible_context, index
        )

    def _clear_accessible_selection_from_context(
            self, accessible_context: JOBJECT64
    ) -> None:
        accessible_context = accessible_context or self.accessible_context
        self.bridge.clearAccessibleSelectionFromContext(self.vmid, accessible_context)

    def _is_same_object(self, obj1: JOBJECT64, obj2: JOBJECT64) -> bool:
        """Returns whether two object references are for the same object.

        Args:
            obj1 (JOBJECT64): Object 1.
            obj2 (JOBJECT64): Object 2.

        Returns:
            bool: Rerturns whether two object is same or not.
        """
        return bool(self.bridge.isSameObject(self.vmid, obj1, obj2))

    def _get_top_level_object(self, accessible_context: JOBJECT64 = None) -> JOBJECT64:
        """Returns the AccessibleContext for the top level object in a Java window.
        This is same AccessibleContext that is obtained from GetAccessibleContextFromHWND for that window.
        Returns (AccessibleContext)0 on error.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get top level object error.

        Returns:
            JOBJECT64: Top level object.
        """
        accessible_context = accessible_context or self.accessible_context
        top_object = self.bridge.getTopLevelObject(self.vmid, accessible_context)
        if top_object == 0:
            raise JABException(self.int_func_err_msg.format("getTopLevelObject"))
        return top_object

    def _get_accessible_parent_from_context(
            self, accessible_context: JOBJECT64 = None
    ) -> JOBJECT64:
        """Returns an AccessibleContext object that represents the parent of object ac.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Returns:
            JOBJECT64: Parent Accessible Context.
        """
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleParentFromContext(self.vmid, accessible_context)

    def _get_accessible_context_info(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleContextInfo:
        """Retrieves an AccessibleContextInfo object of the AccessibleContext object ac.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accessible Context Info error.

        Returns:
            AccessibleContextInfo: Accessible Context Info.
        """
        info = AccessibleContextInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleContextInfo(
            self.vmid, accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("GetAccessibleContextInfo"))
        return info

    def _get_object_depth(self, accessible_context: JOBJECT64 = None) -> int:
        """Returns how deep in the object hierarchy a given object is.
        The top most object in the object hierarchy has an object depth of 0.
        Returns -1 on error.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Object Depth error.

        Returns:
            int: Object depth.
        """
        accessible_context = accessible_context or self.accessible_context
        object_depth = self.bridge.getObjectDepth(self.vmid, accessible_context)
        if object_depth == -1:
            raise JABException(self.int_func_err_msg.format("getObjectDepth"))
        return object_depth

    def _get_accessible_text_info(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleTextInfo:
        info = AccessibleTextInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTextInfo(
            self.vmid, accessible_context, byref(info), 0, 0
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleTextInfo"))
        return info

    def _get_accessible_text_range(
            self,
            start: int,
            end: int,
            text: Array[c_char],
            length: int,
            accessible_context: JOBJECT64 = None,
    ) -> None:
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTextRange(
            self.vmid, accessible_context, start, end, text, length
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleTextRange"))

    def _get_accessible_table_info(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleTableInfo:
        """Returns information about the table, for example, caption, summary,
        row and column count, and the AccessibleTable.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accessible Table Info error.

        Returns:
            AccessibleTableInfo: Accessible Table Info.
        """
        info = AccessibleTableInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTableInfo(
            self.vmid, accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("getAccessibleTableInfo"))
        return info

    def _get_accessible_table_row_header(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleTableInfo:
        """Returns the table row headers of the specified table as a table.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accessible Table Info error.

        Returns:
            AccessibleTableInfo: Accessible Table Info.
        """
        info = AccessibleTableInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTableRowHeader(
            self.vmid, accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableRowHeader")
            )
        return info

    def _get_accessible_table_column_header(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleTableInfo:
        """Returns the table column headers of the specified table as a table.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accessible Table Info error.

        Returns:
            AccessibleTableInfo: Accessible Table Info.
        """
        info = AccessibleTableInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTableColumnHeader(
            self.vmid, accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableColumnHeader")
            )
        return info

    def _get_accessible_table_row_selection_count(
            self, accessible_context: JOBJECT64 = None
    ) -> int:
        """Returns how many rows in the table are selected.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Returns:
            int: Accessible table row selection count.
        """
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleTableRowSelectionCount(
            self.vmid, accessible_context
        )

    def _get_accessible_table_column_selection_count(
            self, accessible_context: JOBJECT64 = None
    ) -> int:
        """Returns how many columns in the table are selected.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Returns:
            int: Accessible table column selection count.
        """
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleTableColumnSelectionCount(
            self.vmid, accessible_context
        )

    def _get_accessible_table_cell_info(
            self, row: int, column: int, accessible_context: JOBJECT64 = None
    ) -> AccessibleTableCellInfo:
        """Returns information about the specified table cell. The row and column specifiers are zero-based.

        Args:
            row (int): Row index in table.
            column (int): Column index in table.
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accesible Table Cell Info error.

        Returns:
            AccessibleTableCellInfo: Accessible Table Cell Info.
        """
        info = AccessibleTableCellInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTableCellInfo(
            self.vmid, accessible_context, row, column, byref(info)
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableCellInfo")
            )
        return info

    def _get_visible_children_count(self, accessible_context: JOBJECT64 = None) -> int:
        """Returns the number of visible children of a component. Returns -1 on error.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Returns:
            int: [description]
        """
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getVisibleChildrenCount(self.vmid, accessible_context)
        if result == -1:
            raise JABException(self.int_func_err_msg.format("getVisibleChildrenCount"))
        return result

    def _get_visible_children(
            self, accessible_context: JOBJECT64 = None
    ) -> VisibleChildrenInfo:
        info = VisibleChildrenInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getVisibleChildren(
            self.vmid, accessible_context, 0, byref(info)
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getVisibleChildren"))
        return info

    def _do_accessible_action(self, action: str = None) -> None:
        """Do Accessible Action with current JABElement.

        Args:
            action (str): Accessible Action name.

        Raises:
            JABException: Raise JABException if current JABElement does not support this action.
        """
        acc_acts = AccessibleActions()
        self.bridge.getAccessibleActions(
            self.vmid, self.accessible_context, byref(acc_acts)
        )
        acc_acts_count = acc_acts.actionsCount
        acc_acts_info = acc_acts.actionInfo
        act_todo = AccessibleActionsToDo()
        if acc_acts_count < 1:
            raise JABException("JABElement does not support Accessible Action")
        if acc_acts_count > 1:
            if action is None:
                raise JABException(
                    "JABElement support multiple Accessible Action, please specifc"
                )
            act_todo.actions[0].name = action
            for index in range(acc_acts_count):
                if acc_acts_info[index].name.lower() == action:
                    break
            else:
                raise JABException(f"JABElement does not support action '{action}'")
        if acc_acts_count == 1:
            act_todo.actions[0].name = acc_acts_info[0].name
        act_todo.actionsCount = 1
        self.bridge.doAccessibleActions(
            self.vmid, self.accessible_context, byref(act_todo), jint()
        )

    def click(self, simulate: bool = False) -> None:
        """Simulates clicking to JABElement.

        Default will use JAB Accessible Action.
        Set parameter 'simulate' to True if internal action does not work.

        Args:
            simulate (bool, optional): Simulate user click action by mouse event. Defaults to False.

        Raises:
            ValueError: Raise ValueError when JABElement width or height is 0.

        Use this to send simple mouse events or to click form fields::

            form_button = driver.find_element_by_name('button')
            form_button.click()
            form_button.click(simulate=True)
        """
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            x = self.bounds.get("x")
            y = self.bounds.get("y")
            width = self.bounds.get("width")
            height = self.bounds.get("height")
            if width == 0 or height == 0:
                raise ValueError("element width or height is 0")
            position_x = round(x + width / 2)
            position_y = round(y + height / 2)
            self.win32_utils._click_mouse(x=position_x, y=position_y)
        else:
            self._do_accessible_action(action="click")

    def clear(self, simulate: bool = False, wait_for_text_update: bool = True) -> None:
        """Clear existing text from JABElement.

        Default will use JAB Accessible Action.
        Set parameter 'simulate' to True if internal action does not work.

        Args:
            simulate (bool, optional): Simulate user input action by keyboard event. Defaults to False.
            wait_for_text_update (bool, optional): Waits for the text attribute to be empty. Defaults to True.

        Use this to send simple key events or to fill out form fields::

            form_textfield = driver.find_element_by_name('username')
            form_textfield.clear()
            from_textfield.send_text(simulate=True)
        """
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            self._request_focus()
            if self.accessible_text and self.text:
                self.win32_utils._press_key("end")
                for _ in self.text:
                    self.win32_utils._press_key("backspace")
        else:
            self.send_text(value="", simulate=False)
        if not wait_for_text_update or self.role != Role.TEXT:
            return
        self._wait_for_value_to_be(None, self.text, error_msg_function="clear text")

    def scroll(self, to_bottom: bool = True, hold: int = 2) -> None:
        """Scroll a scoll bar to top or to bottom.

        Need improvement for scroll to specific position.

        Args:
            to_bottom (bool, optional): Scroll to bottom or not, otherwise scroll to top. Defaults to True.
            hold (int, optional): Mouse hold time to scroll to bar. Default to 2.

        Raises:
            JABException: Raise a JABException when JABElement role is not a scroll bar.
        """
        if self.role_en_us != Role.SCROLL_BAR:
            raise JABException("JABElement is not 'scroll bar'")
        is_horizontal = "horizontal" in self.states_en_us
        x = self.bounds["x"]
        y = self.bounds["y"]
        height = self.bounds["height"]
        width = self.bounds["width"]
        self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        # horizontal scroll to bottom(right)
        if to_bottom and is_horizontal:
            x = x + width - height - 5
            y = y + height / 2
        elif to_bottom:
            x = x + width / 2
            y = y + height - width - 5
        elif is_horizontal:
            x = x + height + 5
            y = y + height / 2
        else:
            x = x + width / 2
            y = y + width + 5
        self.win32_utils._click_mouse(x=int(x), y=int(y), hold=hold)

    def slide(self, to_bottom: bool = True, hold: int = 5) -> None:
        """Slide a slider to top or to bottom.

        Need improvement for slide to specific position.

        Args:
            to_bottom (bool, optional): Slide to bottom or not, otherwise slide to top. Defaults to True.
            hold (int, optional): Mouse hold time to slide. Default to 2.

        Raises:
            JABException: Raise a JABException when JABElement role is not a slider.
        """
        if self.role_en_us != "slider":
            raise JABException("JABElement is not 'slider'")
        is_horizontal = "horizontal" in self.states_en_us
        x = self.bounds["x"]
        y = self.bounds["y"]
        height = self.bounds["height"]
        width = self.bounds["width"]
        self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        # horizontal slide to bottom(right)
        if to_bottom and is_horizontal:
            x = x + width - 5
            y = y + height / 2
        elif to_bottom:
            x = x + width / 2
            y = y + height - 5
        elif is_horizontal:
            y = y + height / 2
        else:
            x = x + width / 2
        self.win32_utils._click_mouse(x=int(x), y=int(y), hold=hold)

    def select(self, option: str, simulate: bool = False, wait_for_selection: bool = True) -> None:
        """Select an item from JABElement selector.
        Support select action from combo box, page tab list, list and menu.

        Args:
            option (str): Item selection from selector.
            simulate (bool, optional): Simulate user input action by mouse event. Defaults to False.
            wait_for_selection (bool, optional): Waits for selection equal to the option value. Defaults to True.
        """
        _ = {
            "combo box": self._select_from_combobox,
            "page tab list": self._select_from_page_tab_list,
            "list": self._select_from_list,
            "menu": self._select_from_menu,
        }[self.role_en_us](option=option, simulate=simulate)
        if wait_for_selection:
            self._wait_for_value_to_contain([States.SELECTED, States.CHECKED],
                                            self.find_element_by_name(option).states_en_us)

    def get_selected_element(self) -> JABElement:
        """Get selected JABElement from selection.
        Support get selection from combo box, list and page tab list.

        Returns:
            JABElement: The selected JABElement
        """
        selected_acc = self._get_accessible_selection_from_context(
            self.accessible_context
        )
        return JABElement(
            bridge=self.bridge,
            hwnd=self.hwnd,
            vmid=self.vmid,
            accessible_context=selected_acc,
        )

    def _add_selection_from_accessible_context(
            self, parent: JABElement, option: str
    ) -> None:
        try:
            item = parent.find_element_by_name(value=option)
        except JABException as e:
            raise JABException(
                f"{parent.role_en_us} option '{option}' not found"
            ) from e

        self._add_accessible_selection_from_context(
            item.index_in_parent, parent.accessible_context
        )

    def _select_from_checkbox(self, simulate: bool = False) -> None:
        if self.role_en_us != "check box":
            raise JABException("JABElement is not 'check box'")
        self._request_focus()
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        self.click(simulate=simulate)

    def _select_from_combobox(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "combo box":
            raise JABException("JABElement is not 'combo box'")
        self._request_focus()
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            self._do_accessible_action(action="togglepopup")
            self._add_selection_from_accessible_context(
                parent=self.find_element_by_role("list"), option=option
            )
            self.win32_utils._press_key("enter")
            return
        self._clear_accessible_selection_from_context(self.accessible_context)
        self._add_selection_from_accessible_context(parent=self, option=option)

    def _select_from_page_tab_list(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "page tab list":
            raise JABException("JABElement is not 'page tab list'")
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            self.find_element_by_name(option).click(simulate=True)
            return
        self._add_selection_from_accessible_context(self, option=option)

    def _select_from_list(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != Role.LIST:
            raise JABException("JABElement is not 'list'")
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        self.find_element_by_name(value=option).click(simulate=simulate)

    def _select_from_menu(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "menu":
            raise JABException("JABElement is not 'menu'")
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            self.click(simulate=True)
            for item in self.find_elements_by_object_depth(self.object_depth + 1):
                if not item.accessible_action:
                    continue
                self.win32_utils._press_key("down_arrow")
                if item.name == option:
                    self.win32_utils._press_key("enter")
                    break
        else:
            self.find_element_by_name(value=option).click(simulate=False)

    def spin(
            self, option: str = None, increase: bool = True, simulate: bool = False
    ) -> None:
        if self.role_en_us != "spinbox":
            raise JABException("JABElement is not 'spinbox'")
        # select spinbox by set text
        if option:
            try:
                text = self.find_element_by_role("text")
            except JABException as e:
                raise JABException(
                    "Current spinbox does not support set 'option', try with 'increase'"
                ) from e
            text.send_text(value=option, simulate=simulate)
            return
        # select spinbox by accessible action or simulate click
        if increase:
            action = "increment"
            offset_y_position = -5
        else:
            action = "decrement"
            offset_y_position = 5
        if simulate:
            x = self.bounds["x"]
            y = self.bounds["y"]
            height = self.bounds["height"]
            width = self.bounds["width"]
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            x = x + width - 5
            y = y + height / 2 + offset_y_position
            self.win32_utils._click_mouse(x=int(x), y=int(y))
            return
        self._do_accessible_action(action=action)

    def expand(self, simulate: bool = False) -> None:
        if "expandable" not in self.states_en_us:
            raise JABException("JABElement does not support 'expand'")
        if simulate:
            self.click(simulate=True)
            self.click(simulate=True)
            return
        self._do_accessible_action("toggleexpand")

    def send_text(self, value: Union[str, int], simulate: bool = False, wait_for_text_update: bool = True) -> None:
        """Type into the JABElement.

        Default will use JAB Accessible Action.
        Set parameter 'simulate' to True if internal action does not work.

        :Args:
            value (str, int): A string for typing.
            simulate (bool, optional): Simulate user input action by keyboard event. Defaults to False.
            wait_for_text_update (bool, optional): Waits for the text attribute to be equal to the input value. Defaults to True.

        Use this to send simple key events or to fill out form fields::

            form_textfield = driver.find_element_by_name('username')
            form_textfield.send_text("admin")
            from_textfield.send_text("admin", simulate=True)
        """
        value = str(value)
        if simulate:
            self.clear(simulate=True)
            self.win32_utils._send_keys(value)
        else:
            result = self.bridge.setTextContents(
                self.vmid, self.accessible_context, value
            )
            if result == 0:
                raise JABException(
                    self.int_func_err_msg.format("setTextContents")
                    + ", try set parameter 'simulate' with True"
                )
        if not wait_for_text_update or self.role != Role.TEXT:
            return
        self._wait_for_value_to_be(value, self.text, error_msg_function=f"update text attribute to '{value}'")

    def is_checked(self) -> bool:
        """Returns whether the JABElement is checked.

        Can be used to check if a checkbox or radio button is checked.
        """
        return States.CHECKED in self.states_en_us

    def is_enabled(self) -> bool:
        """Returns whether the JABElement is enabled."""
        return States.ENABLED in self.states_en_us

    def is_visible(self) -> bool:
        """Returns whether the JABElement is visible."""
        return States.VISIBLE in self.states_en_us

    def is_showing(self) -> bool:
        """Returns whether the JABElement is showing."""
        return States.SHOWING in self.states_en_us

    def is_selected(self) -> bool:
        """Returns whether the JABElement is selected."""
        return States.SELECTED in self.states_en_us

    def is_editable(self) -> bool:
        """Returns whether the JABElement is editable."""
        return States.EDITABLE in self.states_en_us

    def find_element_by_name(self, value: str, visible: bool = False) -> JABElement:
        """find child JABElement by name

        Args:
            value (str): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.NAME, value=value, visible=visible)

    def find_element_by_description(
            self, value: str, visible: bool = False
    ) -> JABElement:
        """find child JABElement by description

        Args:
            value (str): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.DESCRIPTION, value=value, visible=visible)

    def find_element_by_role(self, value: str, visible: bool = False) -> JABElement:
        """find child JABElement by role

        Args:
            value (str): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.ROLE, value=value, visible=visible)

    def find_element_by_states(self, value: Union[list, str], visible: bool = False) -> JABElement:
        """find child JABElement by states

        Args:
            value (list): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.STATES, value=value, visible=visible)

    def find_element_by_object_depth(
            self, value: int, visible: bool = False
    ) -> JABElement:
        """find child JABElement by object depth

        Args:
            value (int): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.OBJECT_DEPTH, value=value, visible=visible)

    def find_element_by_children_count(
            self, value: int, visible: bool = False
    ) -> JABElement:
        """find child JABElement by children count

        Args:
            value (int): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.CHILDREN_COUNT, value=value, visible=visible)

    def find_element_by_index_in_parent(
            self, value: int, visible: bool = False
    ) -> JABElement:
        """find child JABElement by index in parent

        Args:
            value (int): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.INDEX_IN_PARENT, value=value, visible=visible)

    @staticmethod
    def _is_match_attr_name(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by name.

        Args:
            attr_val (str): Attribute name value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        if attr_val[0] in ["'", '"'] and attr_val[-1] in ["'", '"']:
            attr_val = attr_val[1:-1]
        pattern = re.compile("^contains\([\"'](.*?)[\"']\)")
        if content := pattern.findall(attr_val):
            return content[0] in jabelement.name
        else:
            return attr_val == jabelement.name

    @staticmethod
    def _is_match_attr_description(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by description.

        Args:
            attr_val (str): Attribute description value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        if attr_val[0] in ["'", '"'] and attr_val[-1] in ["'", '"']:
            attr_val = attr_val[1:-1]
        pattern = re.compile("^contains\([\"'](.*?)[\"']\)")
        if content := pattern.findall(attr_val):
            return content[0] in jabelement.description
        else:
            return attr_val == jabelement.description

    @staticmethod
    def _is_match_attr_role(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by role.

        Args:
            attr_val (str): Attribute description value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        if attr_val[0] in ["'", '"'] and attr_val[-1] in ["'", '"']:
            attr_val = attr_val[1:-1]
        pattern = re.compile("^contains\([\"'](.*?)[\"']\)")
        if content := pattern.findall(attr_val):
            return content[0] in jabelement.role
        else:
            return attr_val == jabelement.role

    @staticmethod
    def _is_match_attr_states(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by states.

        Args:
            attr_val (str): Attribute states value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        if attr_val[0] in ["'", '"'] and attr_val[-1] in ["'", '"']:
            attr_val = attr_val[1:-1]
        pattern = re.compile("^contains\([\"'](.*?)[\"']\)")
        if content := pattern.findall(attr_val):
            return all(stat in jabelement.states_en_us for stat in content[0].split(","))
        else:
            return set(attr_val.split(",")) == set(jabelement.states_en_us)

    @staticmethod
    def _is_match_attr_objectdepth(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by object depth.

        Args:
            attr_val (str): Attribute object depth value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        return int(attr_val) == jabelement.object_depth

    @staticmethod
    def _is_match_attr_childrencount(
            attr_val: str, jabelement: JABElement
    ) -> bool:
        """Return the attribute value is matched or not by children count.

        Args:
            attr_val (str): Attribute children count value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        return int(attr_val) == jabelement.children_count

    @staticmethod
    def _is_match_attr_indexinparent(
            attr_val: str, jabelement: JABElement
    ) -> bool:
        """Return the attribute value is matched or not by index in parent.

        Args:
            attr_val (str): Attribute index in parent value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        return int(attr_val) == jabelement.index_in_parent

    def _is_match_attributes(
            self, attributes: list[dict], jabelement: JABElement
    ) -> bool:
        """Return the node attributes is matched or not with specific JABElement.


        Args:
            attributes (list[dict]): List of attribute contains
            "name" of attribute and "value" of attribute conditions
            jabelement (JABElement): The JABElement

        Raises:
            JABException: Incorrect attribute name found

        Returns:
            bool: True for attributes matched False for not
        """
        dict_attribute = {
            "name": self._is_match_attr_name,
            "role": self._is_match_attr_role,
            "description": self._is_match_attr_description,
            "states": self._is_match_attr_states,
            "objectdepth": self._is_match_attr_objectdepth,
            "childrencount": self._is_match_attr_childrencount,
            "indexinparent": self._is_match_attr_indexinparent,
        }
        for attribute in attributes:
            name = attribute.get("name")
            value = attribute.get("value")
            if name not in dict_attribute.keys():
                raise JABException(f"incorrect attribute name '{name}'")
            if not dict_attribute[name](value, jabelement):
                return False
        return True

    def _get_node_element(self, jabelement: JABElement = None) -> JABElement:
        """Get node JABElement.

        Args:
            jabelement (JABElement, optional): The JABElement. Defaults to None.

        Returns:
            JABElement: Node JABElement
        """
        jabelement = jabelement or JABElement(self.bridge, self.hwnd, self.vmid, self.accessible_context)
        is_same = self._is_same_object(
            self.accessible_context, jabelement.accessible_context
        )
        if not is_same:
            return jabelement
        top_object = self._get_top_level_object(self.accessible_context)
        is_top_level = self._is_same_object(self.accessible_context, top_object)
        return jabelement if is_top_level else self.parent

    def _get_element_by_node(
            self,
            node: str,
            level: str = "root",
            jabelement: JABElement = None,
            visible: bool = False,
    ) -> JABElement:
        """Get child JABElement by specific node.

        Args:
            node (str): Node content for every single content in xpath.

            level (str, optional): Level for node, two options: "root" and "child". Defaults to "root".

            jabelement (JABElement, optional): The parent JABElement. Defaults to None.

            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Raises:
            ValueError: Incorrect level set
            JABException: No JABElement found with specific node

        Returns:
            JABElement: The child JABElement
        """
        node_element, node_info = self._get_node_info(node, jabelement)
        for _jabelement in self._get_children_by_level(level)(jabelement=node_element, visible=visible):
            if node_info.get("role") not in ["*", _jabelement.role_en_us]:
                self.release_jabelement(_jabelement)
                continue
            if self._is_match_attributes(node_info.get("attributes"), _jabelement):
                return _jabelement
            self.release_jabelement(_jabelement)
        raise JABException(
            f"no JABElement found in level {level} with node '{node}'"
        )

    def find_element_by_xpath(self, value: str, visible: bool = False) -> JABElement:
        """Find child JABElement by xpath

        Args:
            value (str): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Example:
            find_element_by_xpath("//internal frame/panel")\n
            find_element_by_xpath("//*/panel")\n
            find_element_by_xpath("//internal frame[@name='FRM-999']")\n
            find_element_by_xpath("//internal frame[@name=contains('FRM-999')]")\n
            find_element_by_xpath("//internal frame[@states='enable,focusable,visible,showing']")\n
            find_element_by_xpath("//internal frame[@states=contains('enable,focusable')]")\n
            find_element_by_xpath("//internal frame[@objectdepth=7]")\n
            find_element_by_xpath("//internal frame[@childrencount=2]")\n
            find_element_by_xpath("//internal frame[@indexinparent=3]")\n
            find_element_by_xpath("//internal frame[@name=contains('FRM-999') and @objectdepth=7]")\n

        Returns:
            JABElement: The JABElement find by locator
        """
        nodes = self.xpath_parser.split_nodes(value)
        jabelement = None
        for node in nodes:
            level = "root" if nodes.index(node) == 0 else "child"
            jabelement = self._get_element_by_node(
                node=node, level=level, jabelement=jabelement, visible=visible
            )
        return jabelement

    def find_element(
            self, by: str = By.NAME, value: Any = None, visible: bool = False
    ) -> JABElement:
        """Find a jab element given a By strategy and locator.

        Args:
            by (str, optional): By strategy of element need to find. Defaults to By.NAME.
            value (Any, optional): Locator of element need to find.
            Defaults to None will select the first child jab element.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The element find by locator
        """
        if by not in [
            By.NAME,
            By.DESCRIPTION,
            By.ROLE,
            By.STATES,
            By.OBJECT_DEPTH,
            By.CHILDREN_COUNT,
            By.INDEX_IN_PARENT,
            By.XPATH,
        ]:
            raise JABException(f"incorrect by strategy '{by}'")
        if by == By.XPATH:
            self.find_element_by_xpath(value=value, visible=visible)
        for jabelement in self._generate_all_childs(visible=visible):
            if self._is_element_matched(by=by, value=value, jabelement=jabelement):
                return jabelement
            self.release_jabelement(jabelement)
        raise JABException(
            f"jab element not found by '{by}' with locator '{value}'"
        )

    def find_elements_by_name(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by name

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.NAME, value=value, visible=visible)

    def find_elements_by_description(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by description

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.DESCRIPTION, value=value, visible=visible)

    def find_elements_by_role(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by role

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.ROLE, value=value, visible=visible)

    def find_elements_by_states(
            self, value: Union[list, str], visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by states

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.STATES, value=value, visible=visible)

    def find_elements_by_object_depth(
            self, value: int, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by object depth

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.OBJECT_DEPTH, value=value, visible=visible)

    def find_elements_by_children_count(
            self, value: int, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by children count

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.CHILDREN_COUNT, value=value, visible=visible)

    def find_elements_by_index_in_parent(
            self, value: int, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by index inparent

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.INDEX_IN_PARENT, value=value, visible=visible)

    def _get_elements_by_node(
            self,
            node: str,
            level: str = "root",
            jabelement: JABElement = None,
            visible: bool = False,
    ) -> list[JABElement]:
        """Get list of child JABElement by specific node

        Args:
            node (str): Node content for every single content in xpath.

            level (str, optional): Level for node, two options: "root" and "child". Defaults to "root".

            jabelement (JABElement, optional): The parent JABElement. Defaults to None.

            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Raises:
            ValueError: Incorrect level set

        Returns:
            list[JABElement]: list of the JABElement
        """
        node_element, node_info = self._get_node_info(node, jabelement)
        jabelements = []
        for _jabelement in self._get_children_by_level(level)(jabelement=node_element, visible=visible):
            if node_info.get("role") not in ["*", _jabelement.role_en_us]:
                self.release_jabelement(_jabelement)
                continue
            if self._is_match_attributes(node_info.get("attributes"), _jabelement):
                jabelements.append(_jabelement)
                continue
            self.release_jabelement(_jabelement)
        return jabelements

    def _get_children_by_level(self, level: str = "root"):
        if level in {"root", "child"}:
            return self._generate_all_childs if level == "root" else self._generate_childs_from_element
        else:
            raise ValueError("level should be in 'root' or 'child'")

    def _get_node_info(self,
                      node: str,
                      jabelement: JABElement = None,
                      ):
        node_info = self.xpath_parser.get_node_information(node)
        node_element = self._get_node_element(jabelement)
        return node_element, node_info

    def find_elements_by_xpath(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by xpath

        Args:
            value (str): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """

        def generate_node(_nodes: list[str]) -> Generator:
            for index, _node in enumerate(_nodes):
                _level = "root" if index == 0 else "child"
                yield _node, _level

        def get_child_jabelements(
                _node: str,
                _level: str,
                _parent_jabelements: list[JABElement],
                _visible: bool = False,
        ) -> list[JABElement]:
            child_jabelements = []
            for _parent_jabelement in _parent_jabelements:
                child_jabelements.extend(
                    self._get_elements_by_node(
                        node=_node,
                        level=_level,
                        jabelement=_parent_jabelement,
                        visible=_visible,
                    )
                )
            return child_jabelements

        nodes = self.xpath_parser.split_nodes(value)
        _jabelements = [
            JABElement(self.bridge, self.hwnd, self.vmid, self.accessible_context)
        ]
        for node, level in generate_node(nodes):
            if not _jabelements:
                raise JABException("no JABElement found")
            _jabelements = get_child_jabelements(
                _node=node, _level=level, _parent_jabelements=_jabelements, _visible=visible
            )
        return _jabelements

    def find_elements(
            self, by: str = By.NAME, value: Union[list, str, int] = None, visible: bool = False
    ) -> list[JABElement]:
        """Find list of JABElement given a By strategy and locator.

        Args:
            by (str, optional): By strategy of element need to find. Defaults to By.NAME.
            value (Any, optional): Locator of element need to find.
            Defaults to None will select the first child jab element.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list: List of JABElement find by locator
        """
        if by not in [
            By.NAME,
            By.DESCRIPTION,
            By.ROLE,
            By.STATES,
            By.OBJECT_DEPTH,
            By.CHILDREN_COUNT,
            By.INDEX_IN_PARENT,
            By.XPATH,
        ]:
            raise JABException(f"incorrect by strategy '{by}'")
        if by == By.XPATH:
            self.find_elements_by_xpath(value=value, visible=visible)
        jabelements = []
        for jabelement in self._generate_all_childs(visible=visible):
            if self._is_element_matched(by=by, value=value, jabelement=jabelement):
                jabelements.append(jabelement)
                continue
            self.release_jabelement(jabelement)
        if not jabelements:
            raise JABException(
                f"no JABElement found by '{by}' with locator '{value}'"
            )
        return jabelements

    @staticmethod
    def _is_element_matched(jabelement: JABElement, by: str, value: Optional[str]):
        return any(
            [
                value is None,
                by == By.NAME and jabelement.name == value,
                by == By.ROLE and jabelement.role == value,
                by == By.DESCRIPTION and jabelement.description == value,
                by == By.STATES and set(jabelement.states_en_us) == set(value),
                by == By.OBJECT_DEPTH
                and jabelement.object_depth == int(value),
                by == By.CHILDREN_COUNT
                and jabelement.children_count == int(value),
                by == By.INDEX_IN_PARENT
                and jabelement.index_in_parent == int(value),
            ]
        )

    @property
    def size(self) -> dict:
        """The size of the element."""
        return dict(height=self.bounds.get("height"), width=self.bounds.get("width"))

    @property
    def location(self) -> dict:
        """The location of the element in the renderable canvas."""
        return dict(x=self.bounds.get("x"), y=self.bounds.get("y"))

    def get_screenshot_as_file(self, filename: str) -> None:
        """
        Saves a screenshot of the current element to a PNG image file. Returns
           False if there is any IOError, else returns True. Use full paths in
           your filename.

        :Args:
         - filename: The full path you wish to save your screenshot to. This
           should end with a `.png` extension.

        :Usage:
            element.screenshot('/Screenshots/foo.png')
        """
        im = self.get_screenshot()
        im.save(filename)

    def get_screenshot(self) -> Image:
        """
        Gets the screenshot of the current element as pillow Image.

        :Usage:
            img = element.get_screenshot()
        """
        self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        x = self.bounds.get("x")
        y = self.bounds.get("y")
        width = self.bounds.get("width")
        height = self.bounds.get("height")
        return ImageGrab.grab(
            bbox=(
                x,
                y,
                x + width,
                y + height,
            ),
            include_layered_windows=False,
            all_screens=True,
        )

    @property
    def parent(self):
        """Internal reference to the JabDriver instance this element was found from."""
        parent_acc = self._get_accessible_parent_from_context()
        return JABElement(
            bridge=self.bridge,
            hwnd=self.hwnd,
            vmid=self.vmid,
            accessible_context=parent_acc,
        )

    def get_cell(self, row: int, column: int, visible: bool = False) -> JABElement:
        """Get cell JABElement from table

        Args:
            row (int): Row index of cell, start from 0.
            column (int): Column index of cell, start from 0.
            visible (bool, optional): The switch for find only visible cell element or not.
            Defaults to False to find available cell element.

        Raises:
            JABException: Raise JABException if JAB internal function error

        Returns:
            JABElement: Return specific cell JABElement
        """
        if self.role_en_us != "table":
            raise JABException("JABElement is not table, does not support this func")
        info = self._get_accessible_table_cell_info(row, column)
        index = info.index
        accessible_context = info.accessibleContext
        if visible:
            info = self._get_visible_children()
            accessible_context = info.children[index]
        return JABElement(self.bridge, self.hwnd, self.vmid, accessible_context)

    def get_element_information(self) -> dict:
        """Get dict information of current JABElement.

        Notice:
            This dict of component value will NOT update after property changes.

        Returns:
            dict: Dict information of current JABElement
        """
        info = {
            "name": self.name,
            "description": self.description,
            "role": self.role,
            "role_en_us": self.role_en_us,
            "states": self.states,
            "states_en_us": self.states_en_us,
            "bounds": self.bounds,
            "object_depth": self.object_depth,
            "index_in_parent": self.index_in_parent,
            "children_count": self.children_count,
            "accessible_component": self.accessible_component,
            "accessible_action": self.accessible_action,
            "accessible_selection": self.accessible_selection,
            "accessible_text": self.accessible_text,
        }
        if self.accessible_text:
            info["text"] = self.text
        if self.role_en_us == Role.TABLE:
            info["table"] = self.table
        return info

    @staticmethod
    def _wait_for_value_to_be(expected_value: Optional[str], actual_value, timeout: int = 5,
                              error_msg_function: str = None):
        start = time()
        while True:
            if (
                    expected_value
                    and actual_value == expected_value
                    or not expected_value
                    and not actual_value
            ):
                return
            current = time()
            elapsed = round(current - start)
            if elapsed >= timeout:
                if error_msg_function:
                    _error_msg = f"Failed to {error_msg_function} in '{timeout}' seconds"
                else:
                    _error_msg = f"Failed to wait for expected value '{expected_value}' in '{timeout}' seconds"
                raise TimeoutError(_error_msg)

    @staticmethod
    def _wait_for_value_to_contain(expected_values: Union[str, list[str]], actual_values, timeout: int = 5,
                                   error_msg_function: str = None):
        start = time()
        while True:
            if any(v in expected_values for v in actual_values):
                return
            current = time()
            elapsed = round(current - start)
            if elapsed >= timeout:
                if error_msg_function:
                    _error_msg = f"Failed to {error_msg_function} in '{timeout}' seconds"
                else:
                    _expected_values = ", ".join(expected_values)
                    _error_msg = f"Failed to wait for expected values '{_expected_values}' in '{timeout}' seconds"
                raise TimeoutError(_error_msg)
