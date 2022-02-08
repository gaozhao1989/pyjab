import os
import struct
from ctypes import cdll
from ctypes import CDLL
from pathlib import Path

from pyjab.common.logger import Logger
from pyjab.common.singleton import singleton
from pyjab.config import A11Y_PROPS_CONTENT
from pyjab.config import A11Y_PROPS_PATH
from pyjab.config import JAB_BRIDGE_DLL
from pyjab.config import JDK_BRIDGE_DLL
from pyjab.config import JRE_BRIDGE_DLL


@singleton
class Service(object):
    def __init__(self) -> None:
        self.logger = Logger("pyjab")
        self.init_bridge()

    def enable_bridge(self) -> None:
        with open(A11Y_PROPS_PATH, "wt") as fp:
            try:
                self.logger.debug("enable bridge")
                fp.write(A11Y_PROPS_CONTENT)
            except (OSError, IOError):
                self.logger.error("enable bridge failed")

    def is_bridge_enabled(self) -> bool:
        if not Path(A11Y_PROPS_PATH).is_file():
            return False
        with open(A11Y_PROPS_PATH, "rt") as fp:
            try:
                data = fp.read()
            except (OSError, IOError):
                self.logger.error("bridge is not enabled")
                return False
        is_enabled = data == A11Y_PROPS_CONTENT
        self.logger.debug("is bridge enabled => '{}'".format(is_enabled))
        return is_enabled

    def init_bridge(self) -> None:
        self.logger.debug("init bridge")
        if not self.is_bridge_enabled():
            self.enable_bridge()

    def load_library(self, bridge_dll: str = "") -> CDLL:
        self.logger.debug("load library of bridge")
        dll_bit = struct.calcsize("P") * 8
        for dll in [
            str(bridge_dll),
            JDK_BRIDGE_DLL.format(dll_bit),
            JRE_BRIDGE_DLL.format(dll_bit),
            JAB_BRIDGE_DLL.format(dll_bit),
        ]:
            if os.path.isfile(dll):
                return cdll.LoadLibrary(dll)
        raise FileNotFoundError(
            "WindowsAccessBridge dll not found, "
            "please set correct path for environment variable, "
            "or check the passed customized WindowsAccessBridge dll."
        )
