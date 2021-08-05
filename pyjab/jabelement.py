from __future__ import annotations
import re
from ctypes import byref
from ctypes import CDLL
from ctypes import c_long
from ctypes.wintypes import HWND
from typing import Any
from typing import Generator
from PIL import Image
from PIL import ImageGrab
from pyjab.common.by import By
from pyjab.common.exceptions import JABException
from pyjab.common.logger import Logger
from pyjab.common.shortcutkeys import ShortcutKeys
from pyjab.common.types import JOBJECT64
from pyjab.common.win32utils import Win32Utils
from pyjab.common.xpathparser import XpathParser
from pyjab.accessibleinfo import AccessibleContextInfo
from pyjab.accessibleinfo import AccessibleTextItemsInfo


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
        # not recommand instantiation for low performance
        # self.log = Logger(self.__class__.__name__)
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
    def text(self) -> bool:
        return self._text

    @text.setter
    def text(self, text: bool) -> None:
        self._text = text

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

    def click(self) -> None:
        """Clicks the JABElement."""
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

    def clear(self) -> None:
        """Clears the text if it's a text entry JABElement."""
        if self.role_en_us not in ["label", "text", "password text"]:
            raise TypeError(
                "JABElement role '{}' does not support clear".format(self.role_en_us)
            )
        self.win32_utils._set_window_foreground(hwnd=self.hwnd.value)
        self.request_focus()
        self.shortcut_keys.clear_text()

    def select(self, value: str) -> None:
        """Select a dropdown item from selector."""
        if not self.accessible_selection:
            raise AttributeError("Current JABElement does not support selection")
        labels = self.find_elements_by_role("label")
        for index, label in enumerate(labels):
            if value == label.name:
                self.bridge.addAccessibleSelectionFromContext(
                    self.vmid, self.accessible_context, index
                )
                break
        else:
            raise ValueError(f"Option '{value}' does not found")

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

    def send_text(self, value: str) -> None:
        """Simulates typing into the element.

        :Args:
            - value - A string for typing.

        Use this to send simple key events or to fill out form fields::

            form_textfield = driver.find_element_by_name('username')
            form_textfield.send_keys("admin")
        """
        self.clear()
        self.win32_utils._send_keys(value)

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
        if self.accessible_text:
            info = AccessibleTextItemsInfo()
            result = self.bridge.getAccessibleTextItems(
                self.vmid, self.accessible_context, byref(info), 0
            )
            if result == 0:
                raise JABException(
                    self.int_func_err_msg.format("getAccessibleTextItems")
                )
            self.text = info.sentence

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
        )
