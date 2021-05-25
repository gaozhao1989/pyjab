from ctypes import (
    CDLL,
    c_long,
)
from ctypes import byref
from ctypes.wintypes import HWND
from PIL import Image, ImageGrab
from pyjab.jabelement import JABElement
from pyjab.jabfixedfunc import JABFixedFunc
from pyjab.common.actorscheduler import ActorScheduler
from pyjab.common.by import By
from typing import Dict, List
from pyjab.common.exceptions import JABException
from pyjab.common.logger import Logger
from pyjab.common.service import Service
from pyjab.common.types import JOBJECT64
from pyjab.common.xpathparser import XpathParser


class JABDriver(Service, ActorScheduler):
    def __init__(self, title: str = "") -> None:
        super(JABDriver, self).__init__()
        self.log = Logger(self.__class__.__name__)
        self._title = title
        self._bridge = self.service_bridge
        JABFixedFunc(self._bridge).fix_bridge_functions()
        self._root_element = JABElement()
        self.int_func_err_msg = "Java Access Bridge func '{}' error"
        self.init_jab_service()
        self.xpath_parser = XpathParser()

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
    def root_element(self, root_element) -> None:
        self._root_element = root_element

    def init_jab_service(self, root_element: JABElement = JABElement()) -> None:
        # invoke generator in message queue
        sched = ActorScheduler()
        sched.new_actor("jab", self.setup_msg_pump())
        sched.run()
        # init jab
        win_hwnd = self.wait_hwnd_by_title(self._title)
        java_hwnd = self.wait_java_window_present(win_hwnd)
        hwnd = root_element.hwnd or java_hwnd
        vmid = root_element.vmid
        accessible_context = root_element.accessible_context
        if hwnd and not vmid:
            vmid = c_long()
            accessible_context = JOBJECT64()
            self.bridge.getAccessibleContextFromHWND(
                hwnd, byref(vmid), byref(accessible_context)
            )
            vmid = vmid.value
        elif vmid and not hwnd:
            accessible_context = JOBJECT64()
            hwnd = self.bridge.getHWNDFromAccessibleContext(
                byref(vmid), byref(accessible_context)
            )
        if not (vmid and hwnd):
            raise RuntimeError("both vmid and hwnd empty, please check")
        self.root_element.hwnd = HWND(hwnd)
        self.root_element.vmid = c_long(vmid)
        self.root_element.accessible_context = accessible_context

    # jab driver functions: similar with webdriver
    @property
    def title(self) -> str:
        """
        Returns the title of current java window
        """
        win_title = self.get_title_by_hwnd(self.root_element.hwnd)
        self.logger.debug("current java window title '{}'".format(win_title))
        return win_title

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

    def find_element(self, by: str = By.NAME, value: str = None) -> JABElement:
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
        # TODO: set func to maximize window

    def minimize_window(self):
        """
        Invokes the window manager-specific 'minimize' operation
        """
        # TODO: set func to minimize window

    def implicitly_wait(self, time_to_wait):
        """
        Sets a sticky timeout to implicitly wait for an element to be found,
           or a command to complete. This method only needs to be called one
           time per session. To set the timeout for calls to
           execute_async_script, see set_script_timeout.

        :Args:
         - time_to_wait: Amount of time to wait (in seconds)

        :Usage:
            driver.implicitly_wait(30)
        """
        # TODO: set func to implicitly_wait

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
        self.set_window_foreground(hwnd=self.hwnd.value)
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
        # TODO: set func to set_window_size

    def set_window_position(self, x, y):
        """
        Sets the x,y position of the current window. (window.moveTo)

        :Args:
         - x: the x-coordinate in pixels to set the window position
         - y: the y-coordinate in pixels to set the window position

        :Usage:
            driver.set_window_position(0,0)
        """
        # TODO: set func to set_window_position

    def get_window_position(self):
        """
        Gets the x,y position of the current window.

        :Usage:
            driver.get_window_position()
        """
        # TODO: set func to get_window_position