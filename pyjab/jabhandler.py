from ctypes import CDLL, c_int, c_long, c_short, c_wchar, create_string_buffer
from ctypes import byref
from ctypes.wintypes import HWND
from pyjab.jabcontext import JABContext
from typing import Tuple
from pyjab.accessibleinfo import (
    AccessBridgeVersionInfo,
    AccessibleContextInfo,
    AccessibleHyperlinkInfo,
    AccessibleHypertextInfo,
    AccessibleKeyBindings,
    AccessibleRelationSetInfo,
    AccessibleTableCellInfo,
    AccessibleTableInfo,
    AccessibleTextAttributesInfo,
    AccessibleTextInfo,
    AccessibleTextItemsInfo,
    AccessibleTextRectInfo,
    AccessibleTextSelectionInfo,
)
from pyjab.apicallbacks import focus_gained_fp
from pyjab.jabrole import JABElement
from pyjab.common.eventhandler import EvenetHandler
from pyjab.common.winuser import WinUser
from pyjab.common.logger import Logger
from pyjab.common.service import Service
from pyjab.common.types import JOBJECT64
from pyjab.jabcontext import JABContext
from pyjab.globalargs import VMIDS_OF_HWND


class JABHandler(object):
    def __init__(self, bridge: CDLL = None) -> None:
        self.log = Logger(self.__class__.__name__)
        self._bridge = bridge if isinstance(bridge, CDLL) else Service().load_library()
        self.user = WinUser()
        self.handler = EvenetHandler()
        # TODO: set hwnd or vmid at least for AccessibleContext
        self.ac = JABContext()
        self.init_jab_context(self.ac)

    @property
    def bridge(self) -> CDLL:
        return self._bridge

    @bridge.setter
    def bridge(self, bridge: CDLL) -> None:
        self._bridge = bridge

    def init_jab_context(self, ac: JABContext) -> None:
        hwnd = ac.hwnd
        vmid = ac.vmid
        ac = ac.ac
        if hwnd and not vmid:
            vmid = c_long()
            ac = JOBJECT64()
            self._get_accessible_context_from_hwnd(hwnd, vmid, ac)
            vmid = vmid.value
            global VMIDS_OF_HWND
            VMIDS_OF_HWND[vmid] = hwnd
        elif vmid and not hwnd:
            hwnd = self._get_hwnd_from_accessible_context(vmid, ac)
        ac.hwnd = hwnd
        ac.vmid = vmid
        ac.ac = ac

    # Gateway Functions
    # You typically call these functions before calling any other Java Access Bridge API function

    def is_java_window(self) -> bool:
        """
        Checks to see if the given window implements the Java Accessibility API.

        BOOL IsJavaWindow(HWND window);
        """
        result = False
        try:
            result = self.bridge.isJavaWindow(self.ac.hwnd)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'isJavaWindow' error",
                exc_info=exc,
            )
        return bool(result)

    def _get_accessible_context_from_hwnd(
        self, hwnd: HWND, vmid: c_long, ac: JABContext
    ) -> JABContext:
        """
        Gets the AccessibleContext and vmID values for the given window.
        Many Java Access Bridge functions require the AccessibleContext and vmID values.

        BOOL GetAccessibleContextFromHWND(HWND target, long *vmID, AccessibleContext *ac);
        """
        try:
            result = self.bridge.getAccessibleContextFromHWND(
                hwnd, byref(vmid), byref(ac)
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleContextFromHWND' error",
                exc_info=exc,
            )
            return None
        if result:
            return JABContext(hwnd=hwnd, vmid=vmid, ac=ac)

    def get_accessible_context_from_hwnd(self) -> JABContext:
        return self._get_accessible_context_from_hwnd(
            self.ac.hwnd,
            self.ac.vmid,
            self.ac.ac,
        )

    # Event Handling Functions
    # These take a function pointer to the function that will handle the event type. 
    # When you no longer are interested in receiving those types of events, 
    # call the function again, passing in the NULL value. 
    # Find prototypes for the function pointers you need pass into these functions in the file AccessBridgeCallbacks.h. 
    # See the section "API Callbacks" for more information about these prototypes.
    
    @focus_gained_fp
    def set_focus_fained(self)->None:
        ac = JABContext(hwnd=self.ac.hwnd, vmid=self.ac.vmid, ac=self.ac.ac)
        if not self.user.is_descendant_window(self.user.get_foreground_window(), ac.hwnd):
            return
        focus = self.handler.last_queue_focus
        



    # General Functions
    """
    Note:
    To determine the version of the JVM, you need to pass in a valid vmID; 
    otherwise all that is returned is the version of the WindowsAccessBridge.DLL file to which your application is connected.
    """

    def _release_java_object(self, vmid: c_long, context: JABContext) -> None:
        """
        Release the memory used by the Java object object, where object is an object returned to you by Java Access Bridge.
        Java Access Bridge automatically maintains a reference to all Java objects that it returns to you in the JVM so they are not garbage collected.
        To prevent memory leaks, call ReleaseJavaObject on all Java objects returned to you by Java Access Bridge once you are finished with them.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object

        Returns:

            None
        """
        try:
            self.bridge.releaseJavaObject(vmid, context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'releaseJavaObject' error",
                exc_info=exc,
            )

    def release_java_object(self) -> None:
        self._release_java_object(self.ac.vmid, self.ac.ac)

    def _get_version_info(
        self, vmid: c_long, info: AccessBridgeVersionInfo
    ) -> AccessBridgeVersionInfo or None:
        """
        Gets the version information of the instance of Java Access Bridge instance your application is using.
        You can use this information to determine the available functionality of your version of Java Access Bridge.

        Args:

            vmid: java vmid of specific java window
            info: structure of access bridge version info

        Returns:

            AccessBridgeVersionInfo: get info success.
            None: get info failed.
        """
        try:
            result = self.bridge.getVersionInfo(vmid, info)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getVersionInfo' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_version_info(self) -> AccessBridgeVersionInfo:
        info = AccessBridgeVersionInfo()
        self._get_version_info(self.ac.vmid, byref(info))
        return info

    # Accessible Context Functions
    # These functions provide the core of the Java Accessibility API that is exposed by Java Access Bridge.
    # The functions GetAccessibleContextAt and GetAccessibleContextWithFocus retrieve an AccessibleContext object,
    # which is a magic cookie (a Java Object reference) to an Accessible object and a JVM cookie.
    # You use these two cookies to reference objects through Java Access Bridge.
    # Most Java Access Bridge API functions require that you pass in these two parameters.
    """
    Note:
    AccessibleContext objects are 64-bit references under 64-bit interprocess communication (which uses the windowsaccessbridge-64.dll file). 
    However, prior to JDK 9, AccessibleContext objects are 32-bit references under 32-bit interprocess communication (which uses the windowsaccessbridge.dll file without -32 or -64 in the file name). 
    Consequently, if you are converting your assistive technology applications to run on 64-bit Windows systems, then you need to recompile your assistive technology applications.
    """
    # The function GetAccessibleContextInfo returns detailed information about an AccessibleContext object belonging to the JVM.
    # In order to improve performance, the various distinct methods in the Java Accessibility API are collected together into a few routines in the Java Access Bridge API and returned in struct values.
    # The file AccessBridgePackages.h defines these struct values and Java Access Bridge API Callbacks describes them.

    # The functions GetAccessibleChildFromContext and GetAccessibleParentFromContext enable you to walk the GUI component hierarchy, retrieving the nth child, or the parent, of a particular GUI object.

    def _get_accessible_context_at(
        self,
        vmid: c_long,
        parent_context: JABContext,
        x: c_int,
        y: c_int,
        child_context: JABContext,
    ) -> JABContext or None:
        """
        Retrieves an AccessibleContext object of the window or object that is under the mouse pointer.

        Args:

            vmid: java vmid of specific java window
            parent_context: parent accessible context of specifc java object
            x: position x of child accessible context
            y: position y of child accessible context
            child_context: child accessible context of specifc java object

        Returns:

            AccessibleContext: get Accessible Context success
            None: get Accessible Context failed
        """
        try:
            result = self.bridge.GetAccessibleContextAt(
                vmid, parent_context, x, y, child_context
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleContextAt' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_accessible_context_at(self, x: c_int, y: c_int) -> JABContext:
        accessible_context = None
        # TODO: set hwnd or vmid at least for AccessibleContext
        new_accessible_context = JABContext()
        self.init_jab_context(new_accessible_context)
        accessible_context = self._get_accessible_context_at(
            self.ac.vmid,
            self.ac.ac,
            x,
            y,
            byref(new_accessible_context),
        )
        if not accessible_context or not new_accessible_context:
            self.log.error("invalid accessible context")
            return None
        if not self.is_same_object(new_accessible_context, self.ac):
            return JABContext(
                self.ac.hwnd,
                self.ac.vmid,
                new_accessible_context,
            )
        elif new_accessible_context != self.ac:
            self._release_java_object(
                new_accessible_context.vmid, new_accessible_context
            )
        return None

    def _get_accessible_context_with_focus(
        self, hwnd: HWND, vmid: c_long, context: JABContext
    ) -> JABContext or None:
        """
        Retrieves an AccessibleContext object of the window or object that has the focus.

        Args:

            hwnd: HWND of specific window
            vmid: java vmid of specific java window
            context: accessible context of specifc java object

        Returns:

            AccessibleContext: get Accessible Context success
            None: get Accessible Context failed
        """
        try:
            result = self.bridge.GetAccessibleContextWithFocus(hwnd, vmid, context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleContextWithFocus' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_accessible_context_with_focus(self) -> JABContext:
        return self._get_accessible_context_with_focus(
            self.ac.hwnd,
            self.ac.vmid,
            self.ac.ac,
        )

    def _get_accessible_context_info(
        self, vmid: c_long, context: JABContext, info: AccessibleContextInfo
    ) -> AccessibleContextInfo or None:
        """
        Retrieves an AccessibleContextInfo object of the AccessibleContext object ac.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            info: structure of access bridge accessible context info

        Returns:

            AccessibleContextInfo: get info success.
            None: get info failed.
        """
        try:
            result = self.bridge.GetAccessibleContextInfo(vmid, context, info)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleContextInfo' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_accessible_context_info(self) -> AccessibleContextInfo:
        info = AccessibleContextInfo()
        self._get_accessible_context_info(
            self.ac.vmid,
            self.ac.ac,
            byref(info),
        )
        return info

    def _get_accessible_child_from_context(
        self, vmid: c_long, context: JABContext, index: c_int
    ) -> JABContext or None:
        """
        Returns an AccessibleContext object that represents the nth child of the object ac, where n is specified by the value index.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            index: index of child accessible context

        Returns:
            AccessibleContext: get child accessible context success
            None: get child accessible context failed
        """
        try:
            result = self.bridge.GetAccessibleChildFromContext(vmid, context, index)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleChildFromContext' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_accessible_child_from_context(self, index: c_int) -> JABContext:
        accessible_context = self._get_accessible_child_from_context(
            self.ac.vmid,
            self.ac.ac,
            index,
        )
        if accessible_context:
            return JABContext(
                self.ac.hwnd,
                self.ac.vmid,
                accessible_context,
            )
        else:
            return None

    def _get_accessible_parent_from_context(
        self, vmid: c_long, context: JABContext
    ) -> JABContext or None:
        """
        Returns an AccessibleContext object that represents the parent of object ac.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object

        Returns:
            AccessibleContext: get parent accessible context success
            None: get parent accessible context failed
        """
        try:
            result = self.bridge.GetAccessibleParentFromContext(vmid, context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleParentFromContext' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_accessible_parent_from_context(self) -> JABContext:
        accessible_context = self._get_accessible_parent_from_context(
            self.ac.vmid,
            self.ac.ac,
        )
        if accessible_context:
            return JABContext(
                self.ac.hwnd,
                self.ac.vmid,
                accessible_context,
            )
        else:
            return None

    def _get_hwnd_from_accessible_context(
        self, vmid: c_long, context: JABContext
    ) -> HWND or None:
        """
        Returns the HWND from the AccessibleContextof a top-level window.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object

        Returns:

            HWND: get HWND of current window success
            None:  get HWND of current window failed
        """
        try:
            result = self.bridge.getHWNDFromAccessibleContext(vmid, context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getHWNDFromAccessibleContext' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_hwnd_from_accessible_context(self) -> HWND:
        hwnd = self._get_hwnd_from_accessible_context(self.ac.vmid, self.ac.ac)
        if hwnd:
            global VMIDS_OF_HWND
            VMIDS_OF_HWND[self.ac.vmid] = hwnd
            return hwnd
        else:
            return VMIDS_OF_HWND.get(self.ac.vmid)

    # Accessible Text Functions
    # These functions get AccessibleText information provided by the Java Accessibility API, broken down into seven chunks for efficiency.
    # An AccessibleContext has AccessibleText information contained within it if you set the flag accessibleText in the AccessibleContextInfo data structure to TRUE.
    # The file AccessBridgePackages.h defines the struct values used in these functions Java Access Bridge API Callbacks describes them.

    def _get_accessible_text_info(
        self,
        vmid: c_long,
        context: JABContext,
        info: AccessibleTextInfo,
        x: c_int,
        y: c_int,
    ) -> AccessibleTextInfo or None:
        try:
            result = self.bridge.GetAccessibleTextInfo(vmid, context, info, x, y)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleTextInfo' error", exc_info=exc
            )
            return None
        else:
            return result

    def get_accessible_text_info(self, x: c_int, y: c_int) -> AccessibleTextInfo:
        info = AccessibleTextInfo()
        self._get_accessible_text_info(
            self.ac.vmid,
            self.ac.ac,
            byref(info),
            x,
            y,
        )
        return info

    def _get_accessible_text_items(
        self,
        vmid: c_long,
        context: JABContext,
        info: AccessibleTextItemsInfo,
        index: c_int,
    ) -> AccessibleTextItemsInfo or None:
        try:
            result = self.bridge.GetAccessibleTextItems(vmid, context, info, index)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleTextItems' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_accessible_text_items(self, index: c_int) -> AccessibleTextItemsInfo:
        info = AccessibleTextItemsInfo()
        self._get_accessible_text_items(
            self.ac.vmid,
            self.ac.ac,
            byref(info),
            index,
        )
        return info

    def _get_accessible_text_selection_info(
        self,
        vmid: c_long,
        context: JABContext,
        info: AccessibleTextSelectionInfo,
    ) -> AccessibleTextSelectionInfo or None:
        try:
            result = self.bridge.GetAccessibleTextSelectionInfo(vmid, context, info)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleTextSelectionInfo' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_accessible_text_selection_info(self) -> AccessibleTextSelectionInfo:
        info = AccessibleTextSelectionInfo()
        self._get_accessible_text_selection_info(
            self.ac.vmid,
            self.ac.ac,
            byref(info),
        )
        return info

    def _get_accessible_text_attributes(
        self,
        vmid: c_long,
        context: JABContext,
        index: c_int,
        info: AccessibleTextAttributesInfo,
    ) -> AccessibleTextAttributesInfo or None:
        try:
            result = self.bridge.GetAccessibleTextAttributes(vmid, context, index, info)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleTextAttributes' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_accessible_text_attributes(
        self, index: c_int
    ) -> AccessibleTextAttributesInfo:
        info = AccessibleTextAttributesInfo()
        self._get_accessible_text_attributes(
            self.ac.vmid,
            self.ac.ac,
            index,
            byref(info),
        )
        return info

    def _get_accessible_text_rect(
        self,
        vmid: c_long,
        context: JABContext,
        info: AccessibleTextRectInfo,
        index: c_int,
    ) -> AccessibleTextRectInfo or None:
        try:
            result = self.bridge.GetAccessibleTextRect(vmid, context, info, index)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'GetAccessibleTextRect' error",
                exc_info=exc,
            )
            return None
        else:
            return result

    def get_accessible_text_rect(self, index: c_int) -> AccessibleTextRectInfo:
        info = AccessibleTextRectInfo()
        self._get_accessible_text_rect(
            self.ac.vmid,
            self.ac.ac,
            byref(info),
            index,
        )
        return info

    def _get_accessible_text_range(
        self, vmid: c_long, context: JABContext, start: c_int, end: c_int
    ) -> str:
        length = end + 1 - start
        if length <= 0:
            return u""
        # Use a string buffer, as from an unicode buffer, we can't get the raw data.
        buffer = create_string_buffer((length + 1) * 2)
        try:
            return self.bridge.getAccessibleTextRange(
                vmid, context, start, end, buffer, length
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTextRange' error",
                exc_info=exc,
            )
            return u""

    def get_accessible_text_range(self, start: c_int, end: c_int) -> str:
        # TODO: handle return text from raw bytes
        return self._get_accessible_text_range(
            self.ac.vmid,
            self.ac.ac,
            start,
            end,
        )

    def _get_accessible_text_line_bounds(
        self,
        vmid: c_long,
        context: JABContext,
        index: c_int,
        start: c_int,
        end: c_int,
    ) -> Tuple or None:
        try:
            return self.bridge.getAccessibleTextLineBounds(
                vmid,
                context,
                index,
                start,
                end,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTextLineBounds' error",
                exc_info=exc,
            )
            return None

    def get_accessible_text_line_bounds(self, index: c_int) -> Tuple:
        index = max(index, 0)
        self.log.debug("line bounds: index {}".format(index))
        # Java returns end as the last character, not end as past the last character
        start_line = c_int()
        end_line = c_int()
        self._get_accessible_text_line_bounds(
            self.ac.vmid,
            self.ac.ac,
            index,
            byref(start_line),
            byref(end_line),
        )
        start = start_line.value
        end = end_line.value
        self.log.debug(
            "line bounds: start {start}, end {end}".format(start=start, end=end)
        )
        if end < start or start < 0:
            # Invalid or empty line.
            return (0, -1)
        # OpenOffice sometimes returns offsets encompassing more than one line, so try to narrow them down.
        # Try to retract the end offset.
        self._get_accessible_text_line_bounds(
            self.ac.vmid,
            self.ac.ac,
            end,
            byref(start_line),
            byref(end_line),
        )
        temp_start = max(start_line.value, 0)
        temp_end = max(end_line.value, 0)
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
            self.ac.vmid,
            self.ac.ac,
            start,
            byref(start_line),
            byref(end_line),
        )
        temp_start = max(start_line.value, 0)
        temp_end = max(end_line.value, 0)
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

    # Additional Text Functions
    def _select_text_range(
        self, vmid: c_long, context: JABContext, start: c_int, end: c_int
    ) -> bool:
        """
        Selects text between two indices. Selection includes the text at the start index and the text at the end index.
        Returns whether successful.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            start: start index of the selection text
            end: end index of the selection text

        Returns:

            True: select action success
            False: select action failed
        """
        result = False
        try:
            result = self.bridge.selectTextRange(
                vmid,
                context,
                start,
                end,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'selectTextRange' error",
                exc_info=exc,
            )
        return bool(result)

    def select_text_range(self, start: c_int, end: c_int) -> bool:
        return self._select_text_range(
            self.ac.vmid,
            self.ac.ac,
            byref(start),
            byref(end),
        )

    def _get_text_attributes_in_range(
        self,
        vmid: c_long,
        context: JABContext,
        start: c_int,
        end: c_int,
        info: AccessibleTextAttributesInfo,
        length: c_short,
    ) -> bool:
        """
        Get text attributes between two indices.
        The attribute list includes the text at the start index and the text at the end index.
        Returns whether successful.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            start: start index of the text range
            end: end index of the text range
            info: accessible text attribuetes info
            length:

        Returns:

            True: get text attributes in range success
            False: get text attributes in range failed
        """
        result = False
        try:
            result = self.bridge.getTextAttributesInRange(
                vmid, context, start, end, info, length
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getTextAttributesInRange' error",
                exc_info=exc,
            )
        return bool(result)

    def get_text_attributes_in_range(self, start, end) -> Tuple:
        info = AccessibleTextAttributesInfo()
        length = c_short()
        self._get_text_attributes_in_range(
            self.ac.vmid,
            self.ac.ac,
            start,
            end,
            byref(info),
            length,
        )
        return info, length.value

    def _set_caret_position(
        self, vmid: c_long, context: JABContext, position: c_int
    ) -> bool:
        """
        Set the caret to a text position.
        Returns whether successful.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            position: number of text position

        Returns:

            True: set the caret to a text position success
            False: set the caret to a text position failed
        """
        result = False
        try:
            result = self.bridge.setCaretPosition(vmid, context, position)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'setCaretPosition' error",
                exc_info=exc,
            )
        return bool(result)

    def set_caret_position(self, position: c_int) -> bool:
        return self._set_caret_position(
            self.ac.vmid,
            self.ac.ac,
            position,
        )

    def _get_caret_location(
        self,
        vmid: c_long,
        context: JABContext,
        info: AccessibleTextRectInfo,
        index: c_int,
    ) -> bool:
        """
        Gets the text caret location.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            info: accessible text rect info
            index: index of caret

        Returns:

            True: get the text caret location success
            False: get the text caret location failed
        """
        result = False
        try:
            result = self.bridge.getCaretLocation(vmid, context, info, index)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getCaretLocation' error",
                exc_info=exc,
            )
        return bool(result)

    def get_caret_location(self, index: c_int) -> Tuple:
        info = AccessibleTextRectInfo()
        self._get_caret_location(
            self.ac.vmid,
            self.ac.ac,
            byref(info),
            index,
        )
        return info.x, info.y

    def _set_text_contents(
        self, vmid: c_long, context: JABContext, text: c_wchar
    ) -> bool:
        """
        Sets editable text contents.
        The AccessibleContext must implement AccessibleEditableText and be editable.
        The maximum text length that can be set is MAX_STRING_SIZE - 1.
        Returns whether successful.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            text: text contents need to be set

        Returns:

            True: set editable text contents success
            False: set editable text contents failed
        """
        result = False
        try:
            result = self.bridge.setTextContents(vmid, context, text)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'setTextContents' error",
                exc_info=exc,
            )
        return bool(result)

    def set_text_contents(self, text: c_wchar) -> bool:
        return self._set_text_contents(
            self.ac.vmid,
            self.ac.ac,
            text,
        )

    # Accessible Table Functions

    def _get_accessible_table_info(
        self, vmid: c_long, context: JABContext, info: AccessibleTableInfo
    ) -> bool:
        """
        Returns information about the table, for example, caption, summary, row and column count, and the AccessibleTable.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            info: accessible table info

        Returns:

            True: get accessible table info success
            False: get accessible table info failed
        """
        result = False
        try:
            result = self.bridge.getAccessibleTableInfo(vmid, context, info)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableInfo' error",
                exc_info=exc,
            )
        return bool(result)

    def get_accessible_table_info(self) -> AccessibleTableInfo:
        info = AccessibleTableInfo()
        if self._get_accessible_table_info(
            self.ac.vmid,
            self.ac.ac,
            byref(info),
        ):
            for item in [
                info.caption,
                info.summary,
                info.accessibleContext,
                info.accessibleTable,
            ]:
                item = (
                    JABContext(
                        hwnd=self.ac.hwnd,
                        vmid=self.ac.vmid,
                        ac=item,
                    )
                    if item
                    else None
                )
            return info

    def _get_accessible_table_cell_info(
        self,
        vmid: c_long,
        context: JABContext,
        row: c_int,
        column: c_int,
        info: AccessibleTableCellInfo,
    ) -> bool:
        """
        Returns information about the specified table cell. The row and column specifiers are zero-based.

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            row: index of row number for table cell
            column: index of column number for table cell
            info: accessible table cell info

        Returns:

            True: get accessible table cell info success
            False: get accessible table cell info failed
        """
        result = False
        try:
            result = self.bridge.getAccessibleTableCellInfo(
                vmid, context, row, column, info
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableCellInfo' error",
                exc_info=exc,
            )
        return bool(result)

    def get_accessible_table_cell_info(
        self, row: c_int, column: c_int
    ) -> AccessibleTableCellInfo:
        info = AccessibleTableCellInfo()
        if self._get_accessible_table_cell_info(
            self.ac.vmid,
            self.ac.ac,
            row,
            column,
            byref(info),
        ):
            info.accessibleContext = (
                JABContext(
                    hwnd=self.ac.hwnd,
                    vmid=self.ac.vmid,
                    ac=info.accessibleContext,
                )
                if info.accessibleContext
                else None
            )
            return info

    def get_accessible_table_row_header(self) -> AccessibleTableInfo:
        """
        Returns the table row headers of the specified table as a table.
        """
        info = AccessibleTableInfo()
        result = False
        try:
            result = self.bridge.getAccessibleTableRowHeader(
                self.ac.vmid,
                self.ac.ac,
                byref(info),
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableRowHeader' error",
                exc_info=exc,
            )
        if result:
            for item in [
                info.caption,
                info.summary,
                info.accessibleContext,
                info.accessibleTable,
            ]:
                item = (
                    JABContext(
                        hwnd=self.ac.hwnd,
                        vmid=self.ac.vmid,
                        ac=item,
                    )
                    if item
                    else None
                )
            return info

    def get_accessible_table_column_header(self) -> AccessibleTableInfo:
        """
        Returns the table column headers of the specified table as a table.
        """
        info = AccessibleTableInfo()
        result = False
        try:
            result = self.bridge.getAccessibleTableColumnHeader(
                self.ac.vmid,
                self.ac.ac,
                byref(info),
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableColumnHeader' error",
                exc_info=exc,
            )
        if result:
            for item in [
                info.caption,
                info.summary,
                info.accessibleContext,
                info.accessibleTable,
            ]:
                item = (
                    JABContext(
                        hwnd=self.ac.hwnd,
                        vmid=self.ac.vmid,
                        ac=item,
                    )
                    if item
                    else None
                )
            return info

    def get_accessible_table_row_description(self, row: c_int) -> JABContext:
        """
        Returns the description of the specified row in the specified table.
        The row specifier is zero-based.
        """
        result = None
        try:
            result = self.bridge.getAccessibleTableRowDescription(
                self.ac.vmid,
                self.ac.ac,
                row,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableRowDescription' error",
                exc_info=exc,
            )
        if result:
            return JABContext(
                hwnd=self.ac.hwnd,
                vmid=self.ac.vmid,
                accessible_context=self.ac.ac,
            )

    def get_accessible_table_column_description(
        self, column: c_int
    ) -> JABContext:
        """
        Returns the description of the specified column in the specified table.
        The column specifier is zero-based.
        """
        result = None
        try:
            result = self.bridge.getAccessibleTableColumnDescription(
                self.ac.vmid,
                self.ac.ac,
                column,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableColumnDescription' error",
                exc_info=exc,
            )
        if result:
            return JABContext(
                hwnd=self.ac.hwnd,
                vmid=self.ac.vmid,
                accessible_context=self.ac.ac,
            )

    def get_accessible_table_row_selection_count(self) -> int:
        """
        Returns how many rows in the table are selected.
        """
        result = None
        try:
            result = self.bridge.getAccessibleTableRowSelectionCount(
                self.ac.vmid,
                self.ac.ac,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableRowSelectionCount' error",
                exc_info=exc,
            )
        if isinstance(result, int) and result != -1:
            return result

    def is_accessible_table_row_selected(self, row: c_int) -> bool:
        """
        Returns true if the specified zero based row is selected.
        """
        result = False
        try:
            result = self.bridge.isAccessibleTableRowSelected(
                self.ac.vmid,
                self.ac.ac,
                row,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'isAccessibleTableRowSelected' error",
                exc_info=exc,
            )
        return bool(result)

    def get_accessible_table_row_selections(
        self, count: c_int, selections: c_int
    ) -> list:
        """
        Returns an array of zero based indices of the selected rows.
        """
        result = False
        try:
            result = self.bridge.getAccessibleTableRowSelections(
                self.ac.vmid,
                self.ac.ac,
                count,
                selections,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableRowSelections' error",
                exc_info=exc,
            )
        if result and result != -1:
            return result

    def get_accessible_table_column_selection_count(self) -> int:
        """
        Returns how many columns in the table are selected.
        """
        result = None
        try:
            result = self.bridge.getAccessibleTableColumnSelectionCount(
                self.ac.vmid,
                self.ac.ac,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableColumnSelectionCount' error",
                exc_info=exc,
            )
        if isinstance(result, int) and result != -1:
            return result

    def is_accessible_table_column_selected(self, column: c_int) -> bool:
        """
        Returns true if the specified zero based column is selected.
        """
        result = False
        try:
            result = self.bridge.isAccessibleTableColumnSelected(
                self.ac.vmid,
                self.ac.ac,
                column,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'isAccessibleTableColumnSelected' error",
                exc_info=exc,
            )
        return bool(result)

    def get_accessible_table_column_selections(
        self, count: c_int, selections: c_int
    ) -> list:
        """
        Returns an array of zero based indices of the selected columns.
        """
        result = False
        try:
            result = self.bridge.getAccessibleTableColumnSelections(
                self.ac.vmid,
                self.ac.ac,
                count,
                selections,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableColumnSelections' error",
                exc_info=exc,
            )
        if result and result != -1:
            return result

    def get_accessible_table_row(self, index: c_int) -> int:
        """
        Returns the row number of the cell at the specified cell index.
        The values are zero based.
        """
        result = None
        try:
            result = self.bridge.getAccessibleTableRow(
                self.ac.vmid,
                self.ac.ac,
                index,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableRow' error",
                exc_info=exc,
            )
        is_eligible = isinstance(result, int) and result != -1
        if is_eligible:
            return result

    def get_accessible_table_column(self, index: c_int) -> int:
        """
        Returns the column number of the cell at the specified cell index.
        The values are zero based.
        """
        result = None
        try:
            result = self.bridge.getAccessibleTableColumn(
                self.ac.vmid,
                self.ac.ac,
                index,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableColumn' error",
                exc_info=exc,
            )
        is_eligible = isinstance(result, int) and result != -1
        if is_eligible:
            return result

    def get_accessible_table_index(self, row: c_int, column: c_int):
        """
        Returns the index in the table of the specified row and column offset.
        The values are zero based.
        """
        result = None
        try:
            result = self.bridge.getAccessibleTableIndex(
                self.ac.vmid,
                self.ac.ac,
                row,
                column,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleTableIndex' error",
                exc_info=exc,
            )
        is_eligible = isinstance(result, int) and result != -1
        if is_eligible:
            return result

    # Accessible Relation Set Function

    def get_accessible_relation_set(self) -> AccessibleRelationSetInfo:
        """
        Returns information about an object's related objects.
        """
        info = AccessibleRelationSetInfo()
        result = None
        try:
            result = self.bridge.getAccessibleRelationSet(
                self.ac.vmid,
                self.ac.ac,
                byref(info),
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleRelationSet' error",
                exc_info=exc,
            )
        is_eligible = result
        if is_eligible:
            return info

    # Accessible Hypertext Functions

    def get_accessible_hyper_text(self) -> AccessibleHypertextInfo:
        """
        Returns hypertext information associated with a component.
        """
        info = AccessibleHypertextInfo()
        result = None
        try:
            result = self.bridge.getAccessibleHypertext(
                self.ac.vmid,
                self.ac.ac,
                byref(info),
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleHypertext' error",
                exc_info=exc,
            )
        is_eligible = result
        if is_eligible:
            return info

    def active_accessible_hyper_link(self) -> bool:
        """
        Requests that a hyperlink be activated.
        """
        info = AccessibleHyperlinkInfo()
        result = False
        try:
            result = self.bridge.activateAccessibleHyperlink(
                self.ac.vmid,
                self.ac.ac,
                byref(info),
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'activateAccessibleHyperlink' error",
                exc_info=exc,
            )
        return bool(result)

    def get_accessible_hyper_link_count(self) -> int:
        """
        Returns the number of hyperlinks in a component.
        Maps to AccessibleHypertext.getLinkCount.
        Returns -1 on error.

        jint getAccessibleHyperlinkCount(const long vmID, const AccessibleHypertext hypertext);
        """
        result = 0
        try:
            result = self.bridge.getAccessibleHyperlinkCount(
                self.ac.vmid,
                self.ac.ac,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleHyperlinkCount' error",
                exc_info=exc,
            )
        is_eligible = isinstance(result, int) and result != -1
        if is_eligible:
            return result

    def get_accessible_hyper_text_ext(self, start: c_int) -> bool:
        """
        Iterates through the hyperlinks in a component.
        Returns hypertext information for a component starting at hyperlink index nStartIndex.
        No more than MAX_HYPERLINKS AccessibleHypertextInfo objects will be returned for each call to this method.
        Returns FALSE on error.

        BOOL getAccessibleHypertextExt(const long vmID, const AccessibleContext accessibleContext, const jint nStartIndex, AccessibleHypertextInfo *hypertextInfo);
        """
        info = AccessibleHypertextInfo()
        result = False
        try:
            result = self.bridge.getAccessibleHypertextExt(
                self.ac.vmid,
                self.ac.ac,
                start,
                byref(info),
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleHypertextExt' error",
                exc_info=exc,
            )
        return result

    def get_accessible_hyper_link_index(self, index: c_int) -> int:
        """
        Returns the index into an array of hyperlinks that is associated with a character index in document.
        Maps to AccessibleHypertext.getLinkIndex.
        Returns -1 on error.

        jint getAccessibleHypertextLinkIndex(const long vmID, const AccessibleHypertext hypertext, const jint nIndex);
        """
        result = False
        try:
            result = self.bridge.getAccessibleHypertextLinkIndex(
                self.ac.vmid,
                self.ac.ac,
                index,
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleHypertextLinkIndex' error",
                exc_info=exc,
            )
        is_eligible = isinstance(result, int) and result != -1
        if is_eligible:
            return result

    def get_accessible_hyper_link(self, index: c_int) -> JABContext:
        """
        Returns the nth hyperlink in a document.
        Maps to AccessibleHypertext.getLink.
        Returns FALSE on error.

        BOOL getAccessibleHyperlink(const long vmID, const AccessibleHypertext hypertext, const jint nIndex, AccessibleHypertextInfo *hyperlinkInfo);
        """
        info = AccessibleHypertextInfo()
        result = False
        try:
            result = self.bridge.getAccessibleHyperlink(
                self.ac.vmid,
                self.ac.ac,
                index,
                byref(info),
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleHyperlink' error",
                exc_info=exc,
            )
        if result:
            return JABContext(
                hwnd=self.ac.hwnd,
                vmid=self.ac.vmid,
                accessible_context=self.ac.ac,
            )

    # Accessible Key Binding Function

    def get_accessible_key_bindings(self) -> list:
        """
        Returns a list of key bindings associated with a component.

        BOOL getAccessibleKeyBindings(long vmID, AccessibleContext accessibleContext, AccessibleKeyBindings *keyBindings);
        """
        bindings = AccessibleKeyBindings()
        result = None
        try:
            result = self.bridge.getAccessibleKeyBindings(
                self.ac.vmid,
                self.ac.ac,
                byref(bindings),
            )
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getAccessibleKeyBindings' error",
                exc_info=exc,
            )
        is_eligible = isinstance(result, int) and result != -1
        if is_eligible:
            return result

    def _get_top_level_object(
        self, vmid: c_long, context: JABContext
    ) -> JABContext or None:
        try:
            result = self.bridge.getTopLevelObject(vmid, context)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'getTopLevelObject' error", exc_info=exc
            )
            return None
        else:
            return result

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

    def _is_same_object(
        self,
        vmid: c_long,
        expected: JABContext,
        actual: JABContext,
    ) -> bool:
        try:
            return self.bridge.isSameObject(vmid, expected, actual)
        except Exception as exc:
            self.log.error(
                "AccessBridge call function 'isSameObject' error",
                exc_info=exc,
            )
            return False

    def is_same_object(
        self, expected: JABContext, actual: JABContext
    ) -> bool:
        return self._is_same_object(self.ac.vmid, expected, actual)

    @focus_gained_fp
    def _gain_focus(self, vmid: c_long, event: JOBJECT64, source: JOBJECT64) -> None:
        hwnd = self._get_hwnd_from_accessible_context(vmid, source)
        self._release_java_object(vmid, event)

    def gain_focus(
        self, vmid: c_long, accessible_context: JOBJECT64, hwnd: HWND
    ) -> None:
        jab_context = JABContext(
            hwnd=hwnd, vmid=vmid, accessible_context=accessible_context
        )
        is_descendant_window = self.user.is_descendant_window(
            self.user.get_foreground_window(), jab_context.hwnd
        )
        if not is_descendant_window:
            return
        focus = self.handler.last_queue_focus
        is_same_object = (
            isinstance(focus, JABElement) and focus.jab_context == jab_context
        )
        if is_same_object:
            return
        focused_jab_element = JABElement(jab_context=jab_context)
