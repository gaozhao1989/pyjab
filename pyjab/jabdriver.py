from __future__ import annotations

import sys

# pyjab ships as a pure-python wheel, so pip installs it on Linux and macOS too.
# There it used to fail later with a bare
# "ModuleNotFoundError: No module named 'win32process'".  Fail early, before any
# pywin32 import, with something actionable.
if sys.platform != "win32":  # pragma: no cover - platform dependent
    raise ImportError(
        "pyjab drives the Windows Java Access Bridge and only runs on Windows.\n"
        "  detected platform: {!r}\n"
        "The package installs on every platform, but it can only run on "
        "Windows with a JDK installed.".format(sys.platform)
    )

import base64
import os
import signal
from ctypes import byref
from ctypes import CDLL
from ctypes import c_long
from ctypes.wintypes import HWND
from io import BytesIO
from pathlib import Path
from subprocess import Popen
from time import sleep, time
from typing import Any, Dict, Tuple, Optional

import win32process
from PIL import ImageGrab
from pyjab.accessibleinfo import AccessBridgeVersionInfo
from pyjab.common.by import By
from pyjab.common.exceptions import JABException
from pyjab.common.logger import Logger
from pyjab.common.service import Service
from pyjab.common.win32utils import Win32Utils
from pyjab.common.types import JOBJECT64
from pyjab.config import ELEMENT_POLL_INTERVAL
from pyjab.config import TIMEOUT
from pyjab.config import WINDOW_POLL_INTERVAL
from pyjab.jabelement import JABElement
from pyjab.jabfixedfunc import JABFixedFunc


class JABDriver(object):
    """Controls a Java application by Java Access Bridge.

    Args:
        Service ([type]): Host system to initialize the JAB and load JAB dll file.
    """

    def __init__(
            self,
            title: str = "",
            file_path: Path = None,
            bridge_dll: str = "",
            hwnd: HWND = None,
            vmid: c_long = None,
            accessible_context: JOBJECT64 = None,
            timeout: int = TIMEOUT,
    ) -> None:
        """Create a new jab driver.

        Args:
            title (str, optional): Window title of Java application need to bind. Defaults to "".
            file_path (Path, optional): File path of the application to launch. Defaults to None.
            bridge_dll (str, optional): WindowsAccessBridge dll file path. Defaults to "".
            hwnd (HWND, optional): HWND of Java Window. Defaults to None.
            vmid (c_long, optional): vmid of Java Window. Defaults to None.
            accessible_context (JOBJECT64, optional): Any Accessible Context Component in Java Window.
            Defaults to None.
            timeout (int, optional): Default timeout set for JABDriver waiting. Defaults to TIMEOUT.
        """
        super(JABDriver, self).__init__()
        self.win32utils = Win32Utils()
        self.file_path = file_path
        self._title = title
        if self.file_path:
            self.open_application()
        self.serv = Service()
        self.logger = Logger("pyjab")
        self.latest_log = None
        self._bridge_dll = bridge_dll
        self._timeout = timeout
        self._hwnd = hwnd
        self._vmid = vmid
        self._pid = None
        self._accessible_context = accessible_context
        self._bridge = None
        self._root_element = None
        self.init_jab()
        JABFixedFunc(self.bridge)._fix_bridge_functions()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # self.pid stays None if init_jab() raised before it resolved the window
        # handle -- for instance when the window never appeared, which is the
        # most common failure. os.kill(None, ...) then raised TypeError and
        # replaced the real exception with a misleading one.
        if self.pid is None:
            return
        os.kill(self.pid, signal.SIGTERM)

    def open_application(self):
        """Launch the application named by ``file_path``, without waiting for it.

        A ``.jnlp`` is started through ``javaws``; anything else is executed
        directly.

        Note:
            This used to call ``p.wait()``, which blocks until the launched
            process exits.  That defeats the purpose: ``JABDriver`` needs to bind
            to the application's window, and the window only exists while the
            application is running.  Waiting meant the bind could never succeed,
            and for a ``javaws`` launch it could block for as long as the user
            kept the application open.
        """
        # NOTE: Path.suffix includes the leading dot, so this comparison used to
        # be `== "jnlp"` and never matched -- the javaws branch was dead code and
        # .jnlp files were executed directly instead of via Java Web Start.
        #
        # An argv list, not a shell string: `" ".join(...)` with shell=True sent
        # the path through cmd.exe, which splits on spaces, so a path such as
        # "C:\Program Files\Java\...\javacpl.exe" was not launched at all. A list
        # also means an '&' or '^' in a filename is just a character.
        argv = (["javaws", str(self.file_path)]
                if self.file_path.suffix == ".jnlp"
                else [str(self.file_path)])
        return Popen(argv)

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
    def pid(self) -> int:
        return self._pid

    @pid.setter
    def pid(self, pid: int) -> None:
        self._pid = pid

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

    def _pump_messages(self) -> None:
        """Service pending Windows/COM messages on this thread.

        Cheap and non-blocking. See :meth:`Win32Utils.pump_messages` for why
        this is required and why it must happen on the JAB-owning thread.
        """
        self.win32utils.pump_messages()

    def init_jab(self) -> None:
        # enum window and find hwnd
        self.logger.info("init jab")
        # load AccessBridge dll file
        self.bridge = self.serv.load_library(self._bridge_dll)
        self.bridge.Windows_run()
        # Service the message queue once Windows_run() has armed the bridge:
        # accessibility events are delivered through COM on this thread.
        self._pump_messages()
        # wait java window by title and get hwnd if not specific hwnd and vmid
        if not (self.hwnd or (self.vmid and self.accessible_context)):
            self.hwnd = self.wait_java_window_by_title(
                title=self.title, timeout=self._timeout
            )
        # get vmid and accessible_context by hwnd
        if self.hwnd:
            self.accessible_context, self.vmid = self._get_accessible_context_from_hwnd(
                self.hwnd
            )
        # get hwnd by vmid and accessible_context
        elif self.vmid and self.accessible_context:
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
        # check if Java Window HWND valid
        if not self._is_java_window(self.hwnd):
            raise RuntimeError(f"HWND:{self.hwnd} is not Java Window, please check!")
        self.pid = self.get_pid_from_hwnd()
        self.root_element = JABElement(
            bridge=self.bridge,
            hwnd=self.hwnd,
            vmid=self.vmid,
            accessible_context=self.accessible_context,
        )
        self.logger.info("init jab success")

    # Gateway functions
    def _is_java_window(self, hwnd: HWND) -> bool:
        """Return the specific window is or not a Java Window

        Args:
            hwnd (HWND): The hwnd of window.

        Returns:
            bool: True if is a Java Window. False is not a Java Window.
        """
        return bool(self.bridge.isJavaWindow(hwnd))

    def _get_accessible_context_from_hwnd(self, hwnd: HWND) -> Tuple[JOBJECT64, int]:
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
        return accessible_context, vmid.value

    def get_pid_from_hwnd(self):
        _, pid = win32process.GetWindowThreadProcessId(self.hwnd)
        return pid

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

    def get_java_window_hwnd(self, title: str) -> Optional[HWND]:
        """Get Java Window hwnd by title.

        Args:
            title (str): Java window title

        Returns:
            Optional[HWND]: HWND if found Java Window, otherwise return None
        """
        for hwnd in self.win32utils.get_hwnds_by_title(title=title):
            if self._is_java_window(hwnd):
                return hwnd

    def wait_java_window_by_title(self, title: str, timeout: int = TIMEOUT) -> HWND:
        """Wait until a Java Window exists in specific seconds.

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
            # Pump first: a window that opens asynchronously is announced
            # through a COM event on this thread, so the queue has to be
            # serviced before enumeration can see it.
            self._pump_messages()
            if hwnd := self.get_java_window_hwnd(title=title):
                return hwnd
            log_out = f"no java window found by title '{title}'"
            if self.latest_log != log_out:
                self.logger.debug(log_out)
                self.latest_log = log_out
            current = time()
            elapsed = round(current - start)
            if elapsed >= timeout:
                raise TimeoutError(
                    f"no java window found by title '{title}' in '{timeout}'seconds"
                )
            # Do not spin: the previous implementation called a 200ms blocking
            # pump here, then re-enumerated. Sleep briefly instead so the poll
            # interval is explicit and the pump stays non-blocking.
            sleep(WINDOW_POLL_INTERVAL)

    # jab driver functions: similar with webdriver
    def find_element_by_name(self, value: str, visible: bool = False) -> JABElement:
        """
        Find an JABElement given a name locator.
        """
        return self.root_element.find_element_by_name(value=value, visible=visible)

    def find_element_by_description(self, value: str, visible: bool = False) -> JABElement:
        """
        Find an JABElement given a description locator.
        """
        return self.root_element.find_element_by_description(value=value, visible=visible)

    def find_element_by_role(self, value: str, visible: bool = False) -> JABElement:
        """
        Find an JABElement given a role locator.
        """
        return self.root_element.find_element_by_role(value=value, visible=visible)

    def find_element_by_states(self, value: str, visible: bool = False) -> JABElement:
        """
        Find an JABElement given a state locator.
        """
        return self.root_element.find_element_by_states(value=value, visible=visible)

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
        return self.root_element.find_elements_by_name(value=value, visible=visible)

    def find_elements_by_description(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given a description locator.
        """
        return self.root_element.find_elements_by_description(value=value, visible=visible)

    def find_elements_by_role(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given a role locator.
        """
        return self.root_element.find_elements_by_role(value=value, visible=visible)

    def find_elements_by_states(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """
        Find list of JABElement given a state locator.
        """
        return self.root_element.find_elements_by_states(value=value, visible=visible)

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

    def maximize_window(self):
        """
        Maximizes the current java window that jabdriver is using
        """
        self.win32utils._set_window_maximize(hwnd=self.root_element.hwnd)

    def minimize_window(self):
        """
        Invokes the window manager-specific 'minimize' operation
        """
        self.win32utils._set_window_minimize(hwnd=self.root_element.hwnd)

    def wait_until_element_exist(
            self,
            by: str = By.NAME,
            value: Any = None,
            timeout: int = TIMEOUT,
            poll_interval: float = ELEMENT_POLL_INTERVAL,
    ) -> JABElement:
        """Wait until an element matching the locator exists, and return it.

        Args:
            by: Locator strategy, see :class:`~pyjab.common.by.By`.
            value: Locator value.
            timeout: Give up after this many seconds. Defaults to ``TIMEOUT``.
            poll_interval: Seconds to sleep between attempts. Defaults to
                ``ELEMENT_POLL_INTERVAL``.

        Raises:
            JABException: The element was not found within ``timeout`` seconds.

        Note:
            The message queue is pumped on every iteration. Previously this
            method was a tight loop with no sleep at all, which both burned CPU
            re-walking the accessibility tree (issue #29) and never serviced
            COM, so a dialog that opened while waiting was invisible to pyjab.
        """
        start = time()
        while True:
            self._pump_messages()
            try:
                return self.find_element(by=by, value=value)
            except JABException:
                log_out = f"JABElement with locator '{by}' '{value}' does not found"
                if self.latest_log != log_out:
                    self.logger.warning(log_out)
                    self.latest_log = log_out

            elapsed = time() - start
            if elapsed >= timeout:
                raise JABException(
                    f"JABElement with locator '{by}' '{value}' does not found in {timeout} seconds"
                )
            self.logger.debug(f"elapsed => {elapsed:.1f}, remain => {timeout - elapsed:.1f}")
            sleep(poll_interval)

    def get_screenshot_as_file(self, filename):
        """Write a PNG of the bound window to ``filename``.

        Args:
            filename (str): where to write it, as a full path.  A relative path
                is relative to the working directory.

        Returns:
            None.  Pillow raises if the file cannot be written; there is no
            True/False to check.

        Use :meth:`get_screenshot` instead if you want the image rather than a
        file.
        """
        im = self.get_screenshot()
        im.save(filename)

    def get_screenshot(self):
        """The screenshot of the current window, as a Pillow ``Image``.

        Selenium's method of this name returns base64; this one returns the image
        itself, and :meth:`get_screenshot_as_file` is the one that writes a file.
        The docstring said base64 and its example called a
        ``get_screenshot_as_base64()`` that has never existed in pyjab.

        :Usage:
            image = driver.get_screenshot()
        """
        self.win32utils._set_window_foreground(hwnd=self.root_element.hwnd)
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
        """Resize the bound window, in pixels.

        Args:
            width (int): the new width.
            height (int): the new height.

        This moves and resizes a real window on the desktop.  It is not the same
        as setting a preferred size inside the application, and the application
        may lay itself out differently afterwards.
        """
        self.win32utils._set_window_size(
            hwnd=self.root_element.hwnd, width=width, height=height
        )

    def set_window_position(self, x, y):
        """Move the bound window to a screen position, in pixels.

        Args:
            x (int): the new left edge, in screen coordinates.
            y (int): the new top edge, in screen coordinates.

        The position is the window's top-left corner, including its decorations,
        not the client area inside them.
        """
        self.win32utils._set_window_position(
            hwnd=self.root_element.hwnd, left=x, top=y
        )

    def get_window_position(self):
        """Where the bound window is on screen, as ``(x, y)`` in pixels.

        The top-left corner of the window including its decorations, which is the
        same point :meth:`set_window_position` takes.
        """
        return self.win32utils._get_window_position(hwnd=self.root_element.hwnd)

    def get_screenshot_as_png(self) -> bytes:
        """The screenshot as PNG data, the way Selenium returns it.

        This is what :meth:`get_screenshot_as_base64` encodes, and what
        :meth:`get_screenshot_as_file` writes.  Use :meth:`get_screenshot` when
        you want the Pillow ``Image`` itself.

        Returns:
            bytes: a complete PNG file, magic number and all.
        """
        buffer = BytesIO()
        self.get_screenshot().save(buffer, format="PNG")
        return buffer.getvalue()

    def get_screenshot_as_base64(self) -> str:
        """The screenshot as a base64-encoded PNG, for embedding in HTML or JSON.

        Returns:
            str: the same bytes :meth:`get_screenshot_as_png` returns, base64
            encoded as ASCII.
        """
        return base64.b64encode(self.get_screenshot_as_png()).decode("ascii")

    def get_window_size(self):
        """The bound window's size in pixels, as ``(width, height)``.

        Includes the window decorations, so it is the rectangle
        :meth:`set_window_size` takes and :meth:`get_window_position` reports the
        corner of.

        A tuple rather than the dict Selenium returns for the same name, to match
        :meth:`get_window_position`, which is also a tuple.
        """
        return self.win32utils._get_window_size(hwnd=self.root_element.hwnd)

    def get_focused_element(self) -> Optional[JABElement]:
        """The element that currently has keyboard focus in this window.

        Returns:
            Optional[JABElement]: the focused element, or ``None`` when the
            window reports nothing focused -- which is what an unfocused window,
            or one with nothing focusable in it, does.
        """
        focused = self._focused_context()
        if focused is None:
            return None

        vmid, accessible_context = focused
        return JABElement(
            bridge=self.bridge,
            hwnd=self.hwnd,
            vmid=vmid,
            accessible_context=accessible_context,
        )

    def _focused_context(self) -> Optional[Tuple[int, JOBJECT64]]:
        """Ask the bridge which component has focus, or ``None`` if none has.

        Its own step because the answer arrives as two out-parameters and a
        status flag, and the flag carries the meaning: a window with nothing
        focused is the ordinary case, not a failure.

        Returns:
            Optional[Tuple[int, JOBJECT64]]: the VM id and the context handle, or
            ``None``.  The VM id is a plain ``int``, which is how every other
            path in pyjab carries it -- ``_get_accessible_context_from_hwnd``
            takes ``.value`` off the ctypes scalar for the same reason.
        """
        vmid = c_long()
        accessible_context = JOBJECT64()

        found = self.bridge.getAccessibleContextWithFocus(
            self.hwnd, byref(vmid), byref(accessible_context)
        )
        if not found or not accessible_context.value:
            return None

        return vmid.value, accessible_context
