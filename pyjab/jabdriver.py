from __future__ import annotations
from ctypes import byref
from ctypes import CDLL
from ctypes import c_long
from ctypes.wintypes import HWND
from time import time, sleep
from typing import Any
from PIL import ImageGrab
from pyjab.common.actorscheduler import ActorScheduler
from pyjab.common.by import By
from pyjab.common.exceptions import JABException
from pyjab.common.logger import Logger
from pyjab.common.service import Service
from pyjab.common.types import JOBJECT64
from pyjab.common.xpathparser import XpathParser
from pyjab.config import TIMEOUT
from pyjab.jabelement import JABElement
from pyjab.jabfixedfunc import JABFixedFunc


class JABDriver(Service, ActorScheduler):
    int_func_err_msg = "Java Access Bridge func '{}' error"

    def __init__(self, title: str = "") -> None:
        super(JABDriver, self).__init__()
        self.logger = Logger(self.__class__.__name__)
        self._title = title
        self._bridge = None
        self._root_element = None
        self.init_jab_service()
        JABFixedFunc(self._bridge)._fix_bridge_functions()
        self.xpath_parser = XpathParser()

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, title: str) -> None:
        self._title = title

    @property
    def bridge(self) -> CDLL:
        return self._bridge

    @bridge.setter
    def bridge(self, bridge: CDLL) -> None:
        self._bridge = bridge

    @property
    def root_element(self) -> JABElement:
        return self._root_element

    @root_element.setter
    def root_element(self, root_element: JABElement) -> None:
        self._root_element = root_element

    def init_jab_service(
        self,
        hwnd: HWND = None,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> None:
        # enum window and find hwnd
        win_hwnd = self.wait_hwnd_by_title(self.title)
        self.bridge = self.load_library()
        self.bridge.Windows_run()
        # invoke generator in message queue
        sched = ActorScheduler()
        sched.new_actor("jab", self.setup_msg_pump())
        sched.run()
        # init jab
        self.bridge.Windows_run()
        self._wait_until_java_window_exist(win_hwnd)
        hwnd = hwnd or win_hwnd
        if hwnd and not vmid:
            # must have hwnd
            vmid = c_long()
            accessible_context = JOBJECT64()
            self.bridge.getAccessibleContextFromHWND(
                hwnd, byref(vmid), byref(accessible_context)
            )
            vmid = vmid.value
        elif vmid and accessible_context and not hwnd:
            # must have vmid and accessible_context
            top_level_object = self.bridge.getTopLevelObject(vmid, accessible_context)
            hwnd = self.bridge.getHWNDFromAccessibleContext(vmid, top_level_object)
        else:
            raise RuntimeError(
                "At least hwnd or vmid and accessible_context is required"
            )
        self.root_element = JABElement(
            bridge=self.bridge,
            hwnd=HWND(hwnd),
            vmid=c_long(vmid),
            accessible_context=accessible_context,
        )
        # TODO:fix JABElement not loading complete
        sleep(2)

    def _is_java_window(self, hwnd: HWND) -> bool:
        """Return the specific window is or not a Java Window

        Args:
            hwnd (HWND): The hwnd of window. Defaults to None.

        Returns:
            bool: True if is a Java Window. False is not a Java Window.
        """
        return bool(self.bridge.isJavaWindow(hwnd))

    def _wait_until_java_window_exist(self, hwnd: HWND, timeout: int = TIMEOUT) -> None:
        """Wait until a Java Window exist in specific seconds.

        Args:
            hwnd (HWND): The hwnd of specific Java Window need to wait.
            timeout (int, optional): The timeout seconds. Defaults to TIMEOUT.

        Raises:
            TimeoutError: Timeout error occurs when wait time over the specific timeout

        Returns:
            None
        """
        start = time()
        while True:
            if self._is_java_window(hwnd):
                break
            current = time()
            elapsed = round(current - start)
            if elapsed >= timeout:
                raise TimeoutError(
                    "no java window found by hwnd '{}' in '{}'seconds".format(
                        hwnd, timeout
                    )
                )

    # jab driver functions: similar with webdriver
    def find_element_by_name(self, value: str) -> JABElement:
        """
        Find an JABElement given a name locator.
        """
        if value == self.root_element.name:
            return self.root_element
        else:
            return self.root_element.find_element_by_name(value)

    def find_element_by_role(self, value: str) -> JABElement:
        """
        Find an JABElement given a role locator.
        """
        if value == self.root_element.role:
            return self.root_element
        else:
            return self.root_element.find_element_by_role(value)

    def find_element_by_states(self, value: str) -> JABElement:
        """
        Find an JABElement given a states locator.
        """
        if value == self.root_element.states:
            return self.root_element
        else:
            return self.root_element.find_element_by_states(value)

    def find_element_by_object_depth(self, value: int) -> JABElement:
        """
        Find an JABElement given a object depth locator.
        """
        if value == self.root_element.object_depth:
            return self.root_element
        else:
            return self.root_element.find_element_by_object_depth(value)

    def find_element_by_children_count(self, value: int) -> JABElement:
        """
        Find an JABElement given a children count locator.
        """
        if value == self.root_element.children_count:
            return self.root_element
        else:
            return self.root_element.find_element_by_children_count(value)

    def find_element_by_index_in_parent(self, value: int) -> JABElement:
        """
        Find an JABElement given a index in parent locator.
        """
        if value == self.root_element.index_in_parent:
            return self.root_element
        else:
            return self.root_element.find_element_by_index_in_parent(value)

    def find_element_by_xpath(self, value: str) -> JABElement:
        """
        Find an JABElement given a index in parent locator.
        """
        return self.root_element.find_element_by_xpath(value)

    def find_element(self, by: str = By.NAME, value: Any = None) -> JABElement:
        """
        Find an JABElement given a By strategy and locator.
        """
        dict_find = {
            By.NAME: self.find_element_by_name,
            By.ROLE: self.find_element_by_role,
            By.STATES: self.find_element_by_states,
            By.OBJECT_DEPTH: self.find_element_by_object_depth,
            By.CHILDREN_COUNT: self.find_element_by_children_count,
            By.INDEX_IN_PARENT: self.find_element_by_index_in_parent,
            By.XPATH: self.find_element_by_xpath,
        }
        if by not in dict_find.keys():
            raise JABException("incorrect by strategy '{}'".format(by))
        return dict_find[by](value)

    def find_elements_by_name(self, value: str) -> list[JABElement]:
        """
        Find list of JABElement given a name locator.
        """
        jabelements = list()
        if value == self.root_element.name:
            jabelements.append(self.root_element)
        jabelements.extend(self.root_element.find_elements_by_name(value))
        return jabelements

    def find_elements_by_role(self, value: str) -> list[JABElement]:
        """
        Find list of JABElement given a role locator.
        """
        jabelements = list()
        if value == self.root_element.role:
            jabelements.append(self.root_element)
        jabelements.extend(self.root_element.find_elements_by_role(value))
        return jabelements

    def find_elements_by_states(self, value: str) -> list[JABElement]:
        """
        Find list of JABElement given a states locator.
        """
        jabelements = list()
        if value == self.root_element.states:
            jabelements.append(self.root_element)
        jabelements.extend(self.root_element.find_elements_by_states(value))
        return jabelements

    def find_elements_by_object_depth(self, value: int) -> list[JABElement]:
        """
        Find list of JABElement given a object depth locator.
        """
        jabelements = list()
        if value == self.root_element.object_depth:
            jabelements.append(self.root_element)
        jabelements.extend(self.root_element.find_elements_by_object_depth(value))
        return jabelements

    def find_elements_by_children_count(self, value: int) -> list[JABElement]:
        """
        Find list of JABElement given a children count locator.
        """
        jabelements = list()
        if value == self.root_element.children_count:
            jabelements.append(self.root_element)
        jabelements.extend(self.root_element.find_elements_by_children_count(value))
        return jabelements

    def find_elements_by_index_in_parent(self, value: int) -> list[JABElement]:
        """
        Find list of JABElement given a index in parent locator.
        """
        jabelements = list()
        if value == self.root_element.index_in_parent:
            jabelements.append(self.root_element)
        jabelements.extend(self.root_element.find_elements_by_index_in_parent(value))
        return jabelements

    def find_elements_by_xpath(self, value: str) -> list[JABElement]:
        """
        Find list of JABElement given a index in parent locator.
        """
        return self.root_element.find_elements_by_xpath(value)

    def find_elements(self, by: str = By.NAME, value: str = None) -> list[JABElement]:
        """
        Find list of JABElement given a By strategy and locator.
        """
        dict_finds = {
            By.NAME: self.find_elements_by_name,
            By.ROLE: self.find_elements_by_role,
            By.STATES: self.find_elements_by_states,
            By.OBJECT_DEPTH: self.find_elements_by_object_depth,
            By.CHILDREN_COUNT: self.find_elements_by_children_count,
            By.INDEX_IN_PARENT: self.find_elements_by_index_in_parent,
            By.XPATH: self.find_elements_by_xpath,
        }
        if by not in dict_finds.keys():
            raise JABException("incorrect by strategy '{}'".format(by))
        return dict_finds[by](value)

    def maximize_window(self):
        """
        Maximizes the current java window that jabdriver is using
        """
        self._set_window_maximize(hwnd=self.root_element.hwnd.value)

    def minimize_window(self):
        """
        Invokes the window manager-specific 'minimize' operation
        """
        self._set_window_minimize(hwnd=self.root_element.hwnd.value)

    def wait_until_element_exist(
        self, by: str = By.NAME, value: Any = None, timeout: int = TIMEOUT
    ) -> JABElement:
        start = time()
        while True:
            current = time()
            elapsed = round(current - start)
            remain = round(timeout - elapsed)
            self.logger.debug("elapsed => {}, remain => {}".format(elapsed, remain))
            if elapsed >= timeout:
                raise JABException(
                    "JABElement does not found in {} seconds".format(timeout)
                )
            try:
                jabelement = self.find_element(by=by, value=value)
                return jabelement
            except JABException:
                self.logger.warning("JABElement does not found")

    def get_screenshot_as_file(self, filename):
        """
        Saves a screenshot of the current window to a PNG image file. Returns
           False if there is any IOError, else returns True. Use full paths in
           your filename.

        :Args:
         - filename: The full path you wish to save your screenshot to. This
           should end with a `.png` extension.

        :Usage:
            driver.get_screenshot_as_file('/Screenshots/foo.png')
        """
        im = self.get_screenshot()
        im.save(filename)

    def get_screenshot(self):
        """
        Gets the screenshot of the current window as a base64 encoded string
           which is useful in embedded images in HTML.

        :Usage:
            driver.get_screenshot_as_base64()
        """
        self._set_window_foreground(hwnd=self.root_element.hwnd.value)
        self.root_element.set_element_information()
        x = self.root_element.bounds.get("x")
        y = self.root_element.bounds.get("y")
        width = self.root_element.bounds.get("width")
        height = self.root_element.bounds.get("height")
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

    def set_window_size(self, width, height):
        """
        Sets the width and height of the current window. (window.resizeTo)

        :Args:
         - width: the width in pixels to set the window to
         - height: the height in pixels to set the window to

        :Usage:
            driver.set_window_size(800,600)
        """
        self._set_window_size(hwnd=self.root_element.hwnd.value, width=width, height=height)

    def set_window_position(self, x, y):
        """
        Sets the x,y position of the current window. (window.moveTo)

        :Args:
         - x: the x-coordinate in pixels to set the window position
         - y: the y-coordinate in pixels to set the window position

        :Usage:
            driver.set_window_position(0,0)
        """
        self._set_window_position(hwnd=self.root_element.hwnd.value, left=x, top=y)

    def get_window_position(self):
        """
        Gets the x,y position of the current window.

        :Usage:
            driver.get_window_position()
        """
        return self._get_window_position(hwnd=self.root_element.hwnd.value)
