from __future__ import annotations
from pyjab.common.textreader import TextReader
import re
from ctypes import byref, CDLL, c_long, create_string_buffer
from ctypes.wintypes import HWND
from typing import Any, Generator
from PIL import Image, ImageGrab
from pyjab.common.by import By
from pyjab.common.exceptions import JABException
from pyjab.common.shortcutkeys import ShortcutKeys
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
)


class JABElement(object):
    int_func_err_msg = "Java Access Bridge func '{}' error"
    win32_utils = Win32Utils()
    shortcut_keys = ShortcutKeys()
    xpath_parser = XpathParser()

    def __init__(
        self,
        bridge: CDLL = None,
        hwnd: HWND = None,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> None:
        self._bridge = bridge
        # jab context attributes
        self._hwnd = hwnd
        self._vmid = vmid
        self._accessible_context = accessible_context
        # infor attributes
        self._name = None
        self._description = None
        self._role = None
        self._role_en_us = None
        self._states = None
        self._states_en_us = None
        self._object_depth = 0
        self._index_in_parent = 0
        self._children_count = 0
        self._bounds = dict(x=0, y=0, width=0, height=0)
        self._accessible_component = False
        self._accessible_action = False
        self._accessible_selection = False
        self._accessible_text = False
        self._accessible_interfaces = False
        self._text = None
        self._table = None
        self.set_element_information()

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
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, description: str) -> None:
        self._description = description

    @property
    def role(self) -> str:
        return self._role

    @role.setter
    def role(self, role: str) -> None:
        self._role = role

    @property
    def role_en_us(self) -> str:
        return self._role_en_us

    @role_en_us.setter
    def role_en_us(self, role_en_us: str) -> None:
        self._role_en_us = role_en_us

    @property
    def states(self) -> str:
        return self._states

    @states.setter
    def states(self, states: str) -> None:
        self._states = states

    @property
    def states_en_us(self) -> str:
        return self._states_en_us

    @states_en_us.setter
    def states_en_us(self, states_en_us: str) -> None:
        self._states_en_us = states_en_us

    @property
    def object_depth(self) -> int:
        return self._object_depth

    @object_depth.setter
    def object_depth(self, object_depth: int) -> None:
        self._object_depth = object_depth

    @property
    def index_in_parent(self) -> int:
        return self._index_in_parent

    @index_in_parent.setter
    def index_in_parent(self, index_in_parent: int) -> None:
        self._index_in_parent = index_in_parent

    @property
    def children_count(self) -> int:
        return self._children_count

    @children_count.setter
    def children_count(self, children_count: int) -> None:
        self._children_count = children_count

    @property
    def bounds(self) -> dict:
        return self._bounds

    @bounds.setter
    def bounds(self, bounds: dict) -> None:
        self._bounds = bounds

    @property
    def accessible_component(self) -> bool:
        return self._accessible_component

    @accessible_component.setter
    def accessible_component(self, accessible_component: bool) -> None:
        self._accessible_component = accessible_component

    @property
    def accessible_action(self) -> bool:
        return self._accessible_action

    @accessible_action.setter
    def accessible_action(self, accessible_action: bool) -> None:
        self._accessible_action = accessible_action

    @property
    def accessible_selection(self) -> bool:
        return self._accessible_selection

    @accessible_selection.setter
    def accessible_selection(self, accessible_selection: bool) -> None:
        self._accessible_selection = accessible_selection

    @property
    def accessible_text(self) -> bool:
        return self._accessible_text

    @accessible_text.setter
    def accessible_text(self, accessible_text: bool) -> None:
        self._accessible_text = accessible_text

    @property
    def accessible_interfaces(self) -> bool:
        return self._accessible_interfaces

    @accessible_interfaces.setter
    def accessible_interfaces(self, accessible_interfaces: bool) -> None:
        self._accessible_interfaces = accessible_interfaces

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, text: str) -> None:
        self._text = text

    @property
    def table(self) -> dict:
        return self._table

    @table.setter
    def table(self, table: dict) -> None:
        self._table = table

    # Jab Element actions
    def _generate_all_childs(self, jabelement: JABElement = None) -> Generator:
        """generate all child jab elements from a jab element.

        Args:
            jabelement (JABElement, optional): The parent jab element to generate child jab elements.
            Defaults to None use current element.

        Yields:
            Generator: Generator of all child jab elements from this parent jab element.
        """
        jabelement = (
            jabelement
            if jabelement
            else JABElement(self.bridge, self.hwnd, self.vmid, self.accessible_context)
        )
        for jabelement in self._generate_childs_from_element(jabelement):
            if jabelement.children_count != 0:
                yield from self._generate_all_childs(jabelement)
            yield jabelement

    def _generate_childs_from_element(self, jabelement: JABElement = None) -> Generator:
        """generate child jab elements from a jab element.

        Args:
            jabelement (JABElement, optional): The parent jab element to generate child jab elements.
            Defaults to None use current element.

        Yields:
            Generator: Generator of child jab elements from this parent jab element.
        """
        jabelement = (
            jabelement
            if jabelement
            else JABElement(self.bridge, self.hwnd, self.vmid, self.accessible_context)
        )
        for index in range(jabelement.children_count):
            child_acc = jabelement.bridge.getAccessibleChildFromContext(
                jabelement.vmid, jabelement.accessible_context, index
            )
            child_element = JABElement(
                jabelement.bridge, jabelement.hwnd, jabelement.vmid, child_acc
            )
            yield child_element

    def release_jabelement(self, jabelement: JABElement) -> None:
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
        self.bridge.releaseJavaObject(self.vmid, jabelement.accessible_context)

    def request_focus(self):
        """Request focus for a JABElement."""
        self.bridge.requestFocus(self.vmid, self.accessible_context)

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
            self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
            self.set_element_information()
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

    def clear(self, simulate: bool = False) -> None:
        """Clear existing text from JABElement.

        Default will use JAB Accessible Action.
        Set parameter 'simulate' to True if internal action does not work.

        Args:
            simulate (bool, optional): Simulate user input action by keyboard event. Defaults to False.

        Use this to send simple key events or to fill out form fields::

            form_textfield = driver.find_element_by_name('username')
            form_textfield.clear()
            from_textfield.send_text(simulate=True)
        """
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
            self.request_focus()
            if self.text:
                self.win32_utils._press_key("end")
                self.win32_utils._press_hold_release_key("ctrl", "shift", "end")
                for _ in self.text:
                    self.win32_utils._press_key("backspace")
        else:
            self.send_text(value="", simulate=False)

    def scroll(self, to_bottom: bool = True, hold: int = 2) -> None:
        """Scroll a scoll bar to top or to bottom.

        Need improvement for scroll to specific position.

        Args:
            to_bottom (bool, optional): Scroll to bottom or not, otherwise scroll to top. Defaults to True.
            hold (int, optional): Mouse hold time to scroll to bar. Default to 2.

        Raises:
            JABException: Raise a JABException when JABElement role is not a scroll bar.
        """
        if self.role_en_us != "scroll bar":
            raise JABException("JABElement is not 'scroll bar'")
        is_horizontal = True if "horizontal" in self.states_en_us else False
        x = self.bounds["x"]
        y = self.bounds["y"]
        height = self.bounds["height"]
        width = self.bounds["width"]
        self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
        # horizontal scroll to bottom(right)
        if to_bottom and is_horizontal:
            x = x + width - height - 5
            y = y + height / 2
        # vertical scroll to bottom
        elif to_bottom is True and is_horizontal is False:
            x = x + width / 2
            y = y + height - width - 5
        # horizontal scroll to top(left)
        elif to_bottom is False and is_horizontal is True:
            x = x + height + 5
            y = y + height / 2
        # vertical scroll to top
        elif to_bottom is False and is_horizontal is False:
            x = x + width / 2
            y = y + width + 5
        self.win32_utils._click_mouse(x=int(x), y=int(y), hold=hold)

    def slide(self, to_bottom: bool = True, hold: int = 5) -> None:
        """Slide a slider to top or to bottom.

        Need improvement for slide to specific position.

        Args:
            to_bottom (bool, optional): S;ode to bottom or not, otherwise slide to top. Defaults to True.
            hold (int, optional): Mouse hold time to slide. Default to 2.

        Raises:
            JABException: Raise a JABException when JABElement role is not a slider.
        """
        if self.role_en_us != "slider":
            raise JABException("JABElement is not 'slider'")
        is_horizontal = True if "horizontal" in self.states_en_us else False
        x = self.bounds["x"]
        y = self.bounds["y"]
        height = self.bounds["height"]
        width = self.bounds["width"]
        self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
        # horizontal slide to bottom(right)
        if to_bottom and is_horizontal:
            x = x + width - 5
            y = y + height / 2
        # vertical slide to bottom
        elif to_bottom is True and is_horizontal is False:
            x = x + width / 2
            y = y + height - 5
        # horizontal slide to top(left)
        elif to_bottom is False and is_horizontal is True:
            y = y + height / 2
        # vertical slide to top
        elif to_bottom is False and is_horizontal is False:
            x = x + width / 2
        self.win32_utils._click_mouse(x=int(x), y=int(y), hold=hold)

    def select(self, option: str, simulate: bool = False) -> None:
        """Select a item from JABElement selector.
        Support select action from combo box, page tab list, list and menu.

        Args:
            option (str): Item selection from selector.
            simulate (bool, optional): Simulate user input action by mouse event. Defaults to False.
        """
        _ = {
            "combo box": self._select_from_combobox,
            "page tab list": self._select_from_page_tab_list,
            "list": self._select_from_list,
            "menu": self._select_from_menu,
        }[self.role_en_us](option=option, simulate=simulate)

    def get_selected_element(self) -> JABElement:
        """Get selected JABElement from selection.
        Support get selection from combo box, list and page tab list.

        Returns:
            JABElement: The selected JABElement
        """
        selected_acc = self.bridge.getAccessibleSelectionFromContext(
            self.vmid, self.accessible_context, 0
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
        except JABException:
            raise JABException(f"{parent.role_en_us} option '{option}' does not found")
        item.bridge.addAccessibleSelectionFromContext(
            parent.vmid, parent.accessible_context, item.index_in_parent
        )

    def _select_from_checkbox(self, simulate: bool = False) -> None:
        if self.role_en_us != "check box":
            raise JABException("JABElement is not 'check box'")
        self.request_focus()
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
        self.click(simulate=simulate)

    def _select_from_combobox(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "combo box":
            raise JABException("JABElement is not 'combo box'")
        self.request_focus()
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
            self._do_accessible_action(action="togglepopup")
            self._add_selection_from_accessible_context(
                parent=self.find_element_by_role("list"), option=option
            )
            self.win32_utils._press_key("enter")
            return
        self.bridge.clearAccessibleSelectionFromContext(
            self.vmid, self.accessible_context
        )
        self._add_selection_from_accessible_context(parent=self, option=option)

    def _select_from_page_tab_list(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "page tab list":
            raise JABException("JABElement is not 'page tab list'")
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
            self.find_element_by_name(option).click(simulate=True)
            return
        self._add_selection_from_accessible_context(self, option=option)

    def _select_from_list(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "list":
            raise JABException("JABElement is not 'list'")
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
        self.find_element_by_name(value=option).click(simulate=simulate)

    def _select_from_menu(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "menu":
            raise JABException("JABElement is not 'menu'")
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
            self.click(simulate=True)
            for item in self.find_elements_by_object_depth(self.object_depth + 1):
                if item.accessible_action is False:
                    continue
                self.win32_utils._press_key("down_arrow")
                if item.name == option:
                    self.win32_utils._press_key("enter")
                    break
            return
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
            except JABException:
                raise JABException(
                    "Current spinbox does not support set 'option', try with 'increase'"
                )
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
            self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
            x = x + width - 5
            y = y + height / 2 + offset_y_position
            self.win32_utils._click_mouse(x=int(x), y=int(y))
            return
        self._do_accessible_action(action=action)

    def expand(self, simulate: bool = False) -> None:
        if "expandable" not in self._states_en_us:
            raise JABException("JABElement does not support 'expand'")
        if simulate:
            self.click(simulate=True)
            self.click(simulate=True)
            return
        self._do_accessible_action("toggleexpand")

    def send_text(self, value: str, simulate: bool = False) -> None:
        """Type into the JABElement.

        Default will use JAB Accessible Action.
        Set parameter 'simulate' to True if internal action does not work.

        :Args:
            value (str): A string for typing.
            simulate (bool, optional): Simulate user input action by keyboard event. Defaults to False.

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

    def is_checked(self) -> bool:
        """Returns whether the JABElement is checked.

        Can be used to check if a checkbox or radio button is checked.
        """
        self.set_element_information()
        return "checked" in self.states_en_us

    def is_enabled(self) -> bool:
        """Returns whether the JABElement is enabled."""
        self.set_element_information()
        return "enabled" in self.states_en_us

    def is_visible(self) -> bool:
        """Returns whether the JABElement is visible."""
        self.set_element_information()
        return "visible" in self.states_en_us

    def is_showing(self) -> bool:
        """Returns whether the JABElement is showing."""
        self.set_element_information()
        return "showing" in self.states_en_us

    def is_selected(self) -> bool:
        """Returns whether the JABElement is selected."""
        self.set_element_information()
        return "selected" in self.states_en_us

    def is_editable(self) -> bool:
        """Returns whether the JABElement is editable."""
        self.set_element_information()
        return "editable" in self.states_en_us

    def find_element_by_name(self, value: str) -> JABElement:
        """find child JABElement by name

        Args:
            value (str): Locator of JABElement need to find.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.NAME, value=value)

    def find_element_by_role(self, value: str) -> JABElement:
        """find child JABElement by role

        Args:
            value (str): Locator of JABElement need to find.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.ROLE, value=value)

    def find_element_by_states(self, value: list) -> JABElement:
        """find child JABElement by states

        Args:
            value (list): Locator of JABElement need to find.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.STATES, value=value)

    def find_element_by_object_depth(self, value: int) -> JABElement:
        """find child JABElement by object depth

        Args:
            value (int): Locator of JABElement need to find.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.OBJECT_DEPTH, value=value)

    def find_element_by_children_count(self, value: int) -> JABElement:
        """find child JABElement by children count

        Args:
            value (int): Locator of JABElement need to find.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.CHILDREN_COUNT, value=value)

    def find_element_by_index_in_parent(self, value: int) -> JABElement:
        """find child JABElement by index in parent

        Args:
            value (int): Locator of JABElement need to find.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.INDEX_IN_PARENT, value=value)

    def _is_match_attr_name(self, attr_val: str, jabelement: JABElement) -> bool:
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
        content = pattern.findall(attr_val)
        if content:
            return content[0] in jabelement.name
        else:
            return attr_val == jabelement.name

    def _is_match_attr_states(self, attr_val: str, jabelement: JABElement) -> bool:
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
        content = pattern.findall(attr_val)
        if content:
            return all(
                [stat in jabelement.states_en_us for stat in content[0].split(",")]
            )
        else:
            return set(attr_val.split(",")) == set(jabelement.states_en_us)

    def _is_match_attr_objectdepth(self, attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by object depth.

        Args:
            attr_val (str): Attribute object depth value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        return int(attr_val) == jabelement.object_depth

    def _is_match_attr_childrencount(
        self, attr_val: str, jabelement: JABElement
    ) -> bool:
        """Return the attribute value is matched or not by children count.

        Args:
            attr_val (str): Attribute children count value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        return int(attr_val) == jabelement.children_count

    def _is_match_attr_indexinparent(
        self, attr_val: str, jabelement: JABElement
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
            "states": self._is_match_attr_states,
            "objectdepth": self._is_match_attr_objectdepth,
            "childrencount": self._is_match_attr_childrencount,
            "indexinparent": self._is_match_attr_indexinparent,
        }
        for attribute in attributes:
            name = attribute.get("name")
            value = attribute.get("value")
            if name not in dict_attribute.keys():
                raise JABException("incorrect attribute name '{}'".format(name))
            if not dict_attribute[name](value, jabelement):
                return False
        return True

    def _get_node_element(self, jabelement: JABElement = None) -> JABElement:
        """Get node JABElement.

        Args:
            jabelement (JABElement, optional): The JABElement. Defaults to None.

        Raises:
            JABException: internal JAB func getTopLevelObject error

        Returns:
            JABElement: Node JABElement
        """
        jabelement = (
            jabelement
            if jabelement
            else JABElement(self.bridge, self.hwnd, self.vmid, self.accessible_context)
        )
        is_same = bool(
            self.bridge.isSameObject(
                self.vmid, self.accessible_context, jabelement.accessible_context
            )
        )
        if is_same:
            top_object = self.bridge.getTopLevelObject(
                self.vmid, self.accessible_context
            )
            if top_object == 0:
                raise JABException(self.int_func_err_msg.format("getTopLevelObject"))
            is_top_level = bool(
                self.bridge.isSameObject(self.vmid, self.accessible_context, top_object)
            )
            if is_top_level:
                return jabelement
            else:
                return self.parent
        else:
            return jabelement

    def _get_element_by_node(
        self, node: str, level: str = "root", jabelement: JABElement = None
    ) -> JABElement:
        """Get child JABElement by specific node

        Args:
            node (str): Node content for every single content in xpath.\n
            level (str, optional): Level for node, two options: "root" and "child". Defaults to "root".\n
            jabelement (JABElement, optional): The parent JABElement. Defaults to None.

        Raises:
            ValueError: Incorect level set
            JABException: No JABElement found with specific node

        Returns:
            JABElement: The child JABElement
        """
        dict_gen = {
            "root": self._generate_all_childs,
            "child": self._generate_childs_from_element,
        }
        if level not in dict_gen.keys():
            raise ValueError("level should be in 'root' or 'child'")
        node_info = self.xpath_parser.get_node_information(node)
        node_role = node_info.get("role")
        node_attributes = node_info.get("attributes")
        jabelement = self._get_node_element(jabelement)
        child_jabelement = None
        for _jabelement in dict_gen[level](jabelement):
            if node_role not in ["*", _jabelement.role_en_us]:
                self.release_jabelement(_jabelement)
                continue
            if self._is_match_attributes(node_attributes, _jabelement):
                child_jabelement = _jabelement
                break
            self.release_jabelement(_jabelement)
        else:
            raise JABException(
                "no JABElement found in level {} with node '{}'".format(level, node)
            )
        return child_jabelement

    def find_element_by_xpath(self, value: str) -> JABElement:
        """find child JABElement by xpath

        Args:
            value (str): Locator of JABElement need to find.

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
                node=node, level=level, jabelement=jabelement
            )
        return jabelement

    def find_element(self, by: str = By.NAME, value: Any = None) -> JABElement:
        """Find an jab element given a By strategy and locator.

        Args:
            by (str, optional): By strategy of element need to find. Defaults to By.NAME.
            value (Any, optional): Locator of element need to find.
            Defaults to None will select the first child jab element.

        Returns:
            JABElement: The element find by locator
        """
        if by not in [
            By.NAME,
            By.ROLE,
            By.STATES,
            By.OBJECT_DEPTH,
            By.CHILDREN_COUNT,
            By.INDEX_IN_PARENT,
            By.XPATH,
        ]:
            raise JABException("incorrect by strategy '{}'".format(by))
        if by == By.XPATH:
            self.find_element_by_xpath(value)
        located_element = None
        for jabelement in self._generate_all_childs():
            is_matched = (
                (value is None)
                or (by == By.NAME and jabelement.name == value)
                or (by == By.ROLE and jabelement.role_en_us == value)
                or (by == By.STATES and set(jabelement.states_en_us) == set(value))
                or (by == By.OBJECT_DEPTH and jabelement.object_depth == int(value))
                or (by == By.CHILDREN_COUNT and jabelement.children_count == int(value))
                or (
                    by == By.INDEX_IN_PARENT
                    and jabelement.index_in_parent == int(value)
                )
            )
            if is_matched:
                located_element = jabelement
                break
            self.release_jabelement(jabelement)
        else:
            raise JABException(
                "jab element not found by '{}' with locator '{}'".format(by, value)
            )
        return located_element

    def find_elements_by_name(self, value: str) -> list[JABElement]:
        """Find list of child JABElement by name

        Args:
            value (str): Locator of list JABElement need to find.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.NAME, value=value)

    def find_elements_by_role(self, value: str) -> list[JABElement]:
        """Find list of child JABElement by role

        Args:
            value (str): Locator of list JABElement need to find.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.ROLE, value=value)

    def find_elements_by_states(self, value: list) -> list[JABElement]:
        """Find list of child JABElement by states

        Args:
            value (str): Locator of list JABElement need to find.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.STATES, value=value)

    def find_elements_by_object_depth(self, value: int) -> list[JABElement]:
        """Find list of child JABElement by object depth

        Args:
            value (str): Locator of list JABElement need to find.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.OBJECT_DEPTH, value=value)

    def find_elements_by_children_count(self, value: int) -> list[JABElement]:
        """Find list of child JABElement by children count

        Args:
            value (str): Locator of list JABElement need to find.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.CHILDREN_COUNT, value=value)

    def find_elements_by_index_in_parent(self, value: int) -> list[JABElement]:
        """Find list of child JABElement by index inparent

        Args:
            value (str): Locator of list JABElement need to find.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.INDEX_IN_PARENT, value=value)

    def _get_elements_by_node(
        self, node: str, level: str = "root", jabelement: JABElement = None
    ) -> list[JABElement]:
        """Get list of child JABElement by specific node

        Args:
            node (str): Node content for every single content in xpath.\n
            level (str, optional): Level for node, two options: "root" and "child". Defaults to "root".\n
            jabelement (JABElement, optional): The parent JABElement. Defaults to None.

        Raises:
            ValueError: Incorect level set

        Returns:
            list[JABElement]: list of the JABElement
        """
        dict_gen = {
            "root": self._generate_all_childs,
            "child": self._generate_childs_from_element,
        }
        if level not in dict_gen.keys():
            raise ValueError("level should be in 'root' or 'child'")
        node_info = self.xpath_parser.get_node_information(node)
        node_role = node_info.get("role")
        node_attributes = node_info.get("attributes")
        jabelement = self._get_node_element(jabelement)
        jabelements = list()
        for _jabelement in dict_gen[level](jabelement):
            if node_role not in ["*", _jabelement.role_en_us]:
                self.release_jabelement(_jabelement)
                continue
            if self._is_match_attributes(node_attributes, _jabelement):
                jabelements.append(_jabelement)
                continue
            self.release_jabelement(_jabelement)
        return jabelements

    def find_elements_by_xpath(self, value: str) -> list[JABElement]:
        """Find list of child JABElement by xpath

        Args:
            value (str): Locator of JABElement need to find.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """

        def generate_node(nodes: list[str]) -> Generator:
            for index, node in enumerate(nodes):
                level = "root" if index == 0 else "child"
                yield node, level

        def get_child_jabelements(
            node: str, level: str, parent_jabelements: list[JABElement]
        ) -> list(JABElement):
            child_jabelements = list()
            for parent_jabelement in parent_jabelements:
                jabelements = self._get_elements_by_node(
                    node=node, level=level, jabelement=parent_jabelement
                )
                child_jabelements.extend(jabelements)
            return child_jabelements

        nodes = self.xpath_parser.split_nodes(value)
        jabelements = [
            JABElement(self.bridge, self.hwnd, self.vmid, self.accessible_context)
        ]
        for node, level in generate_node(nodes):
            if not jabelements:
                raise JABException("no JABElement found")
            jabelements = get_child_jabelements(node, level, jabelements)
        return jabelements

    def find_elements(self, by: str = By.NAME, value: str = None) -> list[JABElement]:
        """Find list of JABElement given a By strategy and locator.

        Args:
            by (str, optional): By strategy of element need to find. Defaults to By.NAME.
            value (Any, optional): Locator of element need to find.
            Defaults to None will select the first child jab element.

        Returns:
            list: List of JABElement find by locator
        """
        if by not in [
            By.NAME,
            By.ROLE,
            By.STATES,
            By.OBJECT_DEPTH,
            By.CHILDREN_COUNT,
            By.INDEX_IN_PARENT,
            By.XPATH,
        ]:
            raise JABException("incorrect by strategy '{}'".format(by))
        if by == By.XPATH:
            self.find_elements_by_xpath(value)
        jabelements = list()
        for jabelement in self._generate_all_childs():
            is_matched = (
                (value is None)
                or (by == By.NAME and jabelement.name == value)
                or (by == By.ROLE and jabelement.role_en_us == value)
                or (by == By.STATES and set(jabelement.states_en_us) == set(value))
                or (by == By.OBJECT_DEPTH and jabelement.object_depth == int(value))
                or (by == By.CHILDREN_COUNT and jabelement.children_count == int(value))
                or (
                    by == By.INDEX_IN_PARENT
                    and jabelement.index_in_parent == int(value)
                )
            )
            if is_matched:
                jabelements.append(jabelement)
                continue
            self.release_jabelement(jabelement)
        if not jabelements:
            raise JABException(
                "no JABElement found by '{}' with locator '{}'".format(by, value)
            )
        return jabelements

    @property
    def size(self) -> dict:
        """The size of the element."""
        self.set_element_information()
        return dict(height=self.bounds.get("height"), width=self.bounds.get("width"))

    @property
    def location(self) -> dict:
        """The location of the element in the renderable canvas."""
        self.set_element_information()
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
        self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
        self.set_element_information()
        x = self.bounds.get("x")
        y = self.bounds.get("y")
        width = self.bounds.get("width")
        height = self.bounds.get("height")
        im = ImageGrab.grab(
            bbox=(
                x,
                y,
                x + width,
                y + height,
            ),
            include_layered_windows=False,
            all_screens=True,
        )
        return im

    @property
    def parent(self):
        """Internal reference to the JabDriver instance this element was found from."""
        self.set_element_information()
        parent_acc = self.bridge.getAccessibleParentFromContext(
            self.vmid, self.accessible_context
        )
        return JABElement(
            bridge=self.bridge,
            hwnd=self.hwnd,
            vmid=self.vmid,
            accessible_context=parent_acc,
        )

    def set_element_information(self) -> None:
        """Set JABElement information(attributes) from internal jab funcs

        Raises:
            JABException: None value of vmid, hwnd or accessible_context
            JABException: Get Accessible Context Info error(internal jab func error)
            JABException: Get Object Depth error(internal jab func error)
        """
        if not any([self.vmid, self.hwnd, self.accessible_context]):
            raise JABException(
                "JABElement attributes should have vmid, hwnd and accessible_context"
            )
        info = AccessibleContextInfo()
        result = self.bridge.getAccessibleContextInfo(
            self.vmid, self.accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("GetAccessibleContextInfo"))
        object_depth = self.bridge.getObjectDepth(self.vmid, self.accessible_context)
        if object_depth == -1:
            raise JABException(self.int_func_err_msg.format("getObjectDepth"))
        self.name = info.name
        self.description = info.description
        self.role = info.role
        self.role_en_us = info.role_en_US
        self.states = info.states.split(",")
        self.states_en_us = info.states_en_US.split(",")
        self.bounds = dict(
            x=info.x,
            y=info.y,
            height=info.height,
            width=info.width,
        )
        self.object_depth = object_depth
        self.index_in_parent = info.indexInParent
        self.children_count = info.childrenCount
        self.accessible_component = bool(info.accessibleComponent)
        self.accessible_action = bool(info.accessibleAction)
        self.accessible_selection = bool(info.accessibleSelection)
        self.accessible_text = bool(info.accessibleText)
        self._set_element_text_information()
        self._set_element_table_information()

    def _set_element_text_information(self) -> None:
        """Set attribute text if element has accessible text

        Raises:
            JABException: Raise JABException if getAccessibleTextItems get internal error
        """
        if not self.accessible_text:
            return
        info = AccessibleTextInfo()
        result = self.bridge.getAccessibleTextInfo(
            self.vmid, self.accessible_context, byref(info), 0, 0
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleTextInfo"))
        chars_start = 0
        chars_end = info.charCount - 1
        chars_len = chars_end + 1 - chars_start
        buffer = create_string_buffer((chars_len + 1) * 2)
        result = self.bridge.getAccessibleTextRange(
            self.vmid,
            self.accessible_context,
            chars_start,
            chars_end,
            buffer,
            chars_len,
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleTextRange"))
        self.text = TextReader().get_text_from_raw_bytes(
            buffer=buffer, chars_len=chars_len, encoding="utf_16"
        )

    def _set_element_table_information(self) -> None:
        """Get Accessible table information

        Raises:
            JABException: Raise JABException if
            getAccessibleTableInfo,
            getAccessibleTableRowHeader,
            getAccessibleTableColumnHeader get internal error
        """
        if self.role_en_us == "table":
            info = AccessibleTableInfo()
            result = self.bridge.getAccessibleTableInfo(
                self.vmid, self.accessible_context, byref(info)
            )
            if result == 0:
                raise JABException(
                    self.int_func_err_msg.format("getAccessibleTableInfo")
                )
            self.table = {
                "row_count": info.rowCount,
                "column_count": info.columnCount,
            }
            info = AccessibleTableInfo()
            result = self.bridge.getAccessibleTableRowHeader(
                self.vmid, self.accessible_context, byref(info)
            )
            if result == 0:
                raise JABException(
                    self.int_func_err_msg.format("getAccessibleTableRowHeader")
                )
            self.table["row_headers"] = {
                "row_count": info.rowCount,
                "column_count": info.columnCount,
            }
            info = AccessibleTableInfo()
            result = self.bridge.getAccessibleTableColumnHeader(
                self.vmid, self.accessible_context, byref(info)
            )
            if result == 0:
                raise JABException(
                    self.int_func_err_msg.format("getAccessibleTableColumnHeader")
                )
            self.table["column_headers"] = {
                "row_count": info.rowCount,
                "column_count": info.columnCount,
            }
            row_count = self.bridge.getAccessibleTableRowSelectionCount(
                self.vmid, self.accessible_context
            )
            column_count = self.bridge.getAccessibleTableColumnSelectionCount(
                self.vmid, self.accessible_context
            )
            self.table["selected"] = {
                "row_count": row_count,
                "column_count": column_count,
            }

    def get_cell(self, row: int, column: int) -> JABElement:
        """Get cell JABElement from table

        Args:
            row (int): Row index of cell, start from 0
            column (int): Column index of cell, start from 0

        Raises:
            JABException: Raise JABException if JAB internal function error

        Returns:
            JABElement: Return specific cell JABElement
        """
        if self.role_en_us != "table":
            raise JABException("JABElement is not table, does not support this func")
        info = AccessibleTableCellInfo()
        result = self.bridge.getAccessibleTableCellInfo(
            self.vmid, self.accessible_context, row, column, byref(info)
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableCellInfo")
            )
        return JABElement(self.bridge, self.hwnd, self.vmid, info.accessibleContext)

    def get_element_information(self) -> dict:
        """Get dict information of current JABElement

        Returns:
            dict: Dict information of current JABElement
        """
        return dict(
            name=self.name,
            description=self.description,
            role=self.role,
            role_en_us=self.role_en_us,
            states=self.states,
            states_en_us=self.states_en_us,
            bounds=self.bounds,
            object_depth=self.object_depth,
            index_in_parent=self.index_in_parent,
            children_count=self.children_count,
            accessible_component=self.accessible_component,
            accessible_action=self.accessible_action,
            accessible_selection=self.accessible_selection,
            accessible_text=self.accessible_text,
            text=self.text,
            table=self.table,
        )
