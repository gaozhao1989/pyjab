from ctypes import c_long
from ctypes.wintypes import HWND
from typing import TypeVar
from pyjab.common.logger import Logger
from pyjab.common.types import JOBJECT64

_JABContext = TypeVar("_JABContext", bound="JABContext")


class JABContext(object):
    def __init__(
        self,
        hwnd: HWND = None,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> None:
        self.log = Logger(self.__class__.__name__)
        self._hwnd = hwnd
        self._vmid = vmid
        self._accessible_context = accessible_context

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

    def __del__(self) -> None:
        self.hwnd = None
        self.vmid = None
        self.accessible_context = None

    def __eq__(self, jab_context: _JABContext) -> bool:
        is_eligible = (
            self.vmid == jab_context.vmid
            and self.hwnd == jab_context.hwnd
            and self.accessible_context == jab_context.accessible_context
        )
        return is_eligible

    def __hash__(self) -> int:
        return super().__hash__()

    def __ne__(self, jab_context: _JABContext) -> bool:
        is_eligible = (
            self.vmid != jab_context.vmid
            and self.hwnd != jab_context.hwnd
            and self.accessible_context != jab_context.accessible_context
        )
        return is_eligible