import os
import struct
from ctypes import cdll
from ctypes import CDLL
from pathlib import Path
from typing import Union

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
        """Enable Java Access Bridge.
        This is necessary step before use JAB API.
        """
        with open(A11Y_PROPS_PATH, "wt") as fp:
            try:
                self.logger.debug("Enable Java Access Bridge")
                fp.write(A11Y_PROPS_CONTENT)
            except (OSError, IOError):
                self.logger.error("Enable Java Access Bridge failed")

    def is_bridge_enabled(self) -> bool:
        if not Path(A11Y_PROPS_PATH).is_file():
            return False
        with open(A11Y_PROPS_PATH, "rt") as fp:
            try:
                data = fp.read()
            except (OSError, IOError):
                self.logger.error("Java Access Bridge NOT enabled")
                return False
        is_enabled = data == A11Y_PROPS_CONTENT
        self.logger.debug(f"Is Java Access Bridge enabled => '{is_enabled}'")
        return is_enabled

    def init_bridge(self) -> None:
        self.logger.debug("Initialize Java Access Bridge")
        if not self.is_bridge_enabled():
            self.enable_bridge()

    def load_library(self, dll: Union[Path, str]) -> CDLL:
        self.logger.debug("Load library of Java Access Bridge")
        dll_bit = struct.calcsize("P") * 8
        for path in [
            str(dll),
            JDK_BRIDGE_DLL.format(dll_bit),
            JRE_BRIDGE_DLL.format(dll_bit),
            JAB_BRIDGE_DLL.format(dll_bit),
        ]:
            if os.path.isfile(path):
                return cdll.LoadLibrary(path)
        raise FileNotFoundError(
            "WindowsAccessBridge dll NOT found, "
            "Please correct environment variable for JDK, JRE or JAB, "
            "Anotherwise correct customized WindowsAccessBridge dll path."
        )
