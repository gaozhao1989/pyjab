from __future__ import annotations

import os
import signal
from ctypes import CDLL
from ctypes import c_long
from ctypes.wintypes import HWND
from pathlib import Path
from subprocess import Popen
from time import time
from types import TracebackType
from typing import Any, Dict, Tuple, Optional, Type, Union
from pyjab.common.wait import JABDriverWait
from pyjab.jab.api import API

from PIL import ImageGrab
from pyjab.common.actorscheduler import ActorScheduler
from pyjab.common.by import By
from pyjab.common.exceptions import JABException
from pyjab.common.logger import Logger
from pyjab.common.service import Service
from pyjab.common.win32utils import Win32Utils
from pyjab.jab.type import AccessibleContext
from pyjab.config import TIMEOUT
from pyjab.jabelement import JABElement
from pyjab.jab.cfunc import CFunc


class JABDriver(object):
    """Controls a Java Application by sending commands to JAB APIs.

    Args:
        title (str, optional): Window title of Java application need to bind. 
        JABDriver can be bind with existing Java application. 
        Must to have if `app` invalid. Defaults to None.

        app (Union[Path, str, None]): Path of Java application to launch. 
        JABDriver can help to launch Java application with command `javaws`. 
        Must to have if `title` invalid. Defaults to None.

        dll (Union[Path, str, None]): Path of WindowsAccessBridge dll file.
        File can be found in `JAVA_HOME`, `JRE_HOME` or `JAB_HOME`.
        Need to match the application version. 
        Must to have if NO environment variable for `JAVA_HOME`, `JRE_HOME` or `JAB_HOME`.

        hwnd (HWND, optional): HWND of current Java application window. Defaults to None.
        Must to have if both `vmid` and `accessible_context` invalid.

        vmid (c_long, optional): vmid of current Java application window. Defaults to None.

        accessible_context (JOBJECT64, optional): Root component of AccessibleContext 
        for current Java application window. Defaults to None.

        timeout (Union[int, float]): Timeout seconds for JABDriver global settings.
        Defaults to TIMEOUT.
    """

    def __init__(
            self,
            title: Optional[str] = None,
            app: Union[Path, str, None] = None,
            dll: Union[Path, str, None] = None,
            hwnd: Optional[HWND] = None,
            vmid: Optional[c_long] = None,
            accessible_context: Optional[AccessibleContext] = None,
            timeout: Union[int, float] = TIMEOUT,
    ) -> None:
        self.logger = Logger("pyjab")
        self.win32utils = Win32Utils()
        self.app = app
        self.dll = dll
        self.timeout = timeout
        self.open_app()
        self.latest_log = None
        self._title = title
        self._hwnd = hwnd
        self._vmid = vmid
        self._acc = accessible_context
        self._pid = None
        self._bridge = Service().load_library(self.dll)
        CFunc(self.bridge).fix_funcs()
        self.api = API(self.bridge)
        self._root = None
        self.init_jab()

    def __enter__(self) -> JABDriver:
        return self

    def __exit__(self, exc_type: Type, exc_val: BaseException, exc_tb: TracebackType) -> None:
        if self.pid is None:
            self.logger.debug("Nothing to exit sine pid is None")
            return
        os.kill(self.pid, signal.SIGTERM)

    def open_app(self):
        if self.app is None:
            self.logger.debug("No app set, ignore open app")
            return
        app = str(self.app)
        cmd = " ".join(["javaws", app]
                       ) if app.endswith("jnlp") else app
        Popen(cmd, shell=True).wait()

    @property
    def title(self) -> Union[str, None]:
        return self._title

    @title.setter
    def title(self, title: str) -> None:
        self._title = title

    @property
    def hwnd(self) -> HWND:
        if self._hwnd is None:
            raise ValueError("hwnd is None")
        return self._hwnd

    @hwnd.setter
    def hwnd(self, hwnd: HWND) -> None:
        self._hwnd = hwnd

    @property
    def pid(self) -> Union[int, None]:
        return self._pid

    @pid.setter
    def pid(self, pid: int) -> None:
        self._pid = pid

    @property
    def vmid(self) -> c_long:
        if self._vmid is None:
            raise ValueError("vmid is None")
        return self._vmid

    @vmid.setter
    def vmid(self, vmid: c_long) -> None:
        self._vmid = vmid

    @property
    def accessible_context(self) -> AccessibleContext:
        if self._acc is None:
            raise ValueError("accessible_context is None")
        return self._acc

    @accessible_context.setter
    def accessible_context(self, accessible_context: AccessibleContext) -> None:
        self._acc = accessible_context

    @property
    def bridge(self) -> CDLL:
        return self._bridge

    @bridge.setter
    def bridge(self, bridge: CDLL) -> None:
        self._bridge = bridge

    @property
    def root_element(self) -> JABElement:
        if self._root is None:
            raise ValueError("root_element is None")
        return self._root

    @root_element.setter
    def root_element(self, root_element: JABElement) -> None:
        self._root = root_element

    def _run_actor_sched(self) -> None:
        # invoke generator in message queue
        sched = ActorScheduler()
        sched.new_actor("pyjab", self.win32utils.setup_msg_pump())
        sched.run_actor()

    def init_jab(self) -> None:
        self.logger.info("Initialize pyjab")
        # Starts Java Access Bridge. You cannot use any part of the Java Access Bridge API until you call this function.
        self.bridge.Windows_run()
        # Setup message queue for actor scheduler
        self._run_actor_sched()
        # Get HWND by Java applicaiton window title
        if self.title:
            self.hwnd = self.hwnd or self.wait_java_window_by_title(
                self.title, self.timeout
            )
        # Get vmid and AccessibleContext by HWND
        if self.hwnd:
            self.accessible_context, self.vmid = self.api.get_accessible_context_from_hwnd(
                self.hwnd)
        # Get HWND by vmid and AccessibleContext
        elif self.vmid and self.accessible_context:
            self.hwnd = self.api.get_hwnd_from_accessible_context(
                self.vmid, self.api.get_top_level_object(
                    self.vmid, self.accessible_context
                )
            )
        # HWND, vmid and AccessibleContext are requried for pyjab
        if not all([self.hwnd, self.vmid, self.accessible_context]):
            raise RuntimeError(
                "hwnd, vmid and AccessibleContext are required, please check"
                f"hwnd => {self.hwnd}"
                f"vmid => {self.vmid}"
                f"AccessibleContext => {self.accessible_context}"
            )
        self.pid = self.win32utils.get_pid_from_hwnd(self.hwnd)
        self.root_element = JABElement(
            self.bridge,
            self.hwnd,
            self.vmid,
            self.accessible_context,
        )
        self.logger.info("Initialize pyjab success")

    def maximize_window(self):
        """
        Maximizes the current java window that jabdriver is using
        """
        self.win32utils.set_window_maximize(self.hwnd)

    def minimize_window(self):
        """
        Invokes the window manager-specific 'minimize' operation
        """
        self.win32utils.set_window_minimize(self.hwnd)
        
    def get_java_window_hwnd(self, title: str) -> Optional[HWND]:
        """Get Java Window hwnd by title.

        Args:
            title (str): Java window title

        Returns:
            Optional[HWND]: HWND if found Java Window, otherwise return None
        """
        for hwnd in self.win32utils.get_hwnds_by_title(title):
            if self.api.is_java_window(hwnd):
                return hwnd

    def switch_to(self):
        # TODO:
        pass

    def wait_java_window_by_title(self, title: Union[str, None], timeout: Union[int, float] = TIMEOUT) -> HWND:
        """Wait until a Java Window exists in specific seconds.

        Args:
            title (Union[str, None]): The title of specific Java Window need to wait.

            timeout (Union[int, float], optional): The timeout seconds. Defaults to TIMEOUT.

        Raises:
            TimeoutError: Timeout error occurs when wait time over the specific timeout

        Returns:
            HWND of Java window found in specific seconds.
        """
        return JABDriverWait(timeout).until(self.get_java_window_hwnd, title)

    def find_element_by_name(self, value: str, visible: bool = False) -> JABElement:
        """
        Find an JABElement given a name locator.
        """
        if value == self.root_element.name:
            return self.root_element
        else:
            return self.root_element.find_element_by_name(value=value, visible=visible)

    def find_element_by_description(self, value: str, visible: bool = False) -> JABElement:
        """
        Find an JABElement given a description locator.
        """
        if value == self.root_element.description:
            return self.root_element
        else:
            return self.root_element.find_element_by_description(value=value, visible=visible)

    def find_element_by_role(self, value: str, visible: bool = False) -> JABElement:
        """
        Find an JABElement given a role locator.
        """
        if value == self.root_element.role:
            return self.root_element
        else:
            return self.root_element.find_element_by_role(value=value, visible=visible)

    def find_element_by_states(self, value: str, visible: bool = False) -> JABElement:
        """
        Find an JABElement given a state locator.
        """
        if value == self.root_element.states:
            return self.root_element
        else:
            return self.root_element.find_element_by_states(
                value=value, visible=visible
            )

    def find_element_by_object_depth(
            self, value: int, visible: bool = False
    ) -> JABElement:
        """
        Find an JABElement given an object depth locator.
        """
        if value == self.root_element.object_depth:
            return self.root_element
        else:
            return self.root_element.find_element_by_object_depth(
                value=value, visible=visible
            )

    def find_element_by_children_count(
            self, value: int, visible: bool = False
    ) -> JABElement:
        """
        Find an JABElement given a children count locator.
        """
        if value == self.root_element.children_count:
            return self.root_element
        else:
            return self.root_element.find_element_by_children_count(
                value=value, visible=visible
            )

    def find_element_by_index_in_parent(
            self, value: int, visible: bool = False
    ) -> JABElement:
        """
        Find an JABElement given an index in parent locator.
        """
        if value == self.root_element.index_in_parent:
            return self.root_element
        else:
            return self.root_element.find_element_by_index_in_parent(
                value=value, visible=visible
            )

    def find_element_by_xpath(self, value: str, visible: bool = False) -> JABElement:
        """
        Find an JABElement given an index in parent locator.
        """
        return self.root_element.find_element_by_xpath(value=value, visible=visible)

    def find_element(
            self, by: str = By.NAME, value: Any = None, visible: bool = False
    ) -> JABElement:
        """
        Find an JABElement given a By strategy and locator.
        """
        dict_find = {
            By.NAME: self.find_element_by_name,
            By.DESCRIPTION: self.find_element_by_description,
            By.ROLE: self.find_element_by_role,
            By.STATES: self.find_element_by_states,
            By.OBJECT_DEPTH: self.find_element_by_object_depth,
            By.CHILDREN_COUNT: self.find_element_by_children_count,
            By.INDEX_IN_PARENT: self.find_element_by_index_in_parent,
            By.XPATH: self.find_element_by_xpath,
        }
        if by not in dict_find.keys():
            raise JABException(f"incorrect by strategy '{by}'")
        return dict_find[by](value=value, visible=visible)

    def find_elements_by_name(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given a name locator.
        """
        jabelements = []
        if value == self.root_element.name:
            jabelements.append(self.root_element)
        jabelements.extend(
            self.root_element.find_elements_by_name(
                value=value, visible=visible)
        )
        return jabelements

    def find_elements_by_description(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given a description locator.
        """
        jabelements = []
        if value == self.root_element.description:
            jabelements.append(self.root_element)
        jabelements.extend(
            self.root_element.find_elements_by_description(
                value=value, visible=visible)
        )
        return jabelements

    def find_elements_by_role(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given a role locator.
        """
        jabelements = []
        if value == self.root_element.role:
            jabelements.append(self.root_element)
        jabelements.extend(
            self.root_element.find_elements_by_role(
                value=value, visible=visible)
        )
        return jabelements

    def find_elements_by_states(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given a state locator.
        """
        jabelements = []
        if value == self.root_element.states:
            jabelements.append(self.root_element)
        jabelements.extend(
            self.root_element.find_elements_by_states(
                value=value, visible=visible)
        )
        return jabelements

    def find_elements_by_object_depth(
            self, value: int, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given an object depth locator.
        """
        jabelements = []
        if value == self.root_element.object_depth:
            jabelements.append(self.root_element)
        jabelements.extend(
            self.root_element.find_elements_by_object_depth(
                value=value, visible=visible
            )
        )
        return jabelements

    def find_elements_by_children_count(
            self, value: int, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given a children count locator.
        """
        jabelements = []
        if value == self.root_element.children_count:
            jabelements.append(self.root_element)
        jabelements.extend(
            self.root_element.find_elements_by_children_count(
                value=value, visible=visible
            )
        )
        return jabelements

    def find_elements_by_index_in_parent(
            self, value: int, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given an index in parent locator.
        """
        jabelements = []
        if value == self.root_element.index_in_parent:
            jabelements.append(self.root_element)
        jabelements.extend(
            self.root_element.find_elements_by_index_in_parent(
                value=value, visible=visible
            )
        )
        return jabelements

    def find_elements_by_xpath(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given an index in parent locator.
        """
        return self.root_element.find_elements_by_xpath(value=value, visible=visible)

    def find_elements(
            self, by: str = By.NAME, value: str = None, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given a By strategy and locator.
        """
        dict_finds = {
            By.NAME: self.find_elements_by_name,
            By.DESCRIPTION: self.find_elements_by_description,
            By.ROLE: self.find_elements_by_role,
            By.STATES: self.find_elements_by_states,
            By.OBJECT_DEPTH: self.find_elements_by_object_depth,
            By.CHILDREN_COUNT: self.find_elements_by_children_count,
            By.INDEX_IN_PARENT: self.find_elements_by_index_in_parent,
            By.XPATH: self.find_elements_by_xpath,
        }
        if by not in dict_finds.keys():
            raise JABException(f"incorrect by strategy '{by}'")
        return dict_finds[by](value=value, visible=visible)

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
                return self.find_element(by=by, value=value)
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
        self.win32utils.set_window_foreground(hwnd=self.root_element.hwnd)
        bounds = self.root_element.bounds
        x = bounds.get("x")
        y = bounds.get("y")
        width = bounds.get("width")
        height = bounds.get("height")
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

    def set_window_size(self, width, height):
        """
        Sets the width and height of the current window. (window.resizeTo)

        :Args:
         - width: the width in pixels to set the window to
         - height: the height in pixels to set the window to

        :Usage:
            driver.set_window_size(800,600)
        """
        self.win32utils.set_window_size(
            hwnd=self.root_element.hwnd, width=width, height=height
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
        self.win32utils.set_window_position(
            hwnd=self.root_element.hwnd, left=x, top=y
        )

    def get_window_position(self):
        """
        Gets the x,y position of the current window.

        :Usage:
            driver.get_window_position()
        """
        return self.win32utils.get_window_position(hwnd=self.root_element.hwnd)
