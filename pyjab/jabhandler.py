from ctypes import (
    CDLL,
    c_int,
    c_long,
    c_short,
    c_wchar,
    create_string_buffer,
    create_unicode_buffer,
)
from ctypes import byref
from ctypes.wintypes import HWND
from pyjab.accessibles.selection import AccessibleSelection
from pyjab.accessibles.value import AccessibleValue
from pyjab.config import SHORT_STRING_SIZE
from pyjab.common.exceptions import JavaAccessBridgeInternalException
from pyjab.accessibles.actionstodo import AccessibleActionsToDo
from pyjab.accessibles.icons import AccessibleIcons
from pyjab.accessibles.context import AccessibleContext
from pyjab.accessibles.hypertext import AccessibleHypertext
from pyjab.accessibles.hyperlink import AccessibleHyperlink
from pyjab.jabcontext import JABContext
from typing import Optional, Tuple
from pyjab.accessibleinfo import (
    AccessBridgeVersionInfo,
    AccessibleActions,
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
from pyjab.jabelement import JABElement
from pyjab.common.eventhandler import EvenetHandler
from pyjab.common.winuser import WinUser
from pyjab.common.logger import Logger
from pyjab.common.service import Service
from pyjab.common.types import JOBJECT64, jint
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
            self.get_accessible_context_from_hwnd(hwnd, vmid, ac)
            vmid = vmid.value
            global VMIDS_OF_HWND
            VMIDS_OF_HWND[vmid] = hwnd
        elif vmid and not hwnd:
            hwnd = self._get_hwnd_from_accessible_context(vmid, ac)
        ac.hwnd = hwnd
        ac.vmid = vmid
        ac.ac = ac

    # Gateway Functions
    """
    You typically call these functions before calling any other Java Access Bridge API function
    """

    def is_java_window(self) -> bool:
        """
        Checks to see if the given window implements the Java Accessibility API.

        BOOL IsJavaWindow(HWND window);
        """
        result = False
        result = self.bridge.isJavaWindow(self.ac.hwnd)
        return bool(result)

    def get_accessible_context_from_hwnd(
        self, hwnd: HWND, vmid: c_long, context: JABContext
    ) -> JABContext:
        """
        Gets the AccessibleContext and vmID values for the given window.
        Many Java Access Bridge functions require the AccessibleContext and vmID values.

        BOOL GetAccessibleContextFromHWND(HWND target, long *vmID, AccessibleContext *ac);
        """
        hwnd = hwnd if isinstance(hwnd, HWND) else self.ac.hwnd
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.getAccessibleContextFromHWND(
            hwnd, byref(vmid), byref(context)
        )
        if result:
            return JABContext(hwnd=hwnd, vmid=vmid, ac=context)

    # Event Handling Functions
    """
    These take a function pointer to the function that will handle the event type. 
    When you no longer are interested in receiving those types of events, 
    call the function again, passing in the NULL value. 
    Find prototypes for the function pointers you need to pass into these functions 
    in the file AccessBridgeCallbacks.h. Java Access Bridge API Callbacks describes these prototypes.
    """

    # General Functions

    def release_java_object(
        self, vmid: c_long = None, context: JABContext = None
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
            context: accessible context of specifc java object

        Returns:

            None
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.releaseJavaObject(vmid, context)

    def get_version_info(self, vmid: c_long = None) -> AccessBridgeVersionInfo:
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
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        info = AccessBridgeVersionInfo()
        result = self.bridge.getVersionInfo(vmid, byref(info))
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

    def get_accessible_context_at(
        self,
        x: c_int,
        y: c_int,
        vmid: c_long = None,
        parent: JABContext = None,
        child: JABContext = None,
    ) -> JABContext or None:
        """
        Retrieves an AccessibleContext object of the window or object that is under the mouse pointer.

        BOOL GetAccessibleContextAt(long vmID, AccessibleContext acParent, jint x, jint y, AccessibleContext *ac)

        Args:

            x: position x of child accessible context
            y: position y of child accessible context
            vmid: java vmid of specific java window
            parent: parent accessible context of specifc java object
            child: child accessible context of specifc java object

        Returns:

            AccessibleContext: get Accessible Context success
            None: get Accessible Context failed
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        parent = parent if isinstance(parent, JABContext) else self.ac
        child = child if isinstance(child, JABContext) else JOBJECT64()
        result = self.bridge.GetAccessibleContextAt(vmid, parent, x, y, byref(child))
        if not result or not child:
            return None
        if not self.is_same_object(child, parent):
            return JABContext(self.ac.hwnd, self.vmid, self.ac.ac)
        else:
            self.release_java_object()
        return None

    def get_accessible_context_with_focus(
        self, hwnd: HWND = None, vmid: c_long = None, context: JABContext = None
    ) -> JABContext:
        """
        Retrieves an AccessibleContext object of the window or object that has the focus.

        BOOL GetAccessibleContextWithFocus(HWND window, long *vmID, AccessibleContext *ac);

        Args:

            hwnd: HWND of specific window
            vmid: java vmid of specific java window
            context: accessible context of specifc java object

        Returns:

            AccessibleContext: get Accessible Context
        """
        hwnd = hwnd if isinstance(hwnd, HWND) else self.ac.hwnd
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.GetAccessibleContextWithFocus(hwnd, vmid, context)

    def get_accessible_context_info(
        self, vmid: c_long = None, context: JABContext = None
    ) -> AccessibleContextInfo:
        """
        Retrieves an AccessibleContextInfo object of the AccessibleContext object ac.

        BOOL GetAccessibleContextInfo(long vmID, AccessibleContext ac, AccessibleContextInfo *info);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object

        Returns:

            AccessibleContextInfo
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        info = AccessibleContextInfo()
        result = self.bridge.GetAccessibleContextInfo(vmid, context, byref(info))
        return info

    def get_accessible_child_from_context(
        self, index: c_int, vmid: c_long = None, context: JABContext = None
    ) -> JABContext:
        """
        Returns an AccessibleContext object that represents the nth child of the object ac, where n is specified by the value index.

        AccessibleContext GetAccessibleChildFromContext(long vmID, AccessibleContext ac, jint index);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            index: index of child accessible context

        Returns:
            AccessibleContext: get child accessible context success
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        ac = self.bridge.GetAccessibleChildFromContext(vmid, context, index)
        return JABContext(self.ac.hwnd, vmid, ac)

    def get_accessible_parent_from_context(
        self, vmid: c_long = None, context: JABContext = None
    ) -> JABContext:
        """
        Returns an AccessibleContext object that represents the parent of object ac.

        AccessibleContext GetAccessibleParentFromContext(long vmID, AccessibleContext ac);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object

        Returns:
            AccessibleContext: get parent accessible context success
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        ac = self.bridge.GetAccessibleParentFromContext(vmid, context)
        return JABContext(self.ac.hwnd, vmid, ac)

    def get_hwnd_from_accessible_context(
        self, vmid: c_long = None, context: JABContext = None
    ) -> HWND:
        """
        Returns the HWND from the AccessibleContextof a top-level window.

        HWND getHWNDFromAccessibleContext(long vmID, AccessibleContext ac);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object

        Returns:

            HWND: get HWND of current window success
            None:  get HWND of current window failed
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        hwnd = self.bridge.getHWNDFromAccessibleContext(vmid, context)
        if hwnd:
            global VMIDS_OF_HWND
            VMIDS_OF_HWND[self.ac.vmid] = hwnd
        else:
            hwnd = VMIDS_OF_HWND.get(self.ac.vmid)
        return hwnd

    # Accessible Text Functions
    """
    These functions get AccessibleText information provided by the Java Accessibility API, 
    broken down into seven chunks for efficiency. 
    An AccessibleContext has AccessibleText information contained within it if you set the flag accessibleText in the AccessibleContextInfo data structure to TRUE. 
    The file AccessBridgePackages.h defines the struct values used in these functions Java Access Bridge API Callbacks describes them.
    """

    def get_accessible_text_info(
        self,
        x: c_int,
        y: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleTextInfo:
        """
        BOOL GetAccessibleTextInfo(long vmID, AccessibleText at, AccessibleTextInfo *textInfo, jint x, jint y);
        """
        info = AccessibleTextInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.GetAccessibleTextInfo(vmid, context, byref(info), x, y)
        return info

    def get_accessible_text_items(
        self,
        index: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleTextItemsInfo:
        """
        BOOL GetAccessibleTextItems(long vmID, AccessibleText at, AccessibleTextItemsInfo *textItems, jint index);
        """
        info = AccessibleTextItemsInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.GetAccessibleTextItems(vmid, context, byref(info), index)
        return info

    def get_accessible_text_selection_info(
        self,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleTextSelectionInfo:
        """
        BOOL GetAccessibleTextSelectionInfo(long vmID, AccessibleText at, AccessibleTextSelectionInfo *textSelection);
        """
        info = AccessibleTextSelectionInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.GetAccessibleTextSelectionInfo(vmid, context, byref(info))
        return info

    def get_accessible_text_attributes(
        self,
        index: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleTextAttributesInfo:
        """
        char *GetAccessibleTextAttributes(long vmID, AccessibleText at, jint index, AccessibleTextAttributesInfo *attributes);
        """
        info = AccessibleTextAttributesInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.GetAccessibleTextAttributes(
            vmid, context, index, byref(info)
        )
        return info

    def get_accessible_text_rect(
        self,
        index: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleTextRectInfo:
        """
        BOOL GetAccessibleTextRect(long vmID, AccessibleText at, AccessibleTextRectInfo *rectInfo, jint index);
        """
        info = AccessibleTextRectInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.GetAccessibleTextRect(vmid, context, byref(info), index)
        return info

    def get_accessible_text_range(
        self,
        start: c_int,
        end: c_int,
        vmid: c_long = None,
        context: JABContext = None,
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
        # TODO: handle return text from raw bytes
        return self.bridge.getAccessibleTextRange(
            vmid, context, start, end, buffer, length
        )

    def get_accessible_text_line_bounds(
        self,
        index: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> Tuple:
        """
        BOOL GetAccessibleTextLineBounds(long vmID, AccessibleText at, jint index, jint *startIndex, jint *endIndex);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        index = max(index, 0)
        output_text_line_bounds = "line bounds: start {}, end {}"
        self.log.debug("line bounds: index {}".format(index))
        # Java returns end as the last character, not end as past the last character
        start_line = c_int()
        end_line = c_int()
        self.bridge.getAccessibleTextLineBounds(
            vmid,
            context,
            index,
            byref(start_line),
            byref(end_line),
        )
        start = start_line.value
        end = end_line.value
        self.log.debug(output_text_line_bounds.format(start, end))
        if end < start or start < 0:
            # Invalid or empty line.
            return (0, -1)
        # OpenOffice sometimes returns offsets encompassing more than one line, so try to narrow them down.
        # Try to retract the end offset.
        self.bridge.getAccessibleTextLineBounds(
            vmid,
            context,
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
            self.ac.vmid,
            self.ac.ac,
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
        return start, end

    # Additional Text Functions

    def select_text_range(
        self,
        start: c_int,
        end: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> bool:
        """
        Selects text between two indices. Selection includes the text at the start index and the text at the end index.
        Returns whether successful.

        BOOL selectTextRange(const long vmID, const AccessibleContext accessibleContext, const int startIndex, const int endIndex);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            start: start index of the selection text
            end: end index of the selection text

        Returns:

            True: select action success
            False: select action failed
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.selectTextRange(
            vmid,
            context,
            byref(start),
            byref(end),
        )
        return bool(result)

    def get_text_attributes_in_range(
        self,
        start: c_int,
        end: c_int,
        vmid: c_long,
        context: JABContext,
    ) -> AccessibleTextAttributesInfo:
        """
        Get text attributes between two indices.
        The attribute list includes the text at the start index and the text at the end index.
        Returns whether successful.

        BOOL getTextAttributesInRange(const long vmID, const AccessibleContext accessibleContext, const int startIndex, const int endIndex, AccessibleTextAttributesInfo *attributes, short *len);

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
        info = AccessibleTextAttributesInfo()
        length = c_short()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.getTextAttributesInRange(
            vmid, context, start, end, byref(info), length
        )
        return info

    def set_caret_position(
        self,
        position: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> bool:
        """
        Set the caret to a text position.
        Returns whether successful.

        BOOL setCaretPosition(const long vmID, const AccessibleContext accessibleContext, const int position);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            position: number of text position

        Returns:

            True: set the caret to a text position success
            False: set the caret to a text position failed
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.setCaretPosition(vmid, context, position)
        return bool(result)

    def get_caret_location(
        self,
        index: c_int,
        vmid: c_long,
        context: JABContext,
    ) -> Tuple:
        """
        Gets the text caret location.

        BOOL getCaretLocation(long vmID, AccessibleContext ac, AccessibleTextRectInfo *rectInfo, jint index);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            info: accessible text rect info
            index: index of caret

        Returns:

            location of specific caret
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        info = AccessibleTextRectInfo()
        result = self.bridge.getCaretLocation(vmid, context, byref(info), index)
        return info.x, info.y

    def set_text_contents(
        self,
        text: c_wchar,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> bool:
        """
        Sets editable text contents.
        The AccessibleContext must implement AccessibleEditableText and be editable.
        The maximum text length that can be set is MAX_STRING_SIZE - 1.
        Returns whether successful.

        BOOL setTextContents (const long vmID, const AccessibleContext accessibleContext, const wchar_t *text);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            text: text contents need to be set

        Returns:

            True: set editable text contents success
            False: set editable text contents failed
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.setTextContents(vmid, context, text)
        return bool(result)

    # Accessible Table Functions

    def get_accessible_table_info(
        self, vmid: c_long = None, context: JABContext = None
    ) -> AccessibleTableInfo:
        """
        Returns information about the table, for example, caption, summary, row and column count, and the AccessibleTable.

        BOOL getAccessibleTableInfo(long vmID, AccessibleContext acParent, AccessibleTableInfo *tableInfo);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            info: accessible table info

        Returns:

            AccessibleTableInfo
        """
        info = AccessibleTableInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        if self.bridge.getAccessibleTableInfo(vmid, context, byref(info)):
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

    def get_accessible_table_cell_info(
        self,
        row: c_int,
        column: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleTableCellInfo:
        """
        Returns information about the specified table cell. The row and column specifiers are zero-based.

        BOOL getAccessibleTableCellInfo(long vmID, AccessibleTable accessibleTable, jint row, jint column, AccessibleTableCellInfo *tableCellInfo);

        Args:

            vmid: java vmid of specific java window
            context: accessible context of specifc java object
            row: index of row number for table cell
            column: index of column number for table cell
            info: accessible table cell info

        Returns:

            AccessibleTableCellInfo
        """
        info = AccessibleTableCellInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        if self.bridge.getAccessibleTableCellInfo(
            vmid, context, row, column, byref(info)
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

    def get_accessible_table_row_header(
        self,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleTableInfo:
        """
        Returns the table row headers of the specified table as a table.

        BOOL getAccessibleTableRowHeader(long vmID, AccessibleContext acParent, AccessibleTableInfo *tableInfo);
        """
        info = AccessibleTableInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        if self.bridge.getAccessibleTableRowHeader(
            vmid,
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

    def get_accessible_table_column_header(
        self,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleTableInfo:
        """
        Returns the table column headers of the specified table as a table.

        BOOL getAccessibleTableColumnHeader(long vmID, AccessibleContext acParent, AccessibleTableInfo *tableInfo);
        """
        info = AccessibleTableInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        if self.bridge.getAccessibleTableColumnHeader(
            vmid,
            context,
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

    def get_accessible_table_row_description(
        self,
        row: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> str:
        """
        Returns the description of the specified row in the specified table.
        The row specifier is zero-based.

        AccessibleContext getAccessibleTableRowDescription(long vmID, AccessibleContext acParent, jint row);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.getAccessibleTableRowDescription(
            vmid,
            context,
            row,
        )

    def get_accessible_table_column_description(
        self,
        column: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> str:
        """
        Returns the description of the specified column in the specified table.
        The column specifier is zero-based.

        AccessibleContext getAccessibleTableColumnDescription(long vmID, AccessibleContext acParent, jint column);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.getAccessibleTableColumnDescription(
            vmid,
            context,
            column,
        )

    def get_accessible_table_row_selection_count(
        self,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> int:
        """
        Returns how many rows in the table are selected.

        jint getAccessibleTableRowSelectionCount(long vmID, AccessibleTable table);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.getAccessibleTableRowSelectionCount(
            vmid,
            context,
        )
        if isinstance(result, int) and result != -1:
            return result

    def is_accessible_table_row_selected(
        self,
        row: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> bool:
        """
        Returns true if the specified zero based row is selected.

        BOOL isAccessibleTableRowSelected(long vmID, AccessibleTable table, jint row);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.isAccessibleTableRowSelected(
            vmid,
            context,
            row,
        )
        return bool(result)

    def get_accessible_table_row_selections(
        self,
        count: c_int,
        selections: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> list:
        """
        Returns an array of zero based indices of the selected rows.

        BOOL getAccessibleTableRowSelections(long vmID, AccessibleTable table, jint count, jint *selections);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.getAccessibleTableRowSelections(
            vmid,
            context,
            count,
            selections,
        )

    def get_accessible_table_column_selection_count(
        self,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> int:
        """
        Returns how many columns in the table are selected.

        jint getAccessibleTableColumnSelectionCount(long vmID, AccessibleTable table);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.getAccessibleTableColumnSelectionCount(
            vmid,
            context,
        )

    def is_accessible_table_column_selected(
        self,
        column: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> bool:
        """
        Returns true if the specified zero based column is selected.

        BOOL isAccessibleTableColumnSelected(long vmID, AccessibleTable table, jint column);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.isAccessibleTableColumnSelected(
            vmid,
            context,
            column,
        )
        return bool(result)

    def get_accessible_table_column_selections(
        self,
        count: c_int,
        selections: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> list:
        """
        Returns an array of zero based indices of the selected columns.

        BOOL getAccessibleTableColumnSelections(long vmID, AccessibleTable table, jint count, jint *selections);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.getAccessibleTableColumnSelections(
            vmid,
            context,
            count,
            selections,
        )

    def get_accessible_table_row(
        self,
        index: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> int:
        """
        Returns the row number of the cell at the specified cell index.
        The values are zero based.

        jint getAccessibleTableRow(long vmID, AccessibleTable table, jint index);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.getAccessibleTableRow(
            vmid,
            context,
            index,
        )

    def get_accessible_table_column(
        self,
        index: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> int:
        """
        Returns the column number of the cell at the specified cell index.
        The values are zero based.

        jint getAccessibleTableColumn(long vmID, AccessibleTable table, jint index);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.getAccessibleTableColumn(
            vmid,
            context,
            index,
        )

    def get_accessible_table_index(
        self,
        row: c_int,
        column: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> int:
        """
        Returns the index in the table of the specified row and column offset.
        The values are zero based.

        jint getAccessibleTableIndex(long vmID, AccessibleTable table, jint row, jint column);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.getAccessibleTableIndex(
            vmid,
            context,
            row,
            column,
        )

    # Accessible Relation Set Function

    def get_accessible_relation_set(
        self,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleRelationSetInfo:
        """
        Returns information about an object's related objects.

        BOOL getAccessibleRelationSet(long vmID, AccessibleContext accessibleContext, AccessibleRelationSetInfo *relationSetInfo);
        """
        info = AccessibleRelationSetInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.getAccessibleRelationSet(
            vmid,
            context,
            byref(info),
        )
        return info

    # Accessible Hypertext Functions

    def get_accessible_hyper_text(
        self,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleHypertextInfo:
        """
        Returns hypertext information associated with a component.

        BOOL getAccessibleHypertext(long vmID, AccessibleContext accessibleContext, AccessibleHypertextInfo *hypertextInfo);
        """
        info = AccessibleHypertextInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.getAccessibleHypertext(
            vmid,
            context,
            byref(info),
        )
        return info

    def active_accessible_hyper_link(
        self,
        vmid: c_long = None,
        context: JABContext = None,
        hyperlink: AccessibleHyperlink = None,
    ) -> bool:
        """
        Requests that a hyperlink be activated.

        BOOL activateAccessibleHyperlink(long vmID, AccessibleContext accessibleContext, AccessibleHyperlink accessibleHyperlink);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        # TODO: need hanld hyperlink value if none
        result = self.bridge.activateAccessibleHyperlink(
            vmid,
            context,
            hyperlink,
        )
        return bool(result)

    def get_accessible_hyper_link_count(
        self, vmid: c_long = None, hypertext: AccessibleHypertext = None
    ) -> int:
        """
        Returns the number of hyperlinks in a component.
        Maps to AccessibleHypertext.getLinkCount.
        Returns -1 on error.

        jint getAccessibleHyperlinkCount(const long vmID, const AccessibleHypertext hypertext);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        # TODO: need hanld hypertext value if none
        return self.bridge.getAccessibleHyperlinkCount(
            vmid,
            hypertext,
        )

    def get_accessible_hyper_text_ext(
        self,
        start: c_int,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> AccessibleHypertextInfo:
        """
        Iterates through the hyperlinks in a component.
        Returns hypertext information for a component starting at hyperlink index nStartIndex.
        No more than MAX_HYPERLINKS AccessibleHypertextInfo objects will be returned for each call to this method.
        Returns FALSE on error.

        BOOL getAccessibleHypertextExt(const long vmID, const AccessibleContext accessibleContext, const jint nStartIndex, AccessibleHypertextInfo *hypertextInfo);
        """
        info = AccessibleHypertextInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        result = self.bridge.getAccessibleHypertextExt(
            self.ac.vmid,
            self.ac.ac,
            start,
            byref(info),
        )
        return info

    def get_accessible_hyper_link_index(
        self,
        index: c_int,
        vmid: c_long = None,
        hypertext: AccessibleHypertext = None,
    ) -> int:
        """
        Returns the index into an array of hyperlinks that is associated with a character index in document.
        Maps to AccessibleHypertext.getLinkIndex.
        Returns -1 on error.

        jint getAccessibleHypertextLinkIndex(const long vmID, const AccessibleHypertext hypertext, const jint nIndex);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        # TODO: need hanld hypertext value if none
        return self.bridge.getAccessibleHypertextLinkIndex(
            vmid,
            hypertext,
            index,
        )

    def get_accessible_hyper_link(
        self,
        index: c_int,
        vmid: c_long = None,
        hypertext: AccessibleHypertext = None,
    ) -> AccessibleHyperlink:
        """
        Returns the nth hyperlink in a document.
        Maps to AccessibleHypertext.getLink.
        Returns FALSE on error.

        BOOL getAccessibleHyperlink(const long vmID, const AccessibleHypertext hypertext, const jint nIndex, AccessibleHypertextInfo *hyperlinkInfo);
        """
        info = AccessibleHypertextInfo()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        # TODO: need hanld hypertext value if none
        result = self.bridge.getAccessibleHyperlink(
            vmid,
            hypertext,
            index,
            byref(info),
        )
        # TODO: need return type of AccessibleHyperlink
        return result

    # Accessible Key Binding Function

    def get_accessible_key_bindings(
        self,
        vmid: c_long = None,
        context: JABContext = None,
    ) -> list:
        """
        Returns a list of key bindings associated with a component.

        BOOL getAccessibleKeyBindings(long vmID, AccessibleContext accessibleContext, AccessibleKeyBindings *keyBindings);
        """
        bindings = AccessibleKeyBindings()
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        context = context if isinstance(vmid, JABContext) else self.ac
        return self.bridge.getAccessibleKeyBindings(
            vmid,
            context,
            byref(bindings),
        )

    # Accessible Icon Function

    def get_accessible_icons(
        self,
        vmid: c_long = None,
        accessible_context: AccessibleContext = None,
        accessible_icons: AccessibleIcons = None,
    ) -> list:
        """
        Returns a list of icons associate with a component.

        BOOL getAccessibleIcons(long vmID, AccessibleContext accessibleContext, AccessibleIcons *icons);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        return self.bridge.getAccessibleIcons(
            vmid, accessible_context, accessible_icons
        )

    # Accessible Action Functions

    def get_accessible_actions(
        self,
        vmid: c_long = None,
        accessible_context: AccessibleContext = None,
        accessible_actions: AccessibleActions = None,
    ) -> list:
        """
        Returns a list of actions that a component can perform.

        BOOL getAccessibleActions(long vmID, AccessibleContext accessibleContext, AccessibleActions *actions);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        return self.bridge.getAccessibleActions(
            vmid, accessible_context, accessible_actions
        )

    def do_accessible_actions(
        self,
        vmid: c_long = None,
        accessible_context: AccessibleContext = None,
        accessible_actions_todo: AccessibleActionsToDo = None,
        failure: jint = None,
    ) -> list:
        """
        Request that a list of AccessibleActions be performed by a component.
        Returns TRUE if all actions are performed.
        Returns FALSE when the first requested action fails in which case "failure" contains the index of the action that failed.

        BOOL doAccessibleActions(long vmID, AccessibleContext accessibleContext, AccessibleActionsToDo *actionsToDo, jint *failure);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        return self.bridge.doAccessibleActions(
            vmid, accessible_context, accessible_actions_todo, failure
        )

    # Utility Functions

    def is_same_object(
        self,
        object1: JOBJECT64,
        object2: JOBJECT64,
        vmid: c_long = None,
    ) -> bool:
        """
        Returns whether two object references refer to the same object.

        BOOL IsSameObject(long vmID, JOBJECT64 obj1, JOBJECT64 obj2);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        result = self.bridge.isSameObject(vmid, object1, object2)
        return bool(result)

    def get_parent_with_role(
        self,
        role: c_wchar,
        vmid: c_long = None,
        accessible_context: AccessibleContext = None,
    ) -> AccessibleContext:
        """
        Returns the AccessibleContext with the specified role that is the ancestor of a given object.
        The role is one of the role strings defined in Java Access Bridge API Data Structures.
        If there is no ancestor object that has the specified role, returns (AccessibleContext)0.

        AccessibleContext getParentWithRole (const long vmID, const AccessibleContext accessibleContext, const wchar_t *role);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        parent_accessible_context = self.bridge.getParentWithRole(
            vmid, accessible_context, role
        )
        # TODO: success return parent accessible context; fail return current accessible context
        if parent_accessible_context:
            return AccessibleContext(hwnd, vmid, parent_accessible_context)
        else:
            return AccessibleContext(hwnd, vmid, accessible_context)

    def get_parent_with_role_else_root(
        self,
        role: c_wchar,
        vmid: c_long = None,
        accessible_context: AccessibleContext = None,
    ) -> AccessibleContext:
        """
        Returns the AccessibleContext with the specified role that is the ancestor of a given object.
        The role is one of the role strings defined in Java Access Bridge API Data Structures.
        If an object with the specified role does not exist, returns the top level object for the Java window.
        Returns (AccessibleContext)0 on error.

        AccessibleContext getParentWithRoleElseRoot (const long vmID, const AccessibleContext accessibleContext, const wchar_t *role);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        parent_accessible_context = self.bridge.getParentWithRoleElseRoot(
            vmid, accessible_context, role
        )
        # TODO: success return parent accessible context; fail return current accessible context
        if parent_accessible_context:
            return AccessibleContext(hwnd, vmid, parent_accessible_context)
        else:
            return AccessibleContext(hwnd, vmid, accessible_context)

    def get_top_level_object(
        self, vmid: c_long = None, accessible_context: AccessibleContext = None
    ) -> AccessibleContext:
        """
        Returns the AccessibleContext for the top level object in a Java window.
        This is same AccessibleContext that is obtained from GetAccessibleContextFromHWND for that window.
        Returns (AccessibleContext)0 on error.

        AccessibleContext getTopLevelObject (const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        top_level_object = self.bridge.getTopLevelObject(vmid, accessible_context)
        # TODO: success return accessible context; fail return current accessible context
        if top_level_object:
            return AccessibleContext(hwnd, vmid, top_level_object)
        else:
            return AccessibleContext(hwnd, vmid, accessible_context)

    def get_object_depth(
        self, vmid: c_long = None, accessible_context: AccessibleContext = None
    ) -> int:
        """
        Returns how deep in the object hierarchy a given object is.
        The top most object in the object hierarchy has an object depth of 0.
        Returns -1 on error.

        int getObjectDepth (const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        object_depth = self.bridge.getObjectDepth(vmid, accessible_context)
        if object_depth != -1:
            return object_depth
        else:
            raise JavaAccessBridgeInternalException(
                "Java Access Bridge func 'getObjectDepth' error"
            )

    def get_active_descendent(
        self, vmid: c_long = None, accessible_context: AccessibleContext = None
    ) -> AccessibleContext:
        """
        Returns the AccessibleContext of the current ActiveDescendent of an object.
        This method assumes the ActiveDescendent is the component that is currently selected in a container object.
        Returns (AccessibleContext)0 on error or if there is no selection.

        AccessibleContext getActiveDescendent (const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        active_descendent = self.bridge.getActiveDescendent(vmid, accessible_context)
        # TODO: success return accessible context; fail return current accessible context
        if active_descendent:
            return AccessibleContext(hwnd, vmid, active_descendent)
        else:
            return AccessibleContext(hwnd, vmid, accessible_context)

    def request_focus(
        self, vmid: c_long = None, accessible_context: AccessibleContext = None
    ) -> bool:
        """
        Request focus for a component.
        Returns whether successful.

        BOOL requestFocus(const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        is_success = self.bridge.requestFocus(vmid, accessible_context)
        return bool(is_success)

    def get_visible_children_count(
        self, vmid: c_long = None, accessible_context: AccessibleContext = None
    ) -> int:
        """
        Gets the visible children of an AccessibleContext.
        Returns whether successful.

        int getVisibleChildrenCount(const long vmID, const AccessibleContext accessibleContext);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_context = (
            accessible_context if isinstance(vmid, AccessibleContext) else self.ac
        )
        visible_children_count = self.bridge.getVisibleChildrenCount(
            vmid, accessible_context
        )
        if visible_children_count != -1:
            return visible_children_count
        else:
            raise JavaAccessBridgeInternalException(
                "Java Access Bridge func 'getVisibleChildrenCount' error"
            )

    def get_events_waiting(self) -> int:
        """
        Gets the number of events waiting to fire.

        int getEventsWaiting();
        """
        events_waiting = self.bridge.getEventsWaiting()
        if events_waiting != -1:
            return events_waiting
        else:
            raise JavaAccessBridgeInternalException(
                "Java Access Bridge func 'getEventsWaiting' error"
            )

    # Accessible Value Functions
    """
    These functions get AccessibleValue information provided by the Java Accessibility API. 
    An AccessibleContext object has AccessibleValue information contained within it if the flag accessibleValue in the AccessibleContextInfo data structure is set to TRUE. 
    The values returned are strings (char *value) because there is no way to tell in advance if the value is an integer, a floating point value, or some other object that subclasses the Java language construct java.lang.Number.
    """

    def get_current_accessible_value_from_context(
        self,
        vmid: c_long = None,
        accessible_value: AccessibleValue = None,
        unicode_buffer: c_wchar = None,
        length: c_short = None,
    ) -> str:
        """
        Get the value of this object as a Number. If the value has not been set, the return value will be null.

        BOOL GetCurrentAccessibleValueFromContext(long vmID, AccessibleValue av, wchar_t *value, short len);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_value = (
            accessible_value if isinstance(vmid, AccessibleValue) else self.ac
        )
        unicode_buffer = (
            unicode_buffer
            if isinstance(unicode_buffer, c_wchar)
            else create_unicode_buffer(SHORT_STRING_SIZE + 1)
        )
        length = length if isinstance(length, c_short) else SHORT_STRING_SIZE
        current_accessible_value = self.GetCurrentAccessibleValueFromContext(
            vmid, accessible_value, unicode_buffer, length
        )
        return current_accessible_value

    def get_maximum_accessible_value_from_context(
        self,
        vmid: c_long = None,
        accessible_value: AccessibleValue = None,
        unicode_buffer: c_wchar = None,
        length: c_short = None,
    ):
        """
        Get the maximum value of this object as a Number.
        Returns Maximum value of the object; null if this object does not have a maximum value

        BOOL GetMaximumAccessibleValueFromContext(long vmID, AccessibleValue av, wchar_ *value, short len);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_value = (
            accessible_value if isinstance(vmid, AccessibleValue) else self.ac
        )
        unicode_buffer = (
            unicode_buffer
            if isinstance(unicode_buffer, c_wchar)
            else create_unicode_buffer(SHORT_STRING_SIZE + 1)
        )
        length = length if isinstance(length, c_short) else SHORT_STRING_SIZE
        maximum_accessible_value = self.GetMaximumAccessibleValueFromContext(
            vmid, accessible_value, unicode_buffer, length
        )
        return maximum_accessible_value

    def get_minimum_accessible_value_from_context(
        self,
        vmid: c_long = None,
        accessible_value: AccessibleValue = None,
        unicode_buffer: c_wchar = None,
        length: c_short = None,
    ):
        """
        Get the minimum value of this object as a Number.
        Returns Minimum value of the object; null if this object does not have a minimum value

        BOOL GetMinimumAccessibleValueFromContext(long vmID, AccessibleValue av, wchar_ *value, short len);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_value = (
            accessible_value if isinstance(vmid, AccessibleValue) else self.ac
        )
        unicode_buffer = (
            unicode_buffer
            if isinstance(unicode_buffer, c_wchar)
            else create_unicode_buffer(SHORT_STRING_SIZE + 1)
        )
        length = length if isinstance(length, c_short) else SHORT_STRING_SIZE
        maximum_accessible_value = self.GetMinimumAccessibleValueFromContext(
            vmid, accessible_value, unicode_buffer, length
        )
        return maximum_accessible_value

    # Accessible Selection Functions
    """
    These functions get and manipulate AccessibleSelection information provided by the Java Accessibility API. 
    An AccessibleContext has AccessibleSelection information contained within it if the flag accessibleSelection in the AccessibleContextInfo data structure is set to TRUE. 
    The AccessibleSelection support is the first place where the user interface can be manipulated, as opposed to being queries, through adding and removing items from a selection. 
    Some of the functions use an index that is in child coordinates, while other use selection coordinates. 
    For example, add to remove from a selection by passing child indices (for example, add the fourth child to the selection). 
    On the other hand, enumerating the selected children is done in selection coordinates (for example, get the AccessibleContext of the first object selected).
    """

    def add_accessible_selection_from_context(
        self,
        child_index: c_int,
        vmid: c_long = None,
        accessible_selection: AccessibleSelection = None,
    ) -> None:
        """
        Adds the specified Accessible child of the object to the object's selection.
        If the object supports multiple selections, the specified child is added to any existing selection, otherwise it replaces any existing selection in the object.
        If the specified child is already selected, this method has no effect.

        void AddAccessibleSelectionFromContext(long vmID, AccessibleSelection as, int i);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_selection = (
            accessible_selection if isinstance(vmid, AccessibleSelection) else self.ac
        )
        self.bridge.AddAccessibleSelectionFromContext(
            vmid, accessible_selection, child_index
        )

    def clear_accessible_selection_from_context(
        self,
        vmid: c_long = None,
        accessible_selection: AccessibleSelection = None,
    ) -> None:
        """
        Clears the selection in the object, so that no children in the object are selected.

        void ClearAccessibleSelectionFromContext(long vmID, AccessibleSelection as);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_selection = (
            accessible_selection if isinstance(vmid, AccessibleSelection) else self.ac
        )
        self.bridge.ClearAccessibleSelectionFromContext(vmid, accessible_selection)

    def get_accessible_selection_from_context(
        self,
        child_index: c_int,
        vmid: c_long = None,
        accessible_selection: AccessibleSelection = None,
    ) -> JOBJECT64:
        """
        Returns an Accessible representing the specified selected child of the object.
        If there isn't a selection, or there are fewer children selected than the integer passed in, the return value will be null.
        Note that the index represents the i-th selected child, which is different from the i-th child.

        jobject GetAccessibleSelectionFromContext(long vmID, AccessibleSelection as, int i);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_selection = (
            accessible_selection if isinstance(vmid, AccessibleSelection) else self.ac
        )
        selected_object = self.bridge.GetAccessibleSelectionFromContext(
            vmid, accessible_selection, child_index
        )
        if isinstance(selected_object, JOBJECT64):
            return selected_object
        else:
            raise JavaAccessBridgeInternalException(
                "Java Access Bridge func 'GetAccessibleSelectionFromContext' error"
            )

    def get_accessible_selection_count_from_context(
        self,
        vmid: c_long = None,
        accessible_selection: AccessibleSelection = None,
    ) -> int:
        """
        Returns the number of Accessible children currently selected.
        If no children are selected, the return value will be 0.

        int GetAccessibleSelectionCountFromContext(long vmID, AccessibleSelection as);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_selection = (
            accessible_selection if isinstance(vmid, AccessibleSelection) else self.ac
        )
        selection_count = self.bridge.GetAccessibleSelectionCountFromContext(
            vmid, accessible_selection
        )
        if selection_count != -1:
            return selection_count
        else:
            raise JavaAccessBridgeInternalException(
                "Java Access Bridge func 'GetAccessibleSelectionCountFromContext' error"
            )

    def is_accessible_child_selected_from_context(
        self,
        child_index: c_int,
        vmid: c_long = None,
        accessible_selection: AccessibleSelection = None,
    ) -> bool:
        """
        Determines if the current child of this object is selected.

        BOOL IsAccessibleChildSelectedFromContext(long vmID, AccessibleSelection as, int i);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_selection = (
            accessible_selection if isinstance(vmid, AccessibleSelection) else self.ac
        )
        is_selected = self.bridge.IsAccessibleChildSelectedFromContext(
            vmid, accessible_selection, child_index
        )
        return bool(is_selected)

    def remove_accessible_selection_from_context(
        self,
        child_index: c_int,
        vmid: c_long = None,
        accessible_selection: AccessibleSelection = None,
    ) -> None:
        """
        Removes the specified child of the object from the object's selection.
        If the specified item isn't currently selected, this method has no effect.

        void RemoveAccessibleSelectionFromContext(long vmID, AccessibleSelection as, int i);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_selection = (
            accessible_selection if isinstance(vmid, AccessibleSelection) else self.ac
        )
        self.bridge.RemoveAccessibleSelectionFromContext(
            vmid, accessible_selection, child_index
        )

    def select_all_accessible_selection_from_context(
        self,
        vmid: c_long = None,
        accessible_selection: AccessibleSelection = None,
    ) -> None:
        """
        Causes every child of the object to be selected if the object supports multiple selections.

        void SelectAllAccessibleSelectionFromContext(long vmID, AccessibleSelection as);
        """
        vmid = vmid if isinstance(vmid, c_long) else self.ac.vmid
        accessible_selection = (
            accessible_selection if isinstance(vmid, AccessibleSelection) else self.ac
        )
        self.bridge.SelectAllAccessibleSelectionFromContext(vmid, accessible_selection)

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

    @focus_gained_fp
    def set_focus_fained(self) -> None:
        ac = JABContext(hwnd=self.ac.hwnd, vmid=self.ac.vmid, ac=self.ac.ac)
        if not self.user.is_descendant_window(
            self.user.get_foreground_window(), ac.hwnd
        ):
            return
        focus = self.handler.last_queue_focus