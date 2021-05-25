import time
from ctypes import cdll
from ctypes import CDLL
from ctypes.wintypes import HWND

from pyjab.common.logger import Logger
from pyjab.common.win32utils import Win32Utils
from pyjab.config import A11Y_PROPS_CONTENT, A11Y_PROPS_PATH, BRIDGE_DLL, TIMEOUT


class Service(Win32Utils):
    def __init__(self) -> None:
        super(Service, self).__init__()
        self.logger = Logger(self.__class__.__name__)
        self.init_bridge()
        self.service_bridge = self.load_library()
        self.check_is_running()

    def enable_bridge(self) -> None:
        with open(A11Y_PROPS_PATH, "wt") as fp:
            try:
                self.logger.debug("enable bridge")
                fp.write(A11Y_PROPS_CONTENT)
            except (OSError, IOError):
                self.logger.error("enable bridge is failed")

    def is_bridge_enable(self) -> bool:
        with open(A11Y_PROPS_PATH, "rt") as fp:
            try:
                data = fp.read()
            except (OSError, IOError):
                self.logger.error("bridge is not enable")
                return False
        is_enable = data == A11Y_PROPS_CONTENT
        self.logger.debug("is bridge enable => '{}'".format(is_enable))
        return is_enable

    def init_bridge(self) -> None:
        self.logger.debug("init bridge")
        if not self.is_bridge_enable():
            self.enable_bridge()

    def load_library(self) -> CDLL:
        self.logger.debug("load library of bridge")
        return cdll.LoadLibrary(BRIDGE_DLL)

    def check_is_running(self) -> None:
        is_running = bool(self.service_bridge.Windows_run())
        self.logger.debug("jab is running => '{}'".format(is_running))
        if not is_running:
            raise RuntimeError("oracle form services start failed")

    def is_java_window_present(self, hwnd: HWND = None) -> bool:
        return bool(self.service_bridge.isJavaWindow(hwnd))

    def wait_java_window_present(
        self, hwnd: HWND = None, timeout: int = TIMEOUT
    ) -> HWND:
        start = time.time()
        while True:
            if self.is_java_window_present(hwnd):
                return hwnd
            current = time.time()
            elapsed = round(current - start)
            if elapsed >= timeout:
                raise TimeoutError(
                    "no java window found by hwnd '{}' in '{}'seconds".format(
                        hwnd, timeout
                    )
                )
            time.sleep(0.1)