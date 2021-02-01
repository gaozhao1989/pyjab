from ctypes import c_long
from ctypes.wintypes import HWND
from pyjab.common.logger import Logger
from pyjab.jabhandler import JABHandler
from pyjab.common.types import JOBJECT64

from pyjab.globalargs import BRIDGE
from pyjab.globalargs import VMIDS_OF_HWND


class JABContext(object):
    def __init__(
        self,
        hwnd: HWND = None,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> None:
        self.log = Logger(self.__class__.__name__)
        self.jab_handler = JABHandler(BRIDGE)
        if hwnd and not vmid:
            vmid = c_long()
            accessible_context = JOBJECT64()
            self.jab_handler.get_accessible_context_from_hwnd(
                hwnd, vmid, accessible_context
            )
            vmid = vmid.value
            global VMIDS_OF_HWND
            VMIDS_OF_HWND[vmid] = hwnd
        elif vmid and not hwnd:
            hwnd = self.jab_handler.get_hwnd_from_accessible_context(
                vmid, accessible_context
            )
        if BRIDGE is None:
            global BRIDGE
            BRIDGE = self.jab_handler.bridge
        self._hwnd = hwnd
        self._vmid = vmid
        self._accessible_context = accessible_context

    def __del__(self) -> None:
        if BRIDGE:
            self.jab_handler.release_java_object(self.vmid, self.accessible_context)

    def __eq__(self, jabcontext) -> bool:
        is_eligible = (
            self.vmid == jabcontext.vmid
            and self.jab_handler.is_same_object(
                self.vmid,
                self.accessible_context,
                jabcontext.accessible_context,
            )
        )
        return is_eligible

    def __hash__(self) -> int:
        return super().__hash__()

    def __ne__(self, jabcontext) -> bool:
        is_eligible = (
            self.vmid != jabcontext.vmid
            or not self.jab_handler.is_same_object(
                self.vmid,
                self.accessible_context,
                jabcontext.accessible_context,
            )
        )
        return is_eligible

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