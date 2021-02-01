from ctypes import CDLL, c_int, c_long, c_wchar, create_string_buffer
from ctypes import byref
from ctypes.wintypes import HWND
from typing import Tuple
from pyjab.accessibleinfo import (
    AccessBridgeVersionInfo,
    AccessibleContextInfo,
    AccessibleTextInfo,
    AccessibleTextItemsInfo,
    AccessibleTextSelectionInfo,
)
from pyjab.jabelement import JABElement
from pyjab.common.eventhandler import EvenetHandler
from pyjab.common.winuser import WinUser
from pyjab.common.logger import Logger
from pyjab.common.service import Service
from pyjab.common.types import JOBJECT64
from pyjab.common.types import focus_gained_fp
from pyjab.jabcontext import JABContext
from pyjab.globalargs import VMIDS_OF_HWND


class JABHandler(object):
    def __init__(self, bridge: CDLL = None) -> None:
        self.log = Logger(self.__class__.__name__)
        self._bridge = bridge if isinstance(bridge, CDLL) else Service().load_library()
        self.win_user = WinUser()
        self.event_handler = EvenetHandler()

    @property
    def bridge(self) -> CDLL:
        return self._bridge

    @bridge.setter
    def bridge(self, bridge: CDLL) -> None:
        self._bridge = bridge

    def release_java_object(self, vmid: c_long, accessible_context: JOBJECT64) -> None:
        try:
            self.bridge.releaseJavaObject(vmid, accessible_context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'releaseJavaObject' error", exc_info=exc
            )

    def get_top_level_object(
        self, vmid: c_long, accessible_context: JOBJECT64
    ) -> JOBJECT64:
        try:
            return self.bridge.getTopLevelObject(vmid, accessible_context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getTopLevelObject' error", exc_info=exc
            )
            return None

    def _get_hwnd_from_accessible_context(
        self, vmid: c_long, accessible_context: JOBJECT64
    ) -> HWND:
        top_level_object = self.get_top_level_object(vmid, accessible_context)
        try:
            return self.bridge.getHWNDFromAccessibleContext(vmid, top_level_object)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getHWNDFromAccessibleContext' error",
                exc_info=exc,
            )
            return None
        finally:
            self.release_java_object(vmid, top_level_object)

    def get_hwnd_from_accessible_context(
        self, vmid: c_long, accessible_context: JOBJECT64
    ) -> HWND:
        hwnd = self._get_hwnd_from_accessible_context(vmid, accessible_context)
        if hwnd:
            global VMIDS_OF_HWND
            VMIDS_OF_HWND[vmid] = hwnd
            return hwnd
        else:
            return VMIDS_OF_HWND.get(vmid)

    def get_accessible_context_from_hwnd(
        self, hwnd: HWND, vmid: c_long, accessible_context: JOBJECT64
    ) -> JOBJECT64:
        try:
            return self.bridge.getAccessibleContextFromHWND(
                hwnd, byref(vmid), byref(accessible_context)
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleContextFromHWND' error",
                exc_info=exc,
            )
            return None

    def is_same_object(
        self,
        vmid: c_long,
        expected_accessible_context: JOBJECT64,
        actual_accessible_context: JOBJECT64,
    ) -> bool:
        try:
            return self.bridge.isSameObject(
                vmid, expected_accessible_context, actual_accessible_context
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'isSameObject' error",
                exc_info=exc,
            )
            return False

    def get_bridge_version_info(self, vmid: c_long) -> AccessBridgeVersionInfo:
        info = AccessBridgeVersionInfo()
        try:
            self.bridge.getVersionInfo(vmid, byref(info))
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getVersionInfo' error",
                exc_info=exc,
            )
        return info

    def get_object_depth(self, vmid: c_long, accessible_context: JOBJECT64) -> int:
        try:
            return self.bridge.getObjectDepth(vmid, accessible_context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getObjectDepth' error",
                exc_info=exc,
            )
            return -1

    def get_accessible_context_info(
        self, vmid: c_long, accessible_context: JOBJECT64
    ) -> AccessibleContextInfo:
        info = AccessibleContextInfo()
        try:
            self.bridge.getAccessibleContextInfo(vmid, accessible_context, byref(info))
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleContextInfo' error",
                exc_info=exc,
            )
        return info

    def get_accessible_text_info(
        self, vmid: c_long, accessible_context: JOBJECT64, x: c_int, y: c_int
    ) -> AccessibleTextInfo:
        info = AccessibleTextInfo()
        try:
            self.bridge.getAccessibleTextInfo(
                vmid, accessible_context, byref(info), x, y
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTextInfo' error",
                exc_info=exc,
            )
        return info

    def get_accessible_text_items(
        self, vmid: c_long, accessible_context: JOBJECT64, index: c_int
    ) -> AccessibleTextItemsInfo:
        info = AccessibleTextItemsInfo()
        try:
            self.bridge.getAccessibleTextItems(
                vmid, accessible_context, byref(info), index
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTextItems' error",
                exc_info=exc,
            )
        return info

    def get_accessible_text_selection_info(
        self, vmid: c_long, accessible_context: JOBJECT64
    ) -> AccessibleTextSelectionInfo:
        info = AccessibleTextSelectionInfo()
        try:
            self.bridge.getAccessibleTextSelectionInfo(
                vmid, accessible_context, byref(info)
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTextSelectionInfo' error",
                exc_info=exc,
            )
        return info

    def get_accessible_text_range(
        self, vmid: c_long, accessible_context: JOBJECT64, start: c_int, end: c_int
    ) -> str:
        length = end + 1 - start
        if length <= 0:
            return u""
        # Use a string buffer, as from an unicode buffer, we can't get the raw data.
        buffer = create_string_buffer((length + 1) * 2)
        try:
            return self.bridge.getAccessibleTextRange(
                vmid, accessible_context, start, end, buffer, length
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTextRange' error",
                exc_info=exc,
            )
            return u""

    def _get_accessible_text_line_bounds(
        self,
        vmid: c_long,
        accessible_context: JOBJECT64,
        index: c_long,
        start_index: c_long,
        end_index: c_long,
    ) -> None:
        try:
            self.bridge.getAccessibleTextLineBounds(
                vmid, accessible_context, index, byref(start_index), byref(end_index)
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTextLineBounds' error",
                exc_info=exc,
            )

    def get_accessible_text_line_bounds(
        self, vmid: c_long, accessible_context: JOBJECT64, index: int
    ) -> Tuple:
        index = max(index, 0)
        self.log.debug("line bounds: index {}".format(index))
        # Java returns end as the last character, not end as past the last character
        start_index = c_int()
        end_index = c_int()
        self._get_accessible_text_line_bounds(
            vmid, accessible_context, index, byref(start_index), byref(end_index)
        )
        start = start_index.value
        end = end_index.value
        self.log.debug(
            "line bounds: start {start}, end {end}".format(start=start, end=end)
        )
        if end < start or start < 0:
            # Invalid or empty line.
            return (0, -1)
        # OpenOffice sometimes returns offsets encompassing more than one line, so try to narrow them down.
        # Try to retract the end offset.
        self._get_accessible_text_line_bounds(
            vmid, accessible_context, end, byref(start_index), byref(end_index)
        )
        temp_start = max(start_index.value, 0)
        temp_end = max(end_index.value, 0)
        self.log.debug(
            "line bounds: temp_start {temp_start}, temp_end {temp_end}".format(
                temp_start=temp_start, temp_end=temp_end
            )
        )
        if temp_start > (index + 1):
            # This line starts after the requested index, so set end to point at the line before.
            end = temp_start - 1
        # Try to retract the start.
        self._get_accessible_text_line_bounds(
            vmid, accessible_context, start, byref(start_index), byref(end_index)
        )
        temp_start = max(start_index.value, 0)
        temp_end = max(end_index.value, 0)
        self.log.debug(
            "line bounds: temp_start {temp_start}, temp_end {temp_end}".format(
                temp_start=temp_start, temp_end=temp_end
            )
        )
        if temp_end < (index - 1):
            # This line ends before the requested index, so set start to point at the line after.
            start = temp_end + 1
        self.log.debug(
            "line bounds: returning {start}, {end}".format(start=start, end=end)
        )
        return start, end
    
    def get_accessible_parent_from_context(self, vmid:c_long, accessible_context:JOBJECT64) -> JABContext:
        try:
            accessible_context = self.bridge.getAccessibleParentFromContext(vmid, accessible_context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleParentFromContext' error",
                exc_info=exc,
            )
        if accessible_context:
            return JABContext(JABContext.hwnd, vmid, accessible_context)
        else:
            return None
    
    def get_accessible_parent_with_role(self, vmid:c_long, accessible_context:JOBJECT64, role: c_wchar)-> JABContext:
        try:
            accessible_context = self.bridge.getParentWithRole(vmid, accessible_context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getParentWithRole' error",
                exc_info=exc,
            )
        if accessible_context:
            return JABContext(JABContext.hwnd, vmid, accessible_context)
        else:
            return None
    
    

    @focus_gained_fp
    def _gain_focus(self, vmid: c_long, event: JOBJECT64, source: JOBJECT64) -> None:
        hwnd = self.get_hwnd_from_accessible_context(vmid, source)
        self.release_java_object(vmid, event)

    def gain_focus(
        self, vmid: c_long, accessible_context: JOBJECT64, hwnd: HWND
    ) -> None:
        jab_context = JABContext(
            hwnd=hwnd, vmid=vmid, accessible_context=accessible_context
        )
        is_descendant_window = self.win_user.is_descendant_window(
            self.win_user.get_foreground_window(), jab_context.hwnd
        )
        if not is_descendant_window:
            return
        focus = self.event_handler.last_queue_focus
        is_same_object = (
            isinstance(focus, JABElement) and focus.jab_context == jab_context
        )
        if is_same_object:
            return
        focused_jab_element = JABElement(jab_context=jab_context)
