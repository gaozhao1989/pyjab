from ctypes import (
    CDLL,
    c_long,
)
from ctypes import byref
from ctypes.wintypes import HWND
from pyjab.jabelement import JABElement
from pyjab.jabfixedfunc import JABFixedFunc
from pyjab.common.actorscheduler import ActorScheduler
from pyjab.common.by import By
from typing import Dict, List
from pyjab.common.logger import Logger
from pyjab.common.service import Service
from pyjab.common.types import JOBJECT64, jint


class JABDriver(Service, ActorScheduler):
    def __init__(self, title: str = "") -> None:
        super(JABDriver, self).__init__()
        self.log = Logger(self.__class__.__name__)
        self._title = title
        self._bridge = self.service_bridge
        JABFixedFunc(self._bridge).fix_bridge_functions()
        self._root_element = JABElement()
        self._vmids = dict()
        self.int_func_err_msg = "Java Access Bridge func '{}' error"
        self.init_jab_service()

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

    @property
    def vmids(self) -> Dict[str, HWND]:
        return self._vmids

    @vmids.setter
    def vmids(self, vmids: Dict[str, HWND]) -> None:
        self._vmids = vmids

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
            vmid = c_long()
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
        Find an jab element given a name locator.
        """
        if value == self.root_element.name:
            return self.root_element
        else:
            return self.root_element.find_element_by_name(value)

    def find_element_by_role(self, value: str) -> JABElement:
        """
        Find an jab element given a role locator.
        """
        if value == self.root_element.role:
            return self.root_element
        else:
            return self.root_element.find_element_by_role(value)

    def find_element_by_states(self, value: str) -> JABElement:
        """
        Find an jab element given a states locator.
        """
        if value == self.root_element.states:
            return self.root_element
        else:
            return self.root_element.find_element_by_states(value)

    def find_element_by_object_depth(self, value: str) -> JABElement:
        """
        Find an jab element given a object depth locator.
        """
        if value == self.root_element.object_depth:
            return self.root_element
        else:
            return self.root_element.find_element_by_object_depth(value)

    def find_element_by_children_count(self, value: str) -> JABElement:
        """
        Find an jab element given a children count locator.
        """
        if value == self.root_element.children_count:
            return self.root_element
        else:
            return self.root_element.find_element_by_children_count(value)

    def find_element_by_index_in_parent(self, value: str) -> JABElement:
        """
        Find an jab element given a index in parent locator.
        """
        if value == self.root_element.index_in_parent:
            return self.root_element
        else:
            return self.root_element.find_element_by_index_in_parent(value)

    def find_element(self, by: str = By.NAME, value: str = None) -> JABElement:
        """
        Find an jab element given a By strategy and locator.
        """
        jab_elements = self.find_elements(by=by, value=value)
        return jab_elements[0]

    def find_elements(self, by: str = By.NAME, value: str = None) -> List[JABElement]:
        """
        Find jab elements given a By strategy and locator.
        """
        dict_by = {
            By.NAME: "//*[@name='{}']".format(value),
            By.ROLE: "//*[@role_en_us='{}']".format(value),
            By.STATES: "//*[@states_en_us='{}']".format(value),
            By.OBJECT_DEPTH: "//*[@object_depth='{}']".format(value),
            By.CHILDREN_COUNT: "//*[@children_count='{}']".format(value),
            By.INDEX_IN_PARENT: "//*[@index_in_parent='{}']".format(value),
            By.XPATH: value,
        }
        # TODO: set func to find specific jab_context
        jab_context = None
        return [JABElement(jab_context)]

    @property
    def source(self) -> dict:
        """
        Get the source tree of current java window
        """
        # TODO: set func to get source tree

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
        # TODO: set func to get_screenshot_as_file

    def get_screenshot(self):
        """
        Gets the screenshot of the current window as a base64 encoded string
           which is useful in embedded images in HTML.

        :Usage:
            driver.get_screenshot_as_base64()
        """
        # TODO: set func to get_screenshot

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