from __future__ import annotations
from ctypes import byref
from ctypes import CDLL
from ctypes import c_long
from ctypes.wintypes import HWND
from time import time, sleep
from typing import Any, Dict, Tuple, Union
from PIL import ImageGrab
from pyjab.accessibleinfo import AccessBridgeVersionInfo
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
    """Controls a Java application by Java Access Bridge.

    Args:
        Service ([type]): Host system to initialize the JAB and load JAB dll file.
        ActorScheduler ([type]): Set message pump to interacte with windows system.
    """

    def __init__(
        self,
        title: str = "",
        bridge_dll: str = "",
        hwnd: HWND = None,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
        timeout: int = TIMEOUT,
    ) -> None:
        """Create a new jab driver.

        Args:
            title (str, optional): Window title of Java appliction need to bind. Defaults to "".
            bridge_dll (str, optional): WindowsAccessBridge dll file path. Defaults to "".
            hwnd (HWND, optional): HWND of Java Window. Defaults to None.
            vmid (c_long, optional): vmid of Java Window. Defaults to None.
            accessible_context (JOBJECT64, optional): Any Accessible Context Component in Java Window.
            Defaults to None.
            timeout (int, optional): Default timeout set for JABDriver waitting. Defaults to TIMEOUT.
        """
        super(JABDriver, self).__init__()
        self.logger = Logger(self.__class__.__name__)
        self.latest_log = None
        self._bridge_dll = bridge_dll
        self._timeout = timeout
        self._title = title
        self._hwnd = hwnd
        self._vmid = vmid
        self._accessible_context = accessible_context
        self._bridge = None
        self._root_element = None
        self.init_jab()
        JABFixedFunc(self._bridge)._fix_bridge_functions()
        self.xpath_parser = XpathParser()

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, title: str) -> None:
        self._title = title

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

    def init_jab(self) -> None:
        # enum window and find hwnd
        if not (self.hwnd or (self.vmid and self.accessible_context)):
            self.hwnd = self.wait_hwnd_by_title(title=self.title, timeout=self._timeout)
        # load AccessBridge dll file
        self.bridge = self.load_library(self._bridge_dll)
        self.bridge.Windows_run()
        # invoke generator in message queue
        sched = ActorScheduler()
        sched.new_actor("jab", self.setup_msg_pump())
        sched.run()
        # check if Java Window HWND valid
        if not self._is_java_window(self.hwnd):
            raise RuntimeError("HWND is not Java Window, please check!")
        # get vmid and accessible_context by hwnd
        if self.hwnd and not self.vmid:
            self.accessible_context, self.vmid = self._get_accessible_context_from_hwnd(
                self.hwnd
            )
        # get hwnd by vmid and accessible_context
        elif self.vmid and self.accessible_context and not self.hwnd:
            # must have vmid and accessible_context
            top_level_object = self.bridge.getTopLevelObject(
                self.vmid, self.accessible_context
            )
            self.hwnd = self.bridge.getHWNDFromAccessibleContext(
                self.vmid, top_level_object
            )
        else:
            raise RuntimeError(
                "At least hwnd or vmid and accessible_context is required"
            )
        self.root_element = JABElement(
            bridge=self.bridge,
            hwnd=HWND(self.hwnd),
            vmid=c_long(self.vmid),
            accessible_context=self.accessible_context,
        )
        # TODO:fix JABElement not loading complete
        sleep(2)

    # Gateway funcitons
    def _is_java_window(self, hwnd: HWND) -> bool:
        """Return the specific window is or not a Java Window

        Args:
            hwnd (HWND): The hwnd of window.

        Returns:
            bool: True if is a Java Window. False is not a Java Window.
        """
        return bool(self.bridge.isJavaWindow(hwnd))

    def _get_accessible_context_from_hwnd(self, hwnd: HWND) -> Tuple[JOBJECT64, c_long]:
        """Gets the AccessibleContext and vmID values for the given window.

        Args:
            hwnd (HWND): hwnd (HWND): The hwnd of window.

        Returns:
            Tuple: tuple of AccessibleContext and vmID
        """
        vmid = c_long()
        accessible_context = JOBJECT64()
        self.bridge.getAccessibleContextFromHWND(
            hwnd, byref(vmid), byref(accessible_context)
        )
        vmid = vmid.value
        return (accessible_context, vmid)

    def get_version_info(self) -> Dict[str, str]:
        """Gets the version information of the instance of Java Access Bridge instance your application is using.

        Returns:
            Dict[str]: Dict of AccessBridgeVersionInfo, contains:
                VMVersion
                bridgeJavaClassVersion
                bridgeJavaDLLVersion
                bridgeWinDLLVersion
        """
        info = AccessBridgeVersionInfo()
        self.bridge.getVersionInfo(self.vmid, byref(info))
        return {
            "VMVersion": info.VMVersion,
            "bridgeJavaClassVersion": info.bridgeJavaClassVersion,
            "bridgeJavaDLLVersion": info.bridgeJavaDLLVersion,
            "bridgeWinDLLVersion": info.bridgeWinDLLVersion,
        }

    def get_java_window_hwnd(self, title: str) -> Union[HWND, None]:
        """Get Java Window hwnd by title.

        Args:
            title (str): Java window title

        Returns:
            Union[HWND, None]: HWND if found Java Window, otherwise return None
        """
        for hwnd in self.get_hwnds_by_title(title=title):
            if self._is_java_window(hwnd):
                return hwnd

    def wait_java_window_by_title(self, title: str, timeout: int = TIMEOUT) -> HWND:
        """Wait until a Java Window exist in specific seconds.

        Args:
            title (str): The title of specific Java Window need to wait.
            timeout (int, optional): The timeout seconds. Defaults to TIMEOUT.

        Raises:
            TimeoutError: Timeout error occurs when wait time over the specific timeout

        Returns:
            HWND of Java window found in specific seconds.
        """
        start = time()
        while True:
            hwnd = self.get_java_window_hwnd(title=title)
            if hwnd:
                return hwnd
            log_out = f"no java window found by title '{title}'"
            if self.latest_log != log_out:
                self.logger.warning(log_out)
                self.latest_log = log_out
            current = time()
            elapsed = round(current - start)
            if elapsed >= timeout:
                raise TimeoutError(
                    f"no java window found by title '{title}' in '{timeout}'seconds"
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
            self.logger.debug(f"elapsed => {elapsed}, remain => {remain}")
            if elapsed >= timeout:
                raise JABException(
                    f"JABElement with locator '{by}' '{value}' does not found in {timeout} seconds"
                )
            try:
                jabelement = self.find_element(by=by, value=value)
                return jabelement
            except JABException:
                log_out = f"JABElement with locator '{by}' '{value}' does not found"
                if self.latest_log != log_out:
                    self.logger.warning(log_out)
                    self.latest_log = log_out

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
        self._set_window_size(
            hwnd=self.root_element.hwnd.value, width=width, height=height
        )

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
