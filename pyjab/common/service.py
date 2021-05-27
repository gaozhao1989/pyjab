import os
from ctypes import cdll
from ctypes import CDLL

from pyjab.common.logger import Logger
from pyjab.common.win32utils import Win32Utils
from pyjab.config import A11Y_PROPS_CONTENT
from pyjab.config import A11Y_PROPS_PATH
from pyjab.config import JDK_BRIDGE_DLL
from pyjab.config import JAB_BRIDGE_DLL


class Service(Win32Utils):
    def __init__(self) -> None:
        super(Service, self).__init__()
        self.logger = Logger(self.__class__.__name__)
        self.init_bridge()

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
        if os.path.isfile(JDK_BRIDGE_DLL):
            BRIDGE_DLL = JDK_BRIDGE_DLL
        elif os.path.isfile(JAB_BRIDGE_DLL):
            BRIDGE_DLL = JAB_BRIDGE_DLL
        else:
            raise FileNotFoundError(
                "WindowsAccessBridge-32.dll not found, please set correct path for 'JAVA_HOME' or 'JAB_HOME'"
            )
        return cdll.LoadLibrary(BRIDGE_DLL)
