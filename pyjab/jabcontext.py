from ctypes import byref, c_int, c_int64, c_long
from ctypes.wintypes import HWND
from pyjab.globalargs import BRIDGE
from typing import TypeVar
from pyjab.common.logger import Logger

accessible_context = TypeVar("accessible_context", bound="JABContext")


class JABContext(c_int64):
    def __init__(
        self,
        hwnd: HWND = None,
        vmid: c_long = None,
        ac: accessible_context = None,
    ) -> None:
        self.log = Logger(self.__class__.__name__)
        self._hwnd = hwnd
        self._vmid = vmid
        self._ac = ac

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
    def ac(self) -> accessible_context:
        return self._ac

    @ac.setter
    def ac(self, ac: accessible_context) -> None:
        self._ac = ac

    def __del__(self) -> None:
        if BRIDGE:
            BRIDGE.releaseJavaObject(self.vmid, self.ac)

    def __eq__(self, ac: accessible_context) -> bool:
        is_eligible = self.vmid == ac.vmid and BRIDGE.isSameObject(
            self.vmid,
            self.ac,
            ac.ac,
        )
        return is_eligible

    def __hash__(self) -> int:
        return super().__hash__()

    def __ne__(self, ac: accessible_context) -> bool:
        is_eligible = self.vmid != ac.vmid or not BRIDGE.isSameObject(
            self.vmid,
            self.ac,
            ac.ac,
        )
        return is_eligible