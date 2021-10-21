from ctypes import byref, c_int, c_long, c_short, c_wchar, create_string_buffer
from ctypes.wintypes import HWND
from pyjab.accessibleinfo import (
    AccessBridgeVersionInfo,
    AccessibleActions,
    AccessibleActionsToDo,
    AccessibleContextInfo,
    AccessibleHypertextInfo,
    AccessibleKeyBindings,
    AccessibleRelationInfo,
    AccessibleRelationSetInfo,
    AccessibleTableCellInfo,
    AccessibleTableInfo,
    AccessibleTextAttributesInfo,
    AccessibleTextInfo,
    AccessibleTextItemsInfo,
    AccessibleTextRectInfo,
    AccessibleTextSelectionInfo,
)
from pyjab.common.exceptions import JABException
from typing import Dict, TypeVar
from pyjab.common.logger import Logger
from pyjab.common.types import JOBJECT64, jint

_JABContext = TypeVar("_JABContext", bound="JABContext")


class JABContext(object):
    def __init__(
        self,
        hwnd: HWND = None,
        vmid: c_long = c_long(),
        accessible_context: JOBJECT64 = JOBJECT64(),
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

    # Gateway Functions
    """
    You typically call these functions before calling any other Java Access Bridge API function
    """

    def _is_java_window(self) -> bool:
        """
        Checks to see if the given window implements the Java Accessibility API.

        BOOL IsJavaWindow(HWND window);
        """
        result = self.bridge.isJavaWindow(self.hwnd)
        return bool(result)

    def _get_accessible_context_from_hwnd(self) -> _JABContext:
        """
        Gets the AccessibleContext and vmID values for the given window.
        Many Java Access Bridge functions require the AccessibleContext and vmID values.

        BOOL GetAccessibleContextFromHWND(HWND target, long *vmID, AccessibleContext *ac);
        """
        result = self.bridge.getAccessibleContextFromHWND(
            self.hwnd, byref(self.vmid), byref(self.accessible_context)
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("GetAccessibleContextFromHWND")
            )
        return result

    # Event Handling Functions
    """
    These take a function pointer to the function that will handle the event type. 
    When you no longer are interested in receiving those types of events, 
    call the function again, passing in the NULL value. 
    Find prototypes for the function pointers you need to pass into these functions 
    in the file AccessBridgeCallbacks.h. Java Access Bridge API Callbacks describes these prototypes.
    """

    # General Functions

    def _release_java_object(
        self, vmid: c_long = None, java_object: JOBJECT64 = None
    ) -> None:
        """
        Release the memory used by the Java object object,
        where object is an object returned to you by Java Access Bridge.
        Java Access Bridge automatically maintains a reference to all Java objects
        that it returns to you in the JVM so they are not garbage collected.
        To prevent memory leaks, call ReleaseJavaObject on all Java objects returned
        to you by Java Access Bridge once you are finished with them.

        void ReleaseJavaObject(long vmID, Java_Object object);

        Args:

            vmid: java vmid of specific java window
            job: accessible context of specifc java object

        Returns:

            None
        """
        vmid = self.get_vmid(vmid)
        java_object = self.get_accessible_context(java_object)
        result = self.bridge.releaseJavaObject(vmid, java_object)
        if result == 0:
            raise JABException(self.int_func_err_msg.format("ReleaseJavaObject"))

    def _get_version_info(self, vmid: c_long = None) -> AccessBridgeVersionInfo:
        """
        Gets the version information of the instance of Java Access Bridge instance your application is using.
        You can use this information to determine the available functionality of your version of Java Access Bridge.

        BOOL GetVersionInfo(long vmID, AccessBridgeVersionInfo *info);

        Note:To determine the version of the JVM, you need to pass in a valid vmID;
        otherwise all that is returned is the version of the WindowsAccessBridge.DLL file to which your application is connected.

        Args:

            vmid: java vmid of specific java window

        Returns:

            AccessBridgeVersionInfo:
                VMVersion
                bridgeJavaClassVersion
                bridgeJavaDLLVersion
                bridgeWinDLLVersion
        """
        vmid = self.get_vmid(vmid)
        info = AccessBridgeVersionInfo()
        result = self.bridge.getVersionInfo(vmid, byref(info))
        if result == 0:
            raise JABException(self.int_func_err_msg.format("getVersionInfo"))
        return info

    # Accessible Context Functions
    """
    These functions provide the core of the Java Accessibility API that is exposed by Java Access Bridge.

    The functions GetAccessibleContextAt and GetAccessibleContextWithFocus retrieve an AccessibleContext object, 
    which is a magic cookie (a Java Object reference) to an Accessible object and a JVM cookie. 
    You use these two cookies to reference objects through Java Access Bridge. 
    Most Java Access Bridge API functions require that you pass in these two parameters.

    Note:
    AccessibleContext objects are 64-bit references under 64-bit interprocess communication (which uses the windowsaccessbridge-64.dll file). 
    However, prior to JDK 9, AccessibleContext objects are 32-bit references under 32-bit interprocess communication (which uses the windowsaccessbridge.dll file without -32 or -64 in the file name). 
    Consequently, if you are converting your assistive technology applications to run on 64-bit Windows systems, then you need to recompile your assistive technology applications.

    The function GetAccessibleContextInfo returns detailed information about an AccessibleContext object belonging to the JVM. 
    In order to improve performance, the various distinct methods in the Java Accessibility API are collected together into a few routines in the Java Access Bridge API and returned in struct values. 
    The file AccessBridgePackages.h defines these struct values and Java Access Bridge API Callbacks describes them.

    The functions GetAccessibleChildFromContext and GetAccessibleParentFromContext enable you to walk the GUI component hierarchy, retrieving the nth child, or the parent, of a particular GUI object.
    """

    def _get_accessible_context_at(
        self,
        x: c_int,
        y: c_int,
        vmid: c_long = None,
        parent_acc: JOBJECT64 = None,
        new_acc: JOBJECT64 = JOBJECT64(),
    ) -> JOBJECT64:
        """
        Retrieves an AccessibleContext object of the window or object that is under the mouse pointer.

        BOOL GetAccessibleContextAt(long vmID, AccessibleContext acParent, jint x, jint y, AccessibleContext *ac)

        Args:

            x: position x of child accessible context
            y: position y of child accessible context
            vmid: java vmid of specific java window
            parent_acc: parent accessible context of specifc java object
            new_acc: new accessible context of specifc java object

        Returns:

            AccessibleContext: get Accessible Context success
            None: get Accessible Context failed
        """
        vmid = self.get_vmid(vmid)
        parent_acc = self.get_accessible_context(parent_acc)
        new_acc = new_acc if isinstance(new_acc, JOBJECT64) else JOBJECT64()
        result_acc = self.bridge.getAccessibleContextAt(
            vmid, parent_acc, x, y, byref(new_acc)
        )
        if not result_acc or not new_acc:
            raise JABException(self.int_func_err_msg.format("GetAccessibleContextAt"))
        if not self._is_same_object(new_acc, parent_acc):
            return new_acc
        elif new_acc != parent_acc:
            self._release_java_object(vmid, new_acc)
        return None

    def _get_accessible_context_with_focus(
        self,
        hwnd: HWND = None,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> JOBJECT64:
        """
        Retrieves an AccessibleContext object of the window or object that has the focus.

        BOOL GetAccessibleContextWithFocus(HWND window, long *vmID, AccessibleContext *ac);

        Args:

            hwnd: HWND of specific window
            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object

        Returns:

            AccessibleContext: get Accessible Context
        """
        hwnd = self.get_hwnd(hwnd)
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result_acc = self.bridge.getAccessibleContextWithFocus(
            hwnd, vmid, accessible_context
        )
        if not isinstance(result_acc, JOBJECT64):
            raise JABException(
                self.int_func_err_msg.format("GetAccessibleContextWithFocus")
            )
        return result_acc

    def _get_accessible_context_info(self, bridge) -> AccessibleContextInfo:
        """
        Retrieves an AccessibleContextInfo object of the AccessibleContext object ac.

        BOOL GetAccessibleContextInfo(long vmID, AccessibleContext ac, AccessibleContextInfo *info);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object

        Returns:

            AccessibleContextInfo
        """
        info = AccessibleContextInfo()
        result = bridge.getAccessibleContextInfo(
            self.vmid, self.accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("GetAccessibleContextInfo"))
        return info

    def _get_accessible_child_from_context(
        self, index: c_int, vmid: c_long = None, accessible_context: JOBJECT64 = None
    ) -> JOBJECT64:
        """
        Returns an AccessibleContext object that represents the nth child of the object ac, where n is specified by the value index.

        AccessibleContext GetAccessibleChildFromContext(long vmID, AccessibleContext ac, jint index);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object
            index: index of child accessible context

        Returns:
            AccessibleContext: get child accessible context success
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        child_acc = self.bridge.getAccessibleChildFromContext(
            vmid, accessible_context, index
        )
        if not isinstance(child_acc, JOBJECT64):
            raise JABException(
                self.int_func_err_msg.format("GetAccessibleChildFromContext")
            )
        return child_acc

    def _get_accessible_parent_from_context(
        self, vmid: c_long = None, accessible_context: JOBJECT64 = None
    ) -> JOBJECT64:
        """
        Returns an AccessibleContext object that represents the parent of object ac.

        AccessibleContext GetAccessibleParentFromContext(long vmID, AccessibleContext ac);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object

        Returns:
            AccessibleContext: get parent accessible context success
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        parent_acc = self.bridge.getAccessibleParentFromContext(
            vmid, accessible_context
        )
        if not isinstance(parent_acc, JOBJECT64):
            raise JABException(
                self.int_func_err_msg.format("GetAccessibleParentFromContext")
            )
        return parent_acc

    def _get_hwnd_from_accessible_context(
        self, vmid: c_long = None, accessible_context: JOBJECT64 = None
    ) -> HWND:
        """
        Returns the HWND from the AccessibleContextof a top-level window.

        HWND getHWNDFromAccessibleContext(long vmID, AccessibleContext ac);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object

        Returns:

            get HWND of current window
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        hwnd = self.bridge.getHWNDFromAccessibleContext(vmid, accessible_context)
        if isinstance(hwnd, HWND):
            self.vmids[self.jab_context.vmid] = hwnd
        else:
            hwnd = self.vmids.get(self.jab_context.vmid)
        return hwnd

    # Accessible Text Functions
    """
    These functions get AccessibleText information provided by the Java Accessibility API, 
    broken down into seven chunks for efficiency. 
    An AccessibleContext has AccessibleText information contained within it if you set the flag accessibleText in the AccessibleContextInfo data structure to TRUE. 
    The file AccessBridgePackages.h defines the struct values used in these functions Java Access Bridge API Callbacks describes them.
    """

    def _get_accessible_text_info(
        self,
        x: c_int,
        y: c_int,
        vmid: c_long = None,
        accessible_text: JOBJECT64 = None,
    ) -> AccessibleTextInfo:
        """
        BOOL GetAccessibleTextInfo(long vmID, AccessibleText at, AccessibleTextInfo *textInfo, jint x, jint y);
        """
        info = AccessibleTextInfo()
        vmid = self.get_vmid(vmid)
        accessible_text = self.get_accessible_context(accessible_text)
        result = self.bridge.getAccessibleTextInfo(
            vmid, accessible_text, byref(info), x, y
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("GetAccessibleTextInfo"))
        return info

    def _get_accessible_text_items(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_text: JOBJECT64 = None,
    ) -> AccessibleTextItemsInfo:
        """
        Get Accessible Text items information.

            letter: the index of text in Accessible text
            word: the index of word in Accessible text
            sentence: the all sentence in Accessible text

        BOOL GetAccessibleTextItems(long vmID, AccessibleText at, AccessibleTextItemsInfo *textItems, jint index);
        """
        info = AccessibleTextItemsInfo()
        vmid = self.get_vmid(vmid)
        accessible_text = self.get_accessible_context(accessible_text)
        result = self.bridge.getAccessibleTextItems(
            vmid, accessible_text, byref(info), index
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("GetAccessibleTextItems"))
        return info

    def _get_accessible_text_selection_info(
        self,
        vmid: c_long = None,
        accessible_text: JOBJECT64 = None,
    ) -> AccessibleTextSelectionInfo:
        """
        Get Accessible Text of selection information.

            selectionStartIndex: the selection text start index
            selectionEndIndex: the selection text end index
            selectedText: the selection text

        BOOL GetAccessibleTextSelectionInfo(long vmID, AccessibleText at, AccessibleTextSelectionInfo *textSelection);
        """
        info = AccessibleTextSelectionInfo()
        vmid = self.get_vmid(vmid)
        accessible_text = self.get_accessible_context(accessible_text)
        result = self.bridge.getAccessibleTextSelectionInfo(
            vmid, accessible_text, byref(info)
        )
        if result == 0:
            raise JABException(
                self.int_func_err_msg.format("GetAccessibleTextSelectionInfo")
            )
        return info

    def _get_accessible_text_attributes(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_text: JOBJECT64 = None,
    ) -> AccessibleTextAttributesInfo:
        """
        Get Accessible Text Attributes information.

        char *GetAccessibleTextAttributes(long vmID, AccessibleText at, jint index, AccessibleTextAttributesInfo *attributes);
        """
        info = AccessibleTextAttributesInfo()
        vmid = self.get_vmid(vmid)
        accessible_text = self.get_accessible_context(accessible_text)
        result = self.bridge.getAccessibleTextAttributes(
            vmid, accessible_text, index, byref(info)
        )
        if result == 0:
            raise JABException(
                self.int_func_err_msg.format("GetAccessibleTextAttributes")
            )
        return info

    def _get_accessible_text_rect(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_text: JOBJECT64 = None,
    ) -> AccessibleTextRectInfo:
        """
        Get Accessible Text Rect information.
            x
            y
            width
            height

        BOOL GetAccessibleTextRect(long vmID, AccessibleText at, AccessibleTextRectInfo *rectInfo, jint index);
        """
        info = AccessibleTextRectInfo()
        vmid = self.get_vmid(vmid)
        accessible_text = self.get_accessible_context(accessible_text)
        result = self.bridge.getAccessibleTextRect(
            vmid, accessible_text, byref(info), index
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("GetAccessibleTextRect"))
        return info

    def _get_accessible_text_range(
        self,
        start: c_int,
        end: c_int,
        vmid: c_long = None,
        accessible_text: JOBJECT64 = None,
    ) -> str:
        """
        Get a range of text; null if indicies are bogus

        BOOL GetAccessibleTextRange(long vmID, AccessibleText at, jint start, jint end, wchar_t *text, short len);
        """
        length = end + 1 - start
        if length <= 0:
            return u""
        # Use a string buffer, as from an unicode buffer, we can't get the raw data.
        buffer = create_string_buffer((length + 1) * 2)
        result = self.bridge.getAccessibleTextRange(
            vmid, accessible_text, start, end, buffer, length
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleTextRange"))
        # TODO: handle return text from raw bytes
        byte_numbers = length * 2
        raw_text = buffer.raw[:byte_numbers]
        if not any(raw_text):
            return ""
        try:
            text = raw_text.decode("utf_16", errors="surrogatepass")
        except UnicodeDecodeError:
            self.log.debug(
                "Error decoding text in {}, probably wrong encoding assumed or incomplete data".format(
                    buffer
                )
            )
            text = raw_text.decode("utf_16", errors="replace")
        return text

    def _get_accessible_text_line_bounds(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_text: JOBJECT64 = None,
    ) -> Dict:
        """
        BOOL GetAccessibleTextLineBounds(long vmID, AccessibleText at, jint index, jint *startIndex, jint *endIndex);
        """
        vmid = self.get_vmid(vmid)
        accessible_text = self.get_accessible_context(accessible_text)
        index = max(index, 0)
        output_text_line_bounds = "line bounds: start {}, end {}"
        self.log.debug("line bounds: index {}".format(index))
        # Java returns end as the last character, not end as past the last character
        start_line = c_int()
        end_line = c_int()
        self.bridge.getAccessibleTextLineBounds(
            vmid,
            accessible_text,
            index,
            byref(start_line),
            byref(end_line),
        )
        start = start_line.value
        end = end_line.value
        self.log.debug(output_text_line_bounds.format(start, end))
        if end < start or start < 0:
            # Invalid or empty line.
            return dict(start=0, end=-1)
        # OpenOffice sometimes returns offsets encompassing more than one line, so try to narrow them down.
        # Try to retract the end offset.
        self.bridge.getAccessibleTextLineBounds(
            vmid,
            accessible_text,
            end,
            byref(start_line),
            byref(end_line),
        )
        temp_start = max(start_line.value, 0)
        temp_end = max(end_line.value, 0)
        self.log.debug(output_text_line_bounds.format(temp_start, temp_end))
        if temp_start > (index + 1):
            # This line starts after the requested index, so set end to point at the line before.
            end = temp_start - 1
        # Try to retract the start.
        self.bridge.getAccessibleTextLineBounds(
            self.jab_context.vmid,
            self.jab_context.accessible_context,
            start,
            byref(start_line),
            byref(end_line),
        )
        temp_start = max(start_line.value, 0)
        temp_end = max(end_line.value, 0)
        self.log.debug(output_text_line_bounds.format(temp_start, temp_end))
        if temp_end < (index - 1):
            # This line ends before the requested index, so set start to point at the line after.
            start = temp_end + 1
        self.log.debug(
            "line bounds: returning {start}, {end}".format(start=start, end=end)
        )
        return dict(start=start, end=end)

    # Additional Text Functions

    def _select_text_range(
        self,
        start: c_int,
        end: c_int,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> bool:
        """
        Selects text between two indices. Selection includes the text at the start index and the text at the end index.
        Returns whether successful.

        BOOL selectTextRange(const long vmID, const AccessibleContext accessibleContext, const int startIndex, const int endIndex);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible text of specifc java object
            start: start index of the selection text
            end: end index of the selection text

        Returns:

            True: select action success
            False: select action failed
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        # TODO: func will not stop after do action on Java Object
        result = self.bridge.selectTextRange(
            vmid,
            accessible_context,
            start,
            end,
        )
        return bool(result)

    def _get_text_attributes_in_range(
        self,
        start: c_int,
        end: c_int,
        vmid: c_long,
        accessible_context: JOBJECT64,
    ) -> AccessibleTextAttributesInfo:
        """
        Get text attributes between two indices.
        The attribute list includes the text at the start index and the text at the end index.
        Returns whether successful.

        BOOL getTextAttributesInRange(const long vmID, const AccessibleContext accessibleContext, const int startIndex, const int endIndex, AccessibleTextAttributesInfo *attributes, short *len);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object
            start: start index of the text range
            end: end index of the text range
            info: accessible text attribuetes info
            length:

        Returns:

            True: get text attributes in range success
            False: get text attributes in range failed
        """
        info = AccessibleTextAttributesInfo()
        length = c_short()
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getTextAttributesInRange(
            vmid, accessible_context, start, end, byref(info), length
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("getTextAttributesInRange"))
        return info

    def _set_caret_position(
        self,
        position: c_int,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> bool:
        """
        Set the caret to a text position.
        Returns whether successful.

        BOOL setCaretPosition(const long vmID, const AccessibleContext accessibleContext, const int position);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object
            position: number of text position

        Returns:

            True: set the caret to a text position success
            False: set the caret to a text position failed
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.setCaretPosition(vmid, accessible_context, position)
        return bool(result)

    def _get_caret_location(
        self,
        index: c_int,
        vmid: c_long,
        accessible_context: JOBJECT64,
    ) -> Dict:
        """
        Gets the text caret location.

        BOOL getCaretLocation(long vmID, AccessibleContext ac, AccessibleTextRectInfo *rectInfo, jint index);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object
            info: accessible text rect info
            index: index of caret

        Returns:

            location of specific caret
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        info = AccessibleTextRectInfo()
        result = self.bridge.getCaretLocation(
            vmid, accessible_context, byref(info), index
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getCaretLocation"))
        return dict(x=info.x, y=info.y)

    def _set_text_contents(
        self,
        text: c_wchar,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> bool:
        """
        Sets editable text contents.
        The AccessibleContext must implement AccessibleEditableText and be editable.
        The maximum text length that can be set is MAX_STRING_SIZE - 1.
        Returns whether successful.

        BOOL setTextContents (const long vmID, const AccessibleContext accessibleContext, const wchar_t *text);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object
            text: text contents need to be set

        Returns:

            True: set editable text contents success
            False: set editable text contents failed
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        # TODO: func setTextContents not working
        result = self.bridge.setTextContents(vmid, accessible_context, text)
        return bool(result)

    # Accessible Table Functions

    def _get_accessible_table_info(
        self, vmid: c_long = None, accessible_context: JOBJECT64 = None
    ) -> AccessibleTableInfo:
        """
        Returns information about the table, for example, caption, summary, row and column count, and the AccessibleTable.

        BOOL getAccessibleTableInfo(long vmID, AccessibleContext acParent, AccessibleTableInfo *tableInfo);

        Args:

            vmid: java vmid of specific java window
            accessible_context: accessible context of specifc java object
            info: accessible table info

        Returns:

            AccessibleTableInfo
        """
        info = AccessibleTableInfo()
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getAccessibleTableInfo(
            vmid, accessible_context, byref(info)
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleTableInfo"))
        for item in [
            info.caption,
            info.summary,
            info.accessibleContext,
            info.accessibleTable,
        ]:
            item = (
                JABContext(
                    hwnd=self.jab_context.hwnd,
                    vmid=self.jab_context.vmid,
                    accessible_context=item,
                )
                if item
                else None
            )
        return info

    def _get_accessible_table_cell_info(
        self,
        row: c_int,
        column: c_int,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> AccessibleTableCellInfo:
        """
        Returns information about the specified table cell. The row and column specifiers are zero-based.

        BOOL getAccessibleTableCellInfo(long vmID, AccessibleTable accessibleTable, jint row, jint column, AccessibleTableCellInfo *tableCellInfo);

        Args:

            vmid: java vmid of specific java window
            accessible_table: accessible context of specifc java object
            row: index of row number for table cell
            column: index of column number for table cell
            info: accessible table cell info

        Returns:

            AccessibleTableCellInfo
        """
        info = AccessibleTableCellInfo()
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.getAccessibleTableCellInfo(
            vmid, accessible_table, row, column, byref(info)
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableCellInfo")
            )
        info.accessibleContext = (
            JABContext(
                hwnd=self.jab_context.hwnd,
                vmid=self.jab_context.vmid,
                accessible_context=info.accessibleContext,
            )
            if info.accessibleContext
            else None
        )
        return info

    def _get_accessible_table_row_header(
        self,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> AccessibleTableInfo:
        """
        Returns the table row headers of the specified table as a table.

        BOOL getAccessibleTableRowHeader(long vmID, AccessibleContext acParent, AccessibleTableInfo *tableInfo);
        """
        info = AccessibleTableInfo()
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getAccessibleTableRowHeader(
            vmid,
            self.jab_context.accessible_context,
            byref(info),
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableRowHeader")
            )
        for item in [
            info.caption,
            info.summary,
            info.accessibleContext,
            info.accessibleTable,
        ]:
            item = (
                JABContext(
                    hwnd=self.jab_context.hwnd,
                    vmid=self.jab_context.vmid,
                    accessible_context=item,
                )
                if item
                else None
            )
        return info

    def _get_accessible_table_column_header(
        self,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> AccessibleTableInfo:
        """
        Returns the table column headers of the specified table as a table.

        BOOL getAccessibleTableColumnHeader(long vmID, AccessibleContext acParent, AccessibleTableInfo *tableInfo);
        """
        info = AccessibleTableInfo()
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getAccessibleTableColumnHeader(
            vmid,
            accessible_context,
            byref(info),
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableColumnHeader")
            )
        for item in [
            info.caption,
            info.summary,
            info.accessibleContext,
            info.accessibleTable,
        ]:
            item = (
                JABContext(
                    hwnd=self.jab_context.hwnd,
                    vmid=self.jab_context.vmid,
                    accessible_context=item,
                )
                if item
                else None
            )
        return info

    def _get_accessible_table_row_description(
        self,
        row: c_int,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> JOBJECT64:
        """
        Returns the description of the specified row in the specified table.
        The row specifier is zero-based.

        AccessibleContext getAccessibleTableRowDescription(long vmID, AccessibleContext acParent, jint row);
        """
        vmid = self.get_vmid(vmid)
        hwnd = self.get_hwnd()
        accessible_context = self.get_accessible_context(accessible_context)
        result_acc = self.bridge.getAccessibleTableRowDescription(
            vmid,
            accessible_context,
            row,
        )
        if not result_acc:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableRowDescription")
            )
        return JABContext(hwnd, vmid, result_acc)

    def _get_accessible_table_column_description(
        self,
        column: c_int,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> JOBJECT64:
        """
        Returns the description of the specified column in the specified table.
        The column specifier is zero-based.

        AccessibleContext getAccessibleTableColumnDescription(long vmID, AccessibleContext acParent, jint column);
        """
        vmid = self.get_vmid(vmid)
        hwnd = self.get_hwnd()
        accessible_context = self.get_accessible_context(accessible_context)
        result_acc = self.bridge.getAccessibleTableColumnDescription(
            vmid,
            accessible_context,
            column,
        )
        if not result_acc:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableColumnDescription")
            )
        return JABContext(hwnd, vmid, result_acc)

    def _get_accessible_table_row_selection_count(
        self,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> int:
        """
        Returns how many rows in the table are selected.

        jint getAccessibleTableRowSelectionCount(long vmID, AccessibleTable table);
        """
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.getAccessibleTableRowSelectionCount(
            vmid,
            accessible_table,
        )
        if result != -1:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableRowSelectionCount")
            )
        return result

    def _is_accessible_table_row_selected(
        self,
        row: c_int,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> bool:
        """
        Returns true if the specified zero based row is selected.

        BOOL isAccessibleTableRowSelected(long vmID, AccessibleTable table, jint row);
        """
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.isAccessibleTableRowSelected(
            vmid,
            accessible_table,
            row,
        )
        return bool(result)

    def _get_accessible_table_row_selections(
        self,
        count: c_int,
        selections: c_int,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> bool:
        """
        Returns an array of zero based indices of the selected rows.

        BOOL getAccessibleTableRowSelections(long vmID, AccessibleTable table, jint count, jint *selections);
        """
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.getAccessibleTableRowSelections(
            vmid,
            accessible_table,
            count,
            selections,
        )
        return bool(result)

    def _get_accessible_table_column_selection_count(
        self,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> int:
        """
        Returns how many columns in the table are selected.

        jint getAccessibleTableColumnSelectionCount(long vmID, AccessibleTable table);
        """
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.getAccessibleTableColumnSelectionCount(
            vmid,
            accessible_table,
        )
        if result != -1:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableColumnSelectionCount")
            )
        return result

    def _is_accessible_table_column_selected(
        self,
        column: c_int,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> bool:
        """
        Returns true if the specified zero based column is selected.

        BOOL isAccessibleTableColumnSelected(long vmID, AccessibleTable table, jint column);
        """
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.isAccessibleTableColumnSelected(
            vmid,
            accessible_table,
            column,
        )
        return bool(result)

    def _get_accessible_table_column_selections(
        self,
        count: c_int,
        selections: c_int,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> bool:
        """
        Returns an array of zero based indices of the selected columns.

        BOOL getAccessibleTableColumnSelections(long vmID, AccessibleTable table, jint count, jint *selections);
        """
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.getAccessibleTableColumnSelections(
            vmid,
            accessible_table,
            count,
            selections,
        )
        return bool(result)

    def _get_accessible_table_row(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> int:
        """
        Returns the row number of the cell at the specified cell index.
        The values are zero based.

        jint getAccessibleTableRow(long vmID, AccessibleTable table, jint index);
        """
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.getAccessibleTableRow(
            vmid,
            accessible_table,
            index,
        )
        if result != -1:
            raise JABException(self.int_func_err_msg.format("getAccessibleTableRow"))
        return result

    def _get_accessible_table_column(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> int:
        """
        Returns the column number of the cell at the specified cell index.
        The values are zero based.

        jint getAccessibleTableColumn(long vmID, AccessibleTable table, jint index);
        """
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.getAccessibleTableColumn(
            vmid,
            accessible_table,
            index,
        )
        if result != -1:
            raise JABException(self.int_func_err_msg.format("getAccessibleTableColumn"))
        return result

    def _get_accessible_table_index(
        self,
        row: c_int,
        column: c_int,
        vmid: c_long = None,
        accessible_table: JOBJECT64 = None,
    ) -> int:
        """
        Returns the index in the table of the specified row and column offset.
        The values are zero based.

        jint getAccessibleTableIndex(long vmID, AccessibleTable table, jint row, jint column);
        """
        vmid = self.get_vmid(vmid)
        accessible_table = self.get_accessible_context(accessible_table)
        result = self.bridge.getAccessibleTableIndex(
            vmid,
            accessible_table,
            row,
            column,
        )
        if result != -1:
            raise JABException(self.int_func_err_msg.format("getAccessibleTableIndex"))
        return result

    # Accessible Relation Set Function

    def _get_accessible_relation_set(
        self,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> AccessibleRelationInfo:
        """
        Returns information about an object's related objects.

        BOOL getAccessibleRelationSet(long vmID, AccessibleContext accessibleContext, AccessibleRelationSetInfo *relationSetInfo);
        """
        info = AccessibleRelationSetInfo()
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getAccessibleRelationSet(
            vmid,
            accessible_context,
            byref(info),
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleRelationSet"))
        return info

    # Accessible Hypertext Functions

    def _get_accessible_hyper_text(
        self,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> AccessibleHypertextInfo:
        """
        Returns hypertext information associated with a component.

        BOOL getAccessibleHypertext(long vmID, AccessibleContext accessibleContext, AccessibleHypertextInfo *hypertextInfo);
        """
        info = AccessibleHypertextInfo()
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getAccessibleHypertext(
            vmid,
            accessible_context,
            byref(info),
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleHypertext"))
        return info

    def _active_accessible_hyper_link(
        self,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
        accessible_hyper_link: JOBJECT64 = None,
    ) -> bool:
        """
        Requests that a hyperlink be activated.

        BOOL activateAccessibleHyperlink(long vmID, AccessibleContext accessibleContext, AccessibleHyperlink accessibleHyperlink);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.activateAccessibleHyperlink(
            vmid,
            accessible_context,
            accessible_hyper_link,
        )
        return bool(result)

    def _get_accessible_hyper_link_count(
        self, vmid: c_long = None, accessible_hyper_text: JOBJECT64 = None
    ) -> int:
        """
        Returns the number of hyperlinks in a component.
        Maps to AccessibleHypertext.getLinkCount.
        Returns -1 on error.

        jint getAccessibleHyperlinkCount(const long vmID, const AccessibleHypertext hypertext);
        """
        vmid = self.get_vmid(vmid)
        result = self.bridge.getAccessibleHyperlinkCount(
            vmid,
            accessible_hyper_text,
        )
        if result == -1:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleHyperlinkCount")
            )
        return result

    def _get_accessible_hyper_text_ext(
        self,
        start: c_int,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> AccessibleHypertextInfo:
        """
        Iterates through the hyperlinks in a component.
        Returns hypertext information for a component starting at hyperlink index nStartIndex.
        No more than MAX_HYPERLINKS AccessibleHypertextInfo objects will be returned for each call to this method.
        Returns FALSE on error.

        BOOL getAccessibleHypertextExt(const long vmID, const AccessibleContext accessibleContext, const jint nStartIndex, AccessibleHypertextInfo *hypertextInfo);
        """
        info = AccessibleHypertextInfo()
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getAccessibleHypertextExt(
            vmid,
            accessible_context,
            start,
            byref(info),
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleHypertextExt")
            )
        return info

    def _get_accessible_hyper_link_index(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_hyper_text: JOBJECT64 = None,
    ) -> int:
        """
        Returns the index into an array of hyperlinks that is associated with a character index in document.
        Maps to AccessibleHypertext.getLinkIndex.
        Returns -1 on error.

        jint getAccessibleHypertextLinkIndex(const long vmID, const AccessibleHypertext hypertext, const jint nIndex);
        """
        vmid = self.get_vmid(vmid)
        result = self.bridge.getAccessibleHypertextLinkIndex(
            vmid,
            accessible_hyper_text,
            index,
        )
        if result == -1:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleHypertextLinkIndex")
            )
        return result

    def _get_accessible_hyper_link(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_hyper_text: JOBJECT64 = None,
    ) -> bool:
        """
        Returns the nth hyperlink in a document.
        Maps to AccessibleHypertext.getLink.
        Returns FALSE on error.

        BOOL getAccessibleHyperlink(const long vmID, const AccessibleHypertext hypertext, const jint nIndex, AccessibleHypertextInfo *hyperlinkInfo);
        """
        info = AccessibleHypertextInfo()
        vmid = self.get_vmid(vmid)
        result = self.bridge.getAccessibleHyperlink(
            vmid,
            accessible_hyper_text,
            index,
            byref(info),
        )
        return bool(result)

    # Accessible Key Binding Function

    def _get_accessible_key_bindings(
        self,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> bool:
        """
        Returns a list of key bindings associated with a component.

        BOOL getAccessibleKeyBindings(long vmID, AccessibleContext accessibleContext, AccessibleKeyBindings *keyBindings);
        """
        bindings = AccessibleKeyBindings()
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getAccessibleKeyBindings(
            vmid,
            accessible_context,
            byref(bindings),
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleHyperlink"))
        return bindings

    # Accessible Icon Function
    # TODO: get_accessible_icons func need fix
    def _get_accessible_icons(
        self,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
        accessible_icons: JOBJECT64 = None,
    ) -> bool:
        """
        Returns a list of icons associate with a component.

        BOOL getAccessibleIcons(long vmID, AccessibleContext accessibleContext, AccessibleIcons *icons);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getAccessibleIcons(
            vmid, accessible_context, accessible_icons
        )
        return bool(result)

    # Accessible Action Functions

    def _get_accessible_actions(
        self,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
        actions: AccessibleActions = None,
    ) -> list:
        """
        Returns a list of actions that a component can perform.

        BOOL getAccessibleActions(long vmID, AccessibleContext accessibleContext, AccessibleActions *actions);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getAccessibleActions(vmid, accessible_context, actions)
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleActions"))
        return actions.actionInfo[: actions.actionsCount]

    def _do_accessible_actions(
        self,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
        actions_todo: AccessibleActionsToDo = None,
        failure: jint = None,
    ) -> bool:
        """
        Request that a list of AccessibleActions be performed by a component.
        Returns TRUE if all actions are performed.
        Returns FALSE when the first requested action fails in which case "failure" contains the index of the action that failed.

        BOOL doAccessibleActions(long vmID, AccessibleContext accessibleContext, AccessibleActionsToDo *actionsToDo, jint *failure);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        actions_todo = (
            actions_todo
            if isinstance(actions_todo, AccessibleActionsToDo)
            else AccessibleActionsToDo(
                actionsCount=1, actions=(self._get_accessible_actions(),)
            )
        )
        failure = failure if isinstance(failure, jint) else jint()
        result = self.bridge.doAccessibleActions(
            vmid, accessible_context, actions_todo, failure
        )
        return result

    # Utility Functions

    def _is_same_object(
        self,
        jobject1: JOBJECT64,
        jobject2: JOBJECT64,
        vmid: c_long = None,
    ) -> bool:
        """
        Returns whether two object references refer to the same object.

        BOOL IsSameObject(long vmID, JOBJECT64 obj1, JOBJECT64 obj2);
        """
        vmid = self.get_vmid(vmid)
        result = self.bridge.isSameObject(vmid, jobject1, jobject2)
        return bool(result)

    def _get_parent_with_role(
        self,
        role: c_wchar,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> JOBJECT64:
        """
        Returns the AccessibleContext with the specified role that is the ancestor of a given object.
        The role is one of the role strings defined in Java Access Bridge API Data Structures.
        If there is no ancestor object that has the specified role, returns (AccessibleContext)0.

        AccessibleContext getParentWithRole (const long vmID, const AccessibleContext accessibleContext, const wchar_t *role);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getParentWithRole(vmid, accessible_context, role)
        if not result:
            raise JABException(self.int_func_err_msg.format("getParentWithRole"))
        return result

    def _get_parent_with_role_else_root(
        self,
        role: c_wchar,
        vmid: c_long = None,
        accessible_context: JOBJECT64 = None,
    ) -> JOBJECT64:
        """
        Returns the AccessibleContext with the specified role that is the ancestor of a given object.
        The role is one of the role strings defined in Java Access Bridge API Data Structures.
        If an object with the specified role does not exist, returns the top level object for the Java window.
        Returns (AccessibleContext)0 on error.

        AccessibleContext getParentWithRoleElseRoot (const long vmID, const AccessibleContext accessibleContext, const wchar_t *role);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getParentWithRoleElseRoot(vmid, accessible_context, role)
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getParentWithRoleElseRoot")
            )
        return result

    def _get_top_level_object(
        self, vmid: c_long = None, accessible_context: JOBJECT64 = None
    ) -> JOBJECT64:
        """
        Returns the AccessibleContext for the top level object in a Java window.
        This is same AccessibleContext that is obtained from GetAccessibleContextFromHWND for that window.
        Returns (AccessibleContext)0 on error.

        AccessibleContext getTopLevelObject (const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getTopLevelObject(vmid, accessible_context)
        if not result:
            raise JABException(self.int_func_err_msg.format("getTopLevelObject"))
        return result

    def _get_object_depth(
        self, vmid: c_long = None, accessible_context: JOBJECT64 = None
    ) -> int:
        """
        Returns how deep in the object hierarchy a given object is.
        The top most object in the object hierarchy has an object depth of 0.
        Returns -1 on error.

        int getObjectDepth (const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        object_depth = self.bridge.getObjectDepth(vmid, accessible_context)
        if object_depth == -1:
            raise JABException(self.int_func_err_msg.format("getObjectDepth"))
        return object_depth

    def _get_active_descendent(
        self, vmid: c_long = None, accessible_context: JOBJECT64 = None
    ) -> JOBJECT64:
        """
        Returns the AccessibleContext of the current ActiveDescendent of an object.
        This method assumes the ActiveDescendent is the component that is currently selected in a container object.
        Returns (AccessibleContext)0 on error or if there is no selection.

        AccessibleContext getActiveDescendent (const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getActiveDescendent(vmid, accessible_context)
        if not result:
            raise JABException(self.int_func_err_msg.format("getActiveDescendent"))
        return result

    def _request_focus(
        self, vmid: c_long = None, accessible_context: JOBJECT64 = None
    ) -> bool:
        """
        Request focus for a component.
        Returns whether successful.

        BOOL requestFocus(const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        is_focused = self.bridge.requestFocus(vmid, accessible_context)
        return bool(is_focused)

    def _get_visible_children_count(
        self, vmid: c_long = None, accessible_context: JOBJECT64 = None
    ) -> int:
        """
        Gets the visible children of an AccessibleContext.
        Returns whether successful.

        int getVisibleChildrenCount(const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = self.get_vmid(vmid)
        accessible_context = self.get_accessible_context(accessible_context)
        result = self.bridge.getVisibleChildrenCount(vmid, accessible_context)
        return result

    def _get_events_waiting(self) -> int:
        """
        Gets the number of events waiting to fire.

        int getEventsWaiting();
        """
        return self.bridge.getEventsWaiting()

    # Accessible Value Functions
    """
    These functions get AccessibleValue information provided by the Java Accessibility API. 
    An AccessibleContext object has AccessibleValue information contained within it if the flag accessibleValue in the AccessibleContextInfo data structure is set to TRUE. 
    The values returned are strings (char *value) because there is no way to tell in advance if the value is an integer, a floating point value, or some other object that subclasses the Java language construct java.lang.Number.
    """

    def _get_current_accessible_value_from_context(
        self,
        vmid: c_long = None,
        accessible_value: JOBJECT64 = None,
        unicode_buffer: c_wchar = None,
        length: c_short = None,
    ) -> str:
        """
        Get the value of this object as a Number. If the value has not been set, the return value will be null.

        BOOL GetCurrentAccessibleValueFromContext(long vmID, AccessibleValue av, wchar_t *value, short len);
        """
        vmid = self.get_vmid(vmid)
        accessible_value = self.get_accessible_context(accessible_value)
        unicode_buffer = self.get_unicode_buffer(unicode_buffer)
        length = self.get_length(length)
        result = self.GetCurrentAccessibleValueFromContext(
            vmid, accessible_value, unicode_buffer, length
        )
        return result

    def _get_maximum_accessible_value_from_context(
        self,
        vmid: c_long = None,
        accessible_value: JOBJECT64 = None,
        unicode_buffer: c_wchar = None,
        length: c_short = None,
    ):
        """
        Get the maximum value of this object as a Number.
        Returns Maximum value of the object; null if this object does not have a maximum value

        BOOL GetMaximumAccessibleValueFromContext(long vmID, AccessibleValue av, wchar_ *value, short len);
        """
        vmid = self.get_vmid(vmid)
        accessible_value = self.get_accessible_context(accessible_value)
        unicode_buffer = self.get_unicode_buffer(unicode_buffer)
        length = self.get_length(length)
        result = self.GetMaximumAccessibleValueFromContext(
            vmid, accessible_value, unicode_buffer, length
        )
        return result

    def _get_minimum_accessible_value_from_context(
        self,
        vmid: c_long = None,
        accessible_value: JOBJECT64 = None,
        unicode_buffer: c_wchar = None,
        length: c_short = None,
    ):
        """
        Get the minimum value of this object as a Number.
        Returns Minimum value of the object; null if this object does not have a minimum value

        BOOL GetMinimumAccessibleValueFromContext(long vmID, AccessibleValue av, wchar_ *value, short len);
        """
        vmid = self.get_vmid(vmid)
        accessible_value = self.get_accessible_context(accessible_value)
        unicode_buffer = self.get_unicode_buffer(unicode_buffer)
        length = self.get_length(length)
        result = self.GetMinimumAccessibleValueFromContext(
            vmid, accessible_value, unicode_buffer, length
        )
        return result

    # Accessible Selection Functions
    """
    These functions get and manipulate AccessibleSelection information provided by the Java Accessibility API. 
    An AccessibleContext has AccessibleSelection information contained within it if the flag accessibleSelection in the AccessibleContextInfo data structure is set to TRUE. 
    The AccessibleSelection support is the first place where the user interface can be manipulated, as opposed to being queries, through adding and removing items from a selection. 
    Some of the functions use an index that is in child coordinates, while other use selection coordinates. 
    For example, add to remove from a selection by passing child indices (for example, add the fourth child to the selection). 
    On the other hand, enumerating the selected children is done in selection coordinates (for example, get the AccessibleContext of the first object selected).
    """

    def _add_accessible_selection_from_context(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_selection: JOBJECT64 = None,
    ) -> None:
        """
        Adds the specified Accessible child of the object to the object's selection.
        If the object supports multiple selections, the specified child is added to any existing selection, otherwise it replaces any existing selection in the object.
        If the specified child is already selected, this method has no effect.

        void AddAccessibleSelectionFromContext(long vmID, AccessibleSelection as, int i);
        """
        vmid = self.get_vmid(vmid)
        accessible_selection = self.get_accessible_context(accessible_selection)
        self.bridge.AddAccessibleSelectionFromContext(vmid, accessible_selection, index)

    def _clear_accessible_selection_from_context(
        self,
        vmid: c_long = None,
        accessible_selection: JOBJECT64 = None,
    ) -> None:
        """
        Clears the selection in the object, so that no children in the object are selected.

        void ClearAccessibleSelectionFromContext(long vmID, AccessibleSelection as);
        """
        vmid = self.get_vmid(vmid)
        accessible_selection = self.get_accessible_context(accessible_selection)
        self.bridge.ClearAccessibleSelectionFromContext(vmid, accessible_selection)

    def _get_accessible_selection_from_context(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_selection: JOBJECT64 = None,
    ) -> JOBJECT64:
        """
        Returns an Accessible representing the specified selected child of the object.
        If there isn't a selection, or there are fewer children selected than the integer passed in, the return value will be null.
        Note that the index represents the i-th selected child, which is different from the i-th child.

        jobject GetAccessibleSelectionFromContext(long vmID, AccessibleSelection as, int i);
        """
        vmid = self.get_vmid(vmid)
        accessible_selection = self.get_accessible_context(accessible_selection)
        selected_object = self.bridge.GetAccessibleSelectionFromContext(
            vmid, accessible_selection, index
        )
        if not isinstance(selected_object, JOBJECT64):
            raise JABException(
                self.int_func_err_msg.format("GetAccessibleSelectionFromContext")
            )
        return selected_object

    def _get_accessible_selection_count_from_context(
        self,
        vmid: c_long = None,
        accessible_selection: JOBJECT64 = None,
    ) -> int:
        """
        Returns the number of Accessible children currently selected.
        If no children are selected, the return value will be 0.

        int GetAccessibleSelectionCountFromContext(long vmID, AccessibleSelection as);
        """
        vmid = self.get_vmid(vmid)
        accessible_selection = self.get_accessible_context(accessible_selection)
        selection_count = self.bridge.GetAccessibleSelectionCountFromContext(
            vmid, accessible_selection
        )
        return selection_count

    def _is_accessible_child_selected_from_context(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_selection: JOBJECT64 = None,
    ) -> bool:
        """
        Determines if the current child of this object is selected.

        BOOL IsAccessibleChildSelectedFromContext(long vmID, AccessibleSelection as, int i);
        """
        vmid = self.get_vmid(vmid)
        accessible_selection = self.get_accessible_context(accessible_selection)
        is_selected = self.bridge.IsAccessibleChildSelectedFromContext(
            vmid, accessible_selection, index
        )
        return bool(is_selected)

    def _remove_accessible_selection_from_context(
        self,
        index: c_int,
        vmid: c_long = None,
        accessible_selection: JOBJECT64 = None,
    ) -> None:
        """
        Removes the specified child of the object from the object's selection.
        If the specified item isn't currently selected, this method has no effect.

        void RemoveAccessibleSelectionFromContext(long vmID, AccessibleSelection as, int i);
        """
        vmid = self.get_vmid(vmid)
        accessible_selection = self.get_accessible_context(accessible_selection)
        self.bridge.RemoveAccessibleSelectionFromContext(
            vmid, accessible_selection, index
        )

    def _select_all_accessible_selection_from_context(
        self,
        vmid: c_long = None,
        accessible_selection: JOBJECT64 = None,
    ) -> None:
        """
        Causes every child of the object to be selected if the object supports multiple selections.

        void SelectAllAccessibleSelectionFromContext(long vmID, AccessibleSelection as);
        """
        vmid = self.get_vmid(vmid)
        accessible_selection = self.get_accessible_context(accessible_selection)
        self.bridge.SelectAllAccessibleSelectionFromContext(vmid, accessible_selection)
