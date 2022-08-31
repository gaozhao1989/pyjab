"""Java Access Bridge API Calls"""
from ctypes import (
    CDLL,
    Array,
    byref,
    c_int,
    c_long,
    c_short,
    c_wchar,
    create_string_buffer,
    create_unicode_buffer,
)
from typing import Optional, Tuple, Union
from pyjab.common.exceptions import JABException
from pyjab.jabdatastr import (
    SHORT_STRING_SIZE,
    AccessBridgeVersionInfo,
    AccessibleActions,
    AccessibleActionsToDo,
    AccessibleContextInfo,
    AccessibleHypertextInfo,
    AccessibleIcons,
    AccessibleKeyBindings,
    AccessibleRelationInfo,
    AccessibleTableCellInfo,
    AccessibleTableInfo,
    AccessibleTextAttributesInfo,
    AccessibleTextInfo,
    AccessibleTextItemsInfo,
    AccessibleTextRectInfo,
    AccessibleTextSelectionInfo,
    VisibleChildrenInfo,
)

from pyjab.common.logger import Logger
from pyjab.common.textreader import WCHAR_ENCODING, TextReader
from pyjab.common.types import JOBJECT64, AccessibleContext, jint


class JABAPI(object):
    def __init__(self, bridge: CDLL) -> None:
        self.bridge = bridge
        self.logger = Logger()

    # Gateway Functions
    # You typically call these functions before calling any other Java Access Bridge API function

    def is_java_window(self, hwnd: int) -> bool:
        """Checks to see if the given window implements the Java Accessibility API.

        Args:
            hwnd (int): HWND of window.

        Returns:
            bool: True for is Java Window False for NOT.
        """
        result = bool(self.bridge.isJavaWindow(hwnd))
        self.logger.debug(f"Window {hwnd} is Java Window => {result}")
        return result

    def get_accessible_context_from_hwnd(
        self, hwnd: int
    ) -> Tuple[AccessibleContext, int]:
        """Gets the AccessibleContext and vmid values for the given window.
        Many Java Access Bridge functions require the AccessibleContext and vmid values.

        Args:
            hwnd (int): HWND for the given window.

        Returns:
            Tuple (AccessibleContext, int): tuple of AccessibleContext and vmid.
        """
        vmid = c_long()
        accessible_context = AccessibleContext()
        result = bool(
            self.bridge.getAccessibleContextFromHWND(
                hwnd, byref(vmid), byref(accessible_context)
            )
        )
        self.logger.debug(
            f"Gets the AccessibleContext {accessible_context} and "
            f"vmid values {vmid.value} for the given window => {result}"
        )
        return accessible_context, vmid.value

    # General Functions
    def release_java_object(self, vmid: int, java_object: JOBJECT64) -> None:
        """Release the memory used by the Java object object,
        where object is an object returned to you by Java Access Bridge.
        Java Access Bridge automatically maintains a reference to all Java objects
        that it returns to you in the JVM so they are not garbage collected.
        To prevent memory leaks, call ReleaseJavaObject on all Java objects
        returned to you by Java Access Bridge once you are finished with them.

        Args:
            vmid (int): vmid of the given Java Object.
            java_object (JOBJECT64): Java Object need to release(AccessibleContext)
        """
        self.logger.debug(f"Release the Java object => {java_object}")
        self.bridge.releaseJavaObject(vmid, java_object)

    def get_version_info(self, vmid: int) -> dict[str, str]:
        """Gets the version information of the instance of Java Access Bridge instance your application is using.
        You can use this information to determine the available functionality of your version of Java Access Bridge.

        Args:
            vmid (int): vmid of the given Java instance.

        Returns:
            dict[str,str]: Dict of AccessBridgeVersionInfo, contains:
                vm_version (str): version of the Java VM
                bridge_java_class_version (str): version of the AccessBridge.class
                bridge_java_dll_version (str): version of JavaAccessBridge.dll
                bridge_win_dll_version (str): version of WindowsAccessBridge.dll
        """
        info = AccessBridgeVersionInfo()
        result = self.bridge.getVersionInfo(vmid, byref(info))
        self.logger.debug(f"Gets the version information => {result}")
        dict_info = {
            "vm_version": info.VMVersion,
            "bridge_java_class_version": info.bridgeJavaClassVersion,
            "bridge_java_dll_version": info.bridgeJavaDLLVersion,
            "bridge_win_dll_version": info.bridgeWinDLLVersion,
        }
        self.logger.debug(dict_info)
        return dict_info

    # Accessible Context Functions
    # These functions provide the core of the Java Accessibility API that is exposed by Java Access Bridge.
    # The functions GetAccessibleContextAt and GetAccessibleContextWithFocus retrieve an AccessibleContext object,
    # which is a magic cookie (a Java Object reference) to an Accessible object and a JVM cookie.
    # You use these two cookies to reference objects through Java Access Bridge.
    # Most Java Access Bridge API functions require that you pass in these two parameters.
    def get_accessible_context_at(
        self,
        vmid: int,
        accessible_context: AccessibleContext,
        x: int,
        y: int,
    ) -> AccessibleContext:
        """Retrieves an AccessibleContext object of the window or object that is under the mouse pointer.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Parent object of Accessible Context.
            x (int): Mouse pointer position x.
            y (int): Mouse pointer position y.

        Returns:
            AccessibleContext: AccessibleContext object of the window or object that is under the mouse pointer
        """
        new_accessible_context = AccessibleContext()
        result = bool(
            self.bridge.getAccessibleContextAt(
                vmid, accessible_context, x, y, byref(new_accessible_context)
            )
        )
        self.logger.debug(f"Retrieves an AccessibleContext object at => {result}")
        return new_accessible_context

    def get_accessible_context_with_focus(self, hwnd: int) -> AccessibleContext:
        """Retrieves an AccessibleContext object of the window or object that has the focus.

        Args:
            hwnd (int): HWND of window.

        Returns:
            AccessibleContext: Accessible Context object of the window or object that has the focus
        """
        vmid = c_long()
        accessible_context = AccessibleContext()
        result = bool(
            self.bridge.getAccessibleContextWithFocus(
                hwnd, byref(vmid), byref(accessible_context)
            )
        )
        self.logger.debug(
            f"Retrieves an AccessibleContext object has the focus => {result}"
        )
        return accessible_context

    def get_accessible_context_info(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, Union[str, int, bool, list]]:
        """Retrieves an AccessibleContextInfo object of the AccessibleContext object ac.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            dict[str,str]: Dict of AccessibleContextInfo, contains:
                name (str): the AccessibleName of the object
                description (str): the AccessibleDescription of the object
                role (str): localized AccesibleRole string
                role_en_us (str): english AccesibleRole string
                states (list[str]): localized AccesibleStateSet list of string
                states_en_us (list[str]): english AccesibleStateSet list of string
                index_in_parent (int): index of object in parent
                children_count (int): number of children count, if any
                x (int): screen x-axis co-ordinate in pixels
                y (int): screen y-axis co-ordinate in pixels
                width (int): pixel width of object
                height (int): pixel height of object
                accessible_component (bool): flag for accessible_context support AccessibleCompoent
                accessible_action (bool): flag for accessible_context support AccessibleAction
                accessible_text (bool): flag for accessible_context support AccessibleText
                accessible_interfaces (bool): flag for accessible_context support accessibleInterfaces

        """
        info = AccessibleContextInfo()
        result = bool(
            self.bridge.getAccessibleContextInfo(vmid, accessible_context, byref(info))
        )
        self.logger.debug(f"Retrieves an AccessibleContextInfo => {result}")
        dict_info = {
            "name": info.name,
            "description": info.description,
            "role": info.role,
            "role_en_us": info.role_en_US,
            "states": info.states.split(","),
            "states_en_us": info.states_en_US.split(","),
            "index_in_parent": info.indexInParent,
            "children_count": info.childrenCount,
            "x": info.x,
            "y": info.y,
            "width": info.width,
            "height": info.height,
            "accessible_component": bool(info.accessibleComponent),
            "accessible_action": bool(info.accessibleAction),
            "accessible_selection": bool(info.accessibleSelection),
            "accessible_text": bool(info.accessibleText),
            "accessible_interfaces": bool(info.accessibleInterfaces),
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_child_from_context(
        self, vmid: int, accessible_context: AccessibleContext, index: int
    ) -> AccessibleContext:
        """Returns an AccessibleContext object that represents the nth child of the object ac,
        where n is specified by the value index.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Parent object of Accessible Context.
            index (int): index number of specific child need to retrieve.

        Returns:
            AccessibleContext: the nth child of the object Accessible Context
        """
        self.logger.info(f"Get Accessible Context child from context")
        child_accessible_context: AccessibleContext = (
            self.bridge.getAccessibleChildFromContext(vmid, accessible_context, index)
        )
        return child_accessible_context

    def get_accessible_parent_from_context(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> AccessibleContext:
        """Returns an AccessibleContext object that represents the parent of object ac.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.


        Returns:
            AccessibleContext: Parent of object Accessible Context.
        """
        self.logger.info(f"Get Accessible Context parent from context")
        parent_accessible_context: AccessibleContext = (
            self.bridge.getAccessibleParentFromContext(vmid, accessible_context)
        )
        return parent_accessible_context

    def get_hwnd_from_accessible_context(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> int:
        """Returns the HWND from the AccessibleContextof a top-level window.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            int: HWND from the AccessibleContext.
        """
        self.logger.info(f"Get HWND from Accessible Context")
        hwnd: int = self.bridge.getHWNDFromAccessibleContext(vmid, accessible_context)
        return hwnd

    # Accessible Text Functions
    # These functions get AccessibleText information provided by the Java Accessibility API,
    # broken down into seven chunks for efficiency.
    # An AccessibleContext has AccessibleText information contained within it
    # if you set the flag accessibleText in the AccessibleContextInfo data structure to TRUE.
    # The file AccessBridgePackages.h defines the struct values used in these functions
    # Java Access Bridge API Callbacks describes them.

    def get_accessible_text_info(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, int]:
        """Retrieves an AccessibleTextInfo object of the AccessibleText(AccessibleContext) object.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            dict[str,str]: Dict of AccessibleTextInfo, contains:
                char_count (int): Number of characters in this text object.
                caret_index (int): Index of caret in this text object.
                index_at_point (int): Index at the passsed in point in this text object.
        """
        info = AccessibleTextInfo()
        result = bool(
            self.bridge.getAccessibleTextInfo(
                vmid, accessible_context, byref(info), 0, 0
            )
        )
        self.logger.debug(f"Retrieves an GetAccessibleTextInfo => {result}")
        dict_info = {
            "char_count": info.charCount,
            "caret_index": info.caretIndex,
            "index_at_point": info.indexAtPoint,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_text_items(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, int]:
        """Retrieves an AccessibleTextItemsInfo object of the AccessibleText(AccessibleContext) object.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            dict[str,str]: Dict of AccessibleTextItemsInfo, contains:
                letter (str): String of letter in this text object.
                word (str): String of word in this text object.
                sentence (str): String of sentence in this text object.
        """
        info = AccessibleTextItemsInfo()
        result = bool(
            self.bridge.getAccessibleTextItems(vmid, accessible_context, byref(info), 0)
        )
        self.logger.debug(f"Retrieves an AccessibleTextItemsInfo => {result}")
        dict_info = {
            "letter": info.letter,
            "word": info.word,
            "sentence": info.sentence,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_text_selection_info(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, Union[int, str]]:
        """Retrieves an AccessibleTextSelectionInfo object of the AccessibleText(AccessibleContext) object.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            dict[str,Union[int,str]]: Dict of AccessibleTextSelectionInfo, contains:
                selection_start_index (int): Start index of selection text in this text object.
                selection_end_index (int): End index of selection text in this text object.
                selected_text (str): String of selection text in this text object.
        """
        info = AccessibleTextSelectionInfo()
        result = bool(
            self.bridge.getAccessibleTextSelectionInfo(
                vmid, accessible_context, byref(info)
            )
        )
        self.logger.debug(f"Retrieves an AccessibleTextSelectionInfo => {result}")
        dict_info = {
            "selection_start_index": info.selectionStartIndex,
            "selection_end_index": info.selectionEndIndex,
            "selected_text": info.selectedText,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_text_attributes(
        self, vmid: int, accessible_context: AccessibleContext, index: int
    ) -> dict[str, Union[bool, str, int, float]]:
        """Retrieves an AccessibleTextAttributesInfo object of the AccessibleText(AccessibleContext) object.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            index (int): Index of caret at text object.

        Returns:
            dict[str,Union[bool, str, int]]: Dict of AccessibleTextAttributesInfo, contains:
                bold (bool): Text is bold style in this text object.
                italic (bool): Text is italic style in this text object.
                underline (bool): Text is underline style in this text object.
                strikethrough (bool): Text is strikethrough style in this text object.
                superscript (bool): Text is superscript style in this text object.
                subscript (bool): Text is subscript style in this text object.
                background_color (str): Text background color in this text object.
                foreground_color (str): Text foreground color in this text object.
                font_family (str): Text font family in this text object.
                font_size (int): Text font size in this text object.
                alignment (int): Text alignment in this text object.
                bidi_level (int): Text bidi level in this text object.
                first_line_indent (float): Text first line indent in this text object.
                left_indent (float): Text left indent in this text object.
                right_indent (float): Text right indent in this text object.
                line_spacing (float): Text line spacing in this text object.
                space_above (float): Text space above in this text object.
                space_below (float): Text space below in this text object.
                full_attributes_string (float): Text of full attributes string in this text object.
        """
        info = AccessibleTextAttributesInfo()
        result = bool(
            self.bridge.AccessibleTextAttributesInfo(
                vmid, accessible_context, index, byref(info)
            )
        )
        self.logger.debug(f"Retrieves an AccessibleTextAttributesInfo => {result}")
        dict_info = {
            "bold": info.bold,
            "italic": info.italic,
            "underline": info.underline,
            "strikethrough": info.strikethrough,
            "superscript": info.superscript,
            "subscript": info.subscript,
            "background_color": info.backgroundColor,
            "foreground_color": info.foregroundColor,
            "font_family": info.fontFamily,
            "font_size": info.fontSize,
            "alignment": info.alignment,
            "bidi_level": info.bidiLevel,
            "first_line_indent": info.firstLineIndent,
            "left_indent": info.leftIndent,
            "right_indent": info.rightIndent,
            "line_spacing": info.lineSpacing,
            "space_above": info.spaceAbove,
            "space_below": info.spaceBelow,
            "full_attributes_string": info.fullAttributesString,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_text_rect(
        self, vmid: int, accessible_context: AccessibleContext, index: int
    ) -> dict[str, int]:
        """Retrieves an AccessibleTextRect object of the AccessibleText(AccessibleContext) object.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            index (int): Index of caret at text object.

        Returns:
            dict[str,int]: Dict of AccessibleTextRect, contains:
                x (int): Bounding rectangle of char at index, x-axis co-ordinate in this text object.
                y (int): Bounding rectangle of char at index, y-axis co-ordinate in this text object.
                width (int): Bounding rectangle width in this text object.
                height (int): Bounding rectangle height in this text object.
        """
        info = AccessibleTextRectInfo()
        result = bool(
            self.bridge.getAccessibleTextRect(
                vmid, accessible_context, byref(info), index
            )
        )
        self.logger.debug(f"Retrieves an AccessibleTextRect => {result}")
        dict_info = {
            "x": info.x,
            "y": info.y,
            "width": info.width,
            "height": info.height,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_text_range(
        self, vmid: int, accessible_context: AccessibleContext, start: int, end: int
    ) -> str:
        """Retrieves a range of text; null if indicies are bogus.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            start (int): Start Index of range text at text object.
            end (int): End Index of range text at text object.

        Returns:
            str: A range of text else None for indicies are bogus.
        """
        length = (end + 1) - start
        if length <= 0:
            return ""
        # Use a string buffer, as from an unicode buffer, we can't get the raw data.
        buffer = create_string_buffer((length + 1) * 2)
        result = bool(
            self.bridge.getAccessibleTextRange(
                vmid, accessible_context, start, end, buffer, length
            )
        )
        self.logger.debug(f"Retrieves an AccessibleTextRect => {result}")
        txt = TextReader.get_text_from_raw_bytes(buffer.raw, length, WCHAR_ENCODING)
        self.logger.debug(txt)
        return txt

    def get_accessible_text_line_bounds(
        self, vmid: int, accessible_context: AccessibleContext, index: int
    ) -> tuple[int, int]:
        """Retrieves line bounds of the AccessibleText(AccessibleContext) object.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            index (int): Index of caret at text object.

        Returns:
            tuple (int, int): Line bounds of AccessibleText object.
        """
        index = max(index, 0)
        self.logger.debug(f"Line bounds index {index}")
        # Java returns end as the last character, not end as past the last character
        start_index = c_int()
        end_index = c_int()
        self.bridge.getAccessibleTextLineBounds(
            vmid,
            accessible_context,
            index,
            byref(start_index),
            byref(end_index),
        )
        start = start_index.value
        end = end_index.value
        self.logger.debug(f"Line bounds: start {start}, end {end}")
        if end < start or start < 0:
            # Invalid or empty line.
            return (0, -1)
        # OpenOffice sometimes returns offsets encompassing more than one line, so try to narrow them down.
        # Try to retract the end offset.
        flag_ok = False
        while not flag_ok:
            self.bridge.getAccessibleTextLineBounds(
                vmid,
                accessible_context,
                end,
                byref(start_index),
                byref(end_index),
            )
            temp_start = max(start_index.value, 0)
            temp_end = max(end_index.value, 0)
            self.logger.debug(
                f"Line bounds: temp start {temp_start}, temp end {temp_end}"
            )
            if temp_start > (index + 1):
                # This line starts after the requested index, so set end to point at the line before.
                end = temp_start - 1
            else:
                flag_ok = True
        flag_ok = False
        # Try to retract the start.
        while not flag_ok:
            self.bridge.getAccessibleTextLineBounds(
                vmid,
                accessible_context,
                start,
                byref(start_index),
                byref(end_index),
            )
            temp_start = max(start_index.value, 0)
            temp_end = max(end_index.value, 0)
            self.logger.debug(
                f"Line bounds: temp start {temp_start}, temp end {temp_end}"
            )
            if temp_end < (index - 1):
                # This line ends before the requested index, so set start to point at the line after.
                start = temp_end + 1
            else:
                flag_ok = True
        self.logger.debug(f"Line bounds: returning start {start}, end {end}")
        return (start, end)

    # Additional Text Functions
    def select_text_range(
        self,
        vmid: int,
        accessible_context: AccessibleContext,
        start_index: int,
        end_index: int,
    ) -> bool:
        """Selects text between two indices.
        Selection includes the text at the start index and the text at the end index.
        Returns whether successful.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            start_index (int): Start index of text need to selected.
            end_index (int): End index of text need to selected.
        """
        result = bool(
            self.bridge.selectTextRange(
                vmid, accessible_context, start_index, end_index
            )
        )
        self.logger.debug(f"Select Text Range {start_index} to {end_index} => {result}")
        return result

    def get_text_attributes_in_range(
        self,
        vmid: int,
        accessible_context: AccessibleContext,
        start_index: int,
        end_index: int,
    ) -> dict[str, Union[bool, str, int, float]]:
        """Get text attributes between two indices.
        The attribute list includes the text at the start index and the text at the end index.
        Returns whether successful.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            start_index (int): Start index of text need to selected.
            end_index (int): End index of text need to selected.

        Returns:
            dict[str,Union[bool, str, int]]: Dict of AccessibleTextAttributesInfo, contains:
                bold (bool): Text is bold style in this text object.
                italic (bool): Text is italic style in this text object.
                underline (bool): Text is underline style in this text object.
                strikethrough (bool): Text is strikethrough style in this text object.
                superscript (bool): Text is superscript style in this text object.
                subscript (bool): Text is subscript style in this text object.
                background_color (str): Text background color in this text object.
                foreground_color (str): Text foreground color in this text object.
                font_family (str): Text font family in this text object.
                font_size (int): Text font size in this text object.
                alignment (int): Text alignment in this text object.
                bidi_level (int): Text bidi level in this text object.
                first_line_indent (float): Text first line indent in this text object.
                left_indent (float): Text left indent in this text object.
                right_indent (float): Text right indent in this text object.
                line_spacing (float): Text line spacing in this text object.
                space_above (float): Text space above in this text object.
                space_below (float): Text space below in this text object.
                full_attributes_string (float): Text of full attributes string in this text object.
        """
        info = AccessibleTextAttributesInfo()
        length = c_short()
        result = bool(
            self.bridge.getTextAttributesInRange(
                vmid,
                accessible_context,
                start_index,
                end_index,
                byref(info),
                byref(length),
            )
        )
        self.logger.debug(f"Get text attributes between two indices => {result}")
        dict_info = {
            "bold": info.bold,
            "italic": info.italic,
            "underline": info.underline,
            "strikethrough": info.strikethrough,
            "superscript": info.superscript,
            "subscript": info.subscript,
            "background_color": info.backgroundColor,
            "foreground_color": info.foregroundColor,
            "font_family": info.fontFamily,
            "font_size": info.fontSize,
            "alignment": info.alignment,
            "bidi_level": info.bidiLevel,
            "first_line_indent": info.firstLineIndent,
            "left_indent": info.leftIndent,
            "right_indent": info.rightIndent,
            "line_spacing": info.lineSpacing,
            "space_above": info.spaceAbove,
            "space_below": info.spaceBelow,
            "full_attributes_string": info.fullAttributesString,
        }
        self.logger.debug(dict_info)
        return dict_info

    def set_caret_position(
        self,
        vmid: int,
        accessible_context: AccessibleContext,
        position: int,
    ) -> bool:
        """Set the caret to a text position.
        Returns whether successful.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            position (int): Index of caret position at text object.
        """
        result = bool(self.bridge.setCaretPosition(vmid, accessible_context, position))
        self.logger.debug(f"Set the caret to a text position to {position} => {result}")
        return result

    def get_caret_location(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, int]:
        """Gets the text caret location.
        Returns whether successful.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            (dict): Dict of the text caret location, contains:
                x (int): Bounding rectangle of char at index, x-axis co-ordinate in this text object.
                y (int): Bounding rectangle of char at index, y-axis co-ordinate in this text object.
                width (int): Bounding rectangle width in this text object.
                height (int): Bounding rectangle height in this text object.
        """
        info = AccessibleTextRectInfo()
        index = c_int()
        result = bool(
            self.bridge.getCaretLocation(
                vmid, accessible_context, byref(info), byref(index)
            )
        )
        self.logger.debug(f"Get the caret position => {result}")
        dict_info = {
            "x": info.x,
            "y": info.y,
            "width": info.width,
            "height": info.height,
        }
        self.logger.debug(dict_info)
        return dict_info

    def set_text_contents(
        self, vmid: int, accessible_context: AccessibleContext, text: str
    ) -> bool:
        """Sets editable text contents.
        The AccessibleContext must implement AccessibleEditableText and be editable.
        The maximum text length that can be set is MAX_STRING_SIZE - 1.
        Returns whether successful.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            text (str): String of text need to set into AccessibleEditableText.
        """
        result = bool(self.bridge.setTextContents(vmid, accessible_context, text))
        self.logger.debug(f"Set editable text contents => {result}")
        return result

    # Accessible Table Functions
    def get_accessible_table_info(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, Union[JOBJECT64, int]]:
        """Returns information about the table,
        for example, caption, summary, row and column count, and the AccessibleTable.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.

        Returns:
            dict: Dict of information about the table, contains:
                caption (JOBJECT64): caption of table.
                summary (JOBJECT64): summary of table.
                row_count (int): row count number of table.
                column_count (int): column count number of table.
                accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
                accessible_table (AccessibleTable): Current object(AccessibleTable) of Accessible Table.
        """
        info = AccessibleTableInfo()
        result = bool(
            self.bridge.getAccessibleTableInfo(vmid, accessible_context, byref(info))
        )
        self.logger.debug(f"Get information about the table => {result}")
        dict_info = {
            "caption": info.caption,
            "summary": info.summary,
            "row_count": info.rowCount,
            "column_count": info.columnCount,
            "accessible_context": info.accessibleContext,
            "accessible_table": info.accessibleTable,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_table_cell_info(
        self, vmid: int, accessible_context: AccessibleContext, row: int, column: int
    ) -> dict[str, Union[AccessibleContext, int, bool]]:
        """Returns information about the specified table cell.
        The row and column specifiers are zero-based.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            row (int): Index of cell in row.
            column (int): Index of cell in column.

        Returns:
            dict: Dict of information about the cell, contains:
                accessible_context (AccessibleContext): Current object of Accessible Context.
                index (int): Index of cell in table.
                row (int): Index of cell in row.
                column (int): Index of cell in column.
                row_extent (int): Extent of cell in row.
                column_extent (int): Extent of cell in column.
                is_selected (bool): Cell is selected or not.

        """
        info = AccessibleTableCellInfo()
        result = bool(
            self.bridge.getAccessibleTableCellInfo(
                vmid, accessible_context, row, column, byref(info)
            )
        )
        self.logger.debug(f"Get information about the cell => {result}")
        dict_info = {
            "accessible_context": info.accessibleContext,
            "index": info.index,
            "row": info.row,
            "column": info.column,
            "row_extent": info.rowExtent,
            "column_extent": info.columnExtent,
            "is_selected": info.isSelected,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_table_row_header(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, Union[JOBJECT64, int]]:
        """Returns the table row headers of the specified table as a table.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.

        Returns:
            dict[str, Union[JOBJECT64, int]]: Dict of information about the table row header, contains:
                caption (JOBJECT64): caption of table.
                summary (JOBJECT64): summary of table.
                row_count (int): row count number of table.
                column_count (int): column count number of table.
                accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
                accessible_table (AccessibleTable): Current object(AccessibleTable) of Accessible Table.
        """
        info = AccessibleTableInfo()
        result = bool(
            self.bridge.getAccessibleTableRowHeader(
                vmid, accessible_context, byref(info)
            )
        )
        self.logger.debug(f"Get information about the table row header => {result}")
        dict_info = {
            "caption": info.caption,
            "summary": info.summary,
            "row_count": info.rowCount,
            "column_count": info.columnCount,
            "accessible_context": info.accessibleContext,
            "accessible_table": info.accessibleTable,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_table_column_header(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, Union[JOBJECT64, int]]:
        """Returns the table column headers of the specified table as a table.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.

        Returns:
            dict[str, Union[JOBJECT64, int]]: Dict of information about the table column header, contains:
                caption (JOBJECT64): caption of table.
                summary (JOBJECT64): summary of table.
                row_count (int): row count number of table.
                column_count (int): column count number of table.
                accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
                accessible_table (AccessibleTable): Current object(AccessibleTable) of Accessible Table.
        """
        info = AccessibleTableInfo()
        result = bool(
            self.bridge.getAccessibleTableColumnHeader(
                vmid, accessible_context, byref(info)
            )
        )
        self.logger.debug(f"Get information about the table column header => {result}")
        dict_info = {
            "caption": info.caption,
            "summary": info.summary,
            "row_count": info.rowCount,
            "column_count": info.columnCount,
            "accessible_context": info.accessibleContext,
            "accessible_table": info.accessibleTable,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_table_row_description(
        self, vmid: int, accessible_context: AccessibleContext, row: int
    ) -> AccessibleContext:
        """Returns the description of the specified row in the specified table.
        The row specifier is zero-based.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
            row (int): Index of row. Start from 0.

        Returns:
            AccessibleContext: Accessible Context of specified row description.
        """
        row_accessible_context: AccessibleContext = (
            self.bridge.getAccessibleTableRowDescription(vmid, accessible_context, row)
        )
        self.logger.debug(f"Get Accessible Context of specified row description")
        return row_accessible_context

    def get_accessible_table_column_description(
        self, vmid: int, accessible_context: AccessibleContext, column: int
    ) -> AccessibleContext:
        """Returns the description of the specified column in the specified table.
        The column specifier is zero-based.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
            column (int): Index of column. Start from 0.

        Returns:
            AccessibleContext: Accessible Context of specified column description.
        """
        column_accessible_context: AccessibleContext = (
            self.bridge.getAccessibleTableColumnDescription(
                vmid, accessible_context, column
            )
        )
        self.logger.debug(f"Get Accessible Context of specified column description")
        return column_accessible_context

    def get_accessible_table_row_selection_count(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> int:
        """Returns how many rows in the table are selected.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.

        Returns:
            int: How many rows in the table are selected.
        """
        count: int = self.bridge.getAccessibleTableRowSelectionCount(
            vmid, accessible_context
        )
        self.logger.debug(f"Get rows count in the table are selected => {count}")
        return count

    def is_accessible_table_row_selected(
        self, vmid: int, accessible_context: AccessibleContext, row: int
    ) -> bool:
        """Returns true if the specified zero based row is selected.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
            row (int): Index of row. Start from 0.

        Returns:
            bool: True if the specified row is selected False for Not.
        """
        result = bool(
            self.bridge.isAccessibleTableRowSelected(vmid, accessible_context, row)
        )
        self.logger.debug(f"Is {row} row selected => {result}")
        return result

    def get_accessible_table_row_selections(
        self, vmid: int, accessible_context: AccessibleContext
    ):
        """Returns an array of zero based indices of the selected rows(JABElement).

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.

        Returns:
            list[JABElement]: Array of zero based indices of the selected rows(JABElement).
        """
        selection_count = self.get_accessible_table_row_selection_count(
            vmid, accessible_context
        )
        selections = c_int()
        result = bool(
            self.bridge.getAccessibleTableRowSelections(
                vmid, accessible_context, selection_count, byref(selections)
            )
        )
        # TODO: selections.value is not correct, still need research row selections
        self.logger.debug(f"Get Accessible Table Row Selections => {result}")
        return selections.value

    def get_accessible_table_column_selection_count(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> int:
        """Returns how many columns in the table are selected.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.

        Returns:
            int: How many columns in the table are selected.
        """
        count: int = self.bridge.getAccessibleTableColumnSelectionCount(
            vmid, accessible_context
        )
        self.logger.debug(f"Get columns count in the table are selected => {count}")
        return count

    def is_accessible_table_column_selected(
        self, vmid: int, accessible_context: AccessibleContext, column: int
    ) -> bool:
        """Returns true if the specified zero based column is selected.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
            column (int): Index of column. Start from 0.

        Returns:
            bool: True if the specified column is selected False for Not.
        """
        result = bool(
            self.bridge.isAccessibleTableColumnSelected(
                vmid, accessible_context, column
            )
        )
        self.logger.debug(f"Is {column} column selected => {result}")
        return result

    def get_accessible_table_column_selections(
        self, vmid: int, accessible_context: AccessibleContext
    ):
        """Returns an array of zero based indices of the selected columns(JABElement).

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.

        Returns:
            list[JABElement]: Array of zero based indices of the selected columns(JABElement).
        """
        selection_count = self.get_accessible_table_column_selection_count(
            vmid, accessible_context
        )
        selections = c_int()
        result = bool(
            self.bridge.getAccessibleTableColumnSelections(
                vmid, accessible_context, selection_count, byref(selections)
            )
        )
        # TODO: selections.value is not correct, still need research column selections
        self.logger.debug(f"Get Accessible Table Column Selections => {result}")
        return selections.value

    def get_accessible_table_row(
        self, vmid: int, accessible_context: AccessibleContext, index: int
    ) -> int:
        """Returns the row number of the cell at the specified cell index. The values are zero based.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
            index (int): The specified cell index.

        Returns:
            int: The row number of the cell at the specified cell index.
        """
        number: int = self.bridge.getAccessibleTableRow(vmid, accessible_context)
        self.logger.debug(
            f"Get row number of the cell at specified cell index => {number}"
        )
        return number

    def get_accessible_table_column(
        self, vmid: int, accessible_context: AccessibleContext, index: int
    ) -> int:
        """Returns the column number of the cell at the specified cell index. The values are zero based.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
            index (int): The specified cell index.

        Returns:
            int: The column number of the cell at the specified cell index.
        """
        number: int = self.bridge.getAccessibleTableColumn(vmid, accessible_context)
        self.logger.debug(
            f"Get column number of the cell at specified cell index => {number}"
        )
        return number

    def get_accessible_table_index(
        self, vmid: int, accessible_context: AccessibleContext, row: int, column: int
    ) -> int:
        """Returns the index in the table of the specified row and column offset. The values are zero based.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object(AccessibleTable) of Accessible Context.
            row (int): The specified cell index of row.
            column (int): The specified cell index of column.

        Returns:
            int: The index in the table of the specified row and column offset.
        """
        index: int = self.bridge.getAccessibleTableIndex(
            vmid, accessible_context, row, column
        )
        self.logger.debug(
            f"Get index in the table of the specified row and column offset => {index}"
        )
        return index

    # Accessible Relation Set Function
    def get_accessible_relation_set(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, Union[str, int, AccessibleContext]]:
        """Returns information about an object's related objects.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            dict[str, Union[str, int, AccessibleContext]]: Dict information about an object's related objects.
                key (str): String text of key for Accessible Relation Set.
                target_count (int): Integer of count number for Accessible Relation Set.
                targets (list[AccessibleContext]): List of Accessible Context object for Accessible Relation Set.
        """
        info = AccessibleRelationInfo()
        result = bool(
            self.bridge.getAccessibleRelationSet(vmid, accessible_context, byref(info))
        )
        self.logger.debug(
            f"Get information about an object's related objects => {result}"
        )
        dict_info = {
            "key": info.key,
            "target_count": info.targetCount,
            "targets": info.targets,
        }
        self.logger.debug(dict_info)
        return dict_info

    # Accessible Hypertext Functions
    def get_accessible_hypertext(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, Union[int, list, AccessibleContext]]:
        """Returns hypertext information associated with a component.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            dict[str, Union[int, list, AccessibleContext]]: Dict of hypertext information associated with a component.
                link_count (int): Number of hyperlinks.
                links (list[AccessibleContext]): List of Accessible Context object for hyperlink.
                accessible_hypertext (AccessibleContext): Accessible Context object for Hypertext.
        """
        info = AccessibleHypertextInfo()
        result = bool(
            self.bridge.getAccessibleHypertext(vmid, accessible_context, byref(info))
        )
        self.logger.debug(
            f"Get hypertext information associated with a component => {result}"
        )
        dict_info = {
            "link_count": info.linkCount,
            "links": info.links,
            "accessible_hypertext": info.accessibleHypertext,
        }
        self.logger.debug(dict_info)
        return dict_info

    def activate_accessible_hyperlink(
        self,
        vmid: int,
        accessible_context: AccessibleContext,
        accessible_hyperlink: AccessibleContext,
    ) -> bool:
        """Requests that a hyperlink be activated.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            accessible_hyperlink (AccessibleContext): Current object of Accessible Context.

        Returns:
            bool: True if hyperlink be activated False for Not.
        """
        result = bool(
            self.bridge.activateAccessibleHyperlink(
                vmid, accessible_context, accessible_hyperlink
            )
        )
        self.logger.debug(f"Requests that a hyperlink be activated => {result}")
        return result

    def get_accessible_hyperlink_count(
        self, vmid: int, hypertext: AccessibleContext
    ) -> int:
        """Returns the number of hyperlinks in a component. Returns -1 on error.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            int: The number of hyperlinks in a component.
        """
        count = self.bridge.getAccessibleHyperlinkCount(vmid, hypertext)
        self.logger.debug(
            f"Requests the number of hyperlinks in a component => {count}"
        )
        return count

    def get_accessible_hypertext_ext(
        self, vmid: int, accessible_context: AccessibleContext, n_start_index: int
    ) -> dict[str, Union[int, list, AccessibleContext]]:
        """Iterates through the hyperlinks in a component.
        Returns hypertext information for a component starting at hyperlink index nStartIndex.
        No more than MAX_HYPERLINKS AccessibleHypertextInfo objects will be returned for each call to this method.
        Returns FALSE on error.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            n_start_index (int): The component starting at hyperlink index.

        Returns:
            dict[str, Union[int, list, AccessibleContext]]: Dict of hypertext information associated with a component.
                link_count (int): Number of hyperlinks.
                links (list[AccessibleContext]): List of Accessible Context object for hyperlink.
                accessible_hypertext (AccessibleContext): Accessible Context object for Hypertext.
        """
        info = AccessibleHypertextInfo()
        result = bool(
            self.bridge.getAccessibleHypertextExt(
                vmid, accessible_context, n_start_index, byref(info)
            )
        )
        self.logger.debug(
            f"Get hypertext information for a component starting at hyperlink index => {result}"
        )
        dict_info = {
            "link_count": info.linkCount,
            "links": info.links,
            "accessible_hypertext": info.accessibleHypertext,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_accessible_hypertext_link_index(
        self, vmid: int, hypertext: AccessibleContext, n_index: int
    ) -> int:
        """Returns the index into an array of hyperlinks that is associated with a character index in document.
        Maps to AccessibleHypertext.getLinkIndex.
        Returns -1 on error.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            n_index (int): The character index in document.

        Returns:
            int: The index into an array of hyperlinks.
        """
        count = self.bridge.getAccessibleHypertextLinkIndex(vmid, hypertext, n_index)
        self.logger.debug(f"Requests the index into an array of hyperlinks => {count}")
        return count

    def get_accessible_hyperlink(
        self, vmid: int, accessible_context: AccessibleContext, n_index: int
    ) -> AccessibleContext:
        """Returns the nth hyperlink in a document.
        Maps to AccessibleHypertext.getLink.
        Returns FALSE on error.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            n_index (int): The index of hyperlink in a document.

        Returns:
            AccessibleContext: The nth hyperlink(AccessibleContext object) in a document.
        """
        info = AccessibleHypertextInfo()
        result = bool(
            self.bridge.getAccessibleHyperlink(
                vmid, accessible_context, n_index, byref(info)
            )
        )
        self.logger.debug(f"Get the nth hyperlink in a document => {result}")
        hyperlink: AccessibleContext = info.accessibleHypertext
        return hyperlink

    # Accessible Key Binding Function
    def get_accessible_key_bindings(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, Union[int, list]]:
        """Returns a list of key bindings associated with a component.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            dict[str, Union[int, list]]: Dict of AccessibleKeyBindings information.
        """
        info = AccessibleKeyBindings()
        result = bool(
            self.bridge.getAccessibleKeyBindings(vmid, accessible_context, byref(info))
        )
        self.logger.debug(
            f"Get list of key bindings associated with a component => {result}"
        )
        dict_info = {
            "key_bindings_count": info.keyBindingsCount,
            "key_binding_info": info.keyBindingInfo,
        }
        self.logger.debug(dict_info)
        return dict_info

    # Accessible Icon Function
    def get_accessible_icons(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict[str, Union[int, list]]:
        """Returns a list of icons associate with a component.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            dict[str,Union[str,list]]: Dict of AccessibleIcons information.
        """
        info = AccessibleIcons()
        result = bool(
            self.bridge.getAccessibleIcons(vmid, accessible_context, byref(info))
        )
        self.logger.debug(f"Get AccessibleIcons information => {result}")
        dict_info = {"icons_count": info.iconsCount, "icon_info": info.iconInfo}
        self.logger.debug(dict_info)
        return dict_info

    # Accessible Action Functions
    def get_accessible_actions(
        self, vmid: int, accessible_context: AccessibleContext
    ) -> dict:
        """Returns a list of actions that a component can perform.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.

        Returns:
            dict[str,Union[int,AccessibleActionsToDo]]: Dict of AccessibleActions information.
        """
        info = AccessibleActions()
        result = bool(
            self.bridge.getAccessibleActions(vmid, accessible_context, byref(info))
        )
        self.logger.debug(f"Get AccessibleActions information => {result}")
        dict_info = {"actions_count": info.iconsCount, "action_info": info.iconInfo}
        self.logger.debug(dict_info)
        return dict_info

    def do_accessible_actions(
        self,
        vmid: int,
        accessible_context: AccessibleContext,
        actions_to_do: Optional[AccessibleActionsToDo] = None,
        failure: Optional[int] = None,
    ) -> bool:
        """Request that a list of AccessibleActions be performed by a component.
        Returns TRUE if all actions are performed.
        Returns FALSE when the first requested action fails in which case "failure" contains the index of the action that failed.

        Args:
            vmid (int): vmid of the given Java Object.
            accessible_context (AccessibleContext): Current object of Accessible Context.
            actions_to_do (AccessibleActionsToDo, optional): AccessibleActionsToDo object for list of AccessibleActions be performed.
            Defaults to None.
            failure (int, optional): index of the first fails action. Defaults to None.

        Returns:
            bool: True if all actions are performed False for Not.
        """

        acc_acts = self.get_accessible_actions(vmid, accessible_context)
        act_cnt: int = acc_acts.get("actions_count", 0)
        if act_cnt < 1:
            raise JABException("Current JABElement NOT support Accessible Action")
        acts_todo: AccessibleActionsToDo = actions_to_do or acc_acts.get(
            "action_info", AccessibleActionsToDo()
        )
        fail = failure or jint()
        rslt = bool(
            self.bridge.doAccessibleActions(
                vmid, accessible_context, byref(acts_todo), fail
            )
        )
        self.logger.debug(
            f"Request that a list of AccessibleActions be performed => {rslt}"
        )
        return rslt

    # Utility Functions
    def is_same_object(self, vmid: int, obj1: JOBJECT64, obj2: JOBJECT64) -> bool:
        """Returns whether two object references refer to the same object.

        Args:
            vmid (int): vmid of the given Java Object.
            obj1 (JOBJECT64): Java object 1.
            obj2 (JOBJECT64): Java object 2.

        Returns:
            bool: True for two object references refer to the same object False for Not.
        """
        rslt = bool(self.bridge.isSameObject(vmid, obj1, obj2))
        self.logger.debug(f"Two object references refer to the same object => {rslt}")
        return rslt

    def get_parent_with_role(
        self, vmid: int, acc_ctx: AccessibleContext, role: str
    ) -> AccessibleContext:
        """Returns the AccessibleContext with the specified role that is the ancestor of a given object.
        The role is one of the role strings defined in Java Access Bridge API Data Structures.
        If there is no ancestor object that has the specified role, returns (AccessibleContext)0.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.
            role (str): String text of role that is the ancestor of a given object.

        Returns:
            AccessibleContext: The Parent AccessibleContext with the specified role.
        """
        par_acc: AccessibleContext = self.bridge.getParentWithRole(vmid, acc_ctx, role)
        if par_acc == 0:
            raise JABException("JAB API 'getParentWithRole' Exception")
        self.logger.debug(f"Get Parent AccessibleContext with the specified role")
        return par_acc

    def get_parent_with_role_else_root(
        self, vmid: int, acc_ctx: AccessibleContext, role: str
    ) -> AccessibleContext:
        """Returns the AccessibleContext with the specified role that is the ancestor of a given object.
        The role is one of the role strings defined in Java Access Bridge API Data Structures.
        If an object with the specified role does not exist, returns the top level object for the Java window.
        Returns (AccessibleContext)0 on error.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.
            role (str): String text of role that is the ancestor of a given object.

        Returns:
            AccessibleContext: The Parent AccessibleContext with the specified role.
        """
        par_acc: AccessibleContext = self.bridge.getParentWithRoleElseRoot(
            vmid, acc_ctx, role
        )
        if par_acc == 0:
            raise JABException("JAB API 'getParentWithRoleElseRoot' Exception")
        self.logger.debug(f"Get Parent AccessibleContext with the specified role")
        return par_acc

    def get_top_level_object(
        self, vmid: int, acc_ctx: AccessibleContext
    ) -> AccessibleContext:
        """Returns the AccessibleContext for the top level object in a Java window.
        This is same AccessibleContext that is obtained from GetAccessibleContextFromHWND for that window.
        Returns (AccessibleContext)0 on error.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.

        Returns:
            AccessibleContext: The top level AccessibleContext.
        """
        top_acc_ctx: AccessibleContext = self.bridge.getTopLevelObject(vmid, acc_ctx)
        if top_acc_ctx == 0:
            raise JABException("JAB API 'getTopLevelObject' Exception")
        self.logger.debug(f"Get top level AccessibleContext")
        return top_acc_ctx

    def get_object_depth(self, vmid: int, acc_ctx: AccessibleContext) -> int:
        """Returns how deep in the object hierarchy a given object is.
        The top most object in the object hierarchy has an object depth of 0.
        Returns -1 on error.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.

        Returns:
            int: Integer of object depth.
        """
        obj_dpth: int = self.bridge.getObjectDepth(vmid, acc_ctx)
        if obj_dpth == -1:
            raise JABException("JAB API 'getObjectDepth' Exception")
        self.logger.debug(f"Get object depth => {obj_dpth}")
        return obj_dpth

    def get_active_descendent(
        self, vmid: int, acc_ctx: AccessibleContext
    ) -> AccessibleContext:
        """Returns the AccessibleContext of the current ActiveDescendent of an object.
        This method assumes the ActiveDescendent is the component that is currently selected in a container object.
        Returns (AccessibleContext)0 on error or if there is no selection.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.

        Returns:
            AccessibleContext: The AccessibleContext of the current ActiveDescendent.
        """
        act_dsc_acc_ctx: AccessibleContext = self.bridge.getActiveDescendent(
            vmid, acc_ctx
        )
        if act_dsc_acc_ctx == 0:
            raise JABException("JAB API 'getActiveDescendent' Exception")
        self.logger.debug(f"Get AccessibleContext of the current ActiveDescendent")
        return act_dsc_acc_ctx

    def request_focus(self, vmid: int, acc_ctx: AccessibleContext) -> bool:
        """Request focus for a component. Returns whether successful.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.

        Returns:
            bool: True for request focus success Fale for Not.
        """
        rslt = bool(self.bridge.requestFocus(vmid, acc_ctx))
        self.logger.debug(f"Request focus for component")
        return rslt

    def get_visible_children_count(self, vmid: int, acc_ctx: AccessibleContext) -> int:
        """Returns the number of visible children of a component. Returns -1 on error.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.

        Returns:
            int: Number of visible children count.
        """
        chn_cnt: int = self.bridge.getVisibleChildrenCount(vmid, acc_ctx)
        if chn_cnt == -1:
            raise JABException("JAB API 'getVisibleChildrenCount' Exception")
        self.logger.debug(f"Get number of visible children count => {chn_cnt}")
        return chn_cnt

    def get_visible_children(
        self,
        vmid: int,
        acc_ctx: AccessibleContext,
        idx: int,
        info: Optional[VisibleChildrenInfo] = None,
    ) -> dict:
        """Gets the visible children of an AccessibleContext. Returns whether successful.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.
            idx (int): Start index of visible children.
            info (VisibleChildrenInfo, optional): VisibleChildrenInfo object. Defaults to None.

        Returns:
            AccessibleContext: The visible children of an AccessibleContext.
        """
        info = info or VisibleChildrenInfo()
        rslt = bool(self.bridge.getVisibleChildren(vmid, acc_ctx, idx, byref(info)))
        if not rslt:
            raise JABException("JAB API 'getVisibleChildren' Exception")
        self.logger.debug(f"Get Visible Children Info")
        dict_info = {
            "returned_children_count": info.returnedChildrenCount,
            "children": info.children,
        }
        self.logger.debug(dict_info)
        return dict_info

    def get_events_waiting(self) -> int:
        """Gets the number of events waiting to fire.

        Returns:
            int: Number of events waiting.
        """
        evts: int = self.bridge.getEventsWaiting()
        self.logger.debug(f"Get Number of events waiting => {evts}")
        return evts

    # Accessible Value Functions
    # These functions get AccessibleValue information provided by the Java Accessibility API.
    # An AccessibleContext object has AccessibleValue information contained within it
    # if the flag accessibleValue in the AccessibleContextInfo data structure is set to TRUE.
    # The values returned are strings (char *value) because there is no way to tell in advance
    # if the value is an integer, a floating point value, or some other object that subclasses
    # the Java language construct java.lang.Number.
    def get_current_accessible_value_from_context(
        self,
        vmid: int,
        acc_ctx: AccessibleContext,
        value: Optional[Array[c_wchar]] = None,
        length: Optional[int] = None,
    ) -> int:
        """Get the value of this object as a Number. If the value has not been set, the return value will be null.

        Args:
            vmid (int): _description_
            acc_ctx (AccessibleContext): _description_
            value (Optional[Array[c_wchar]], optional): _description_. Defaults to None.
            length (Optional[int], optional): _description_. Defaults to None.

        Returns:
            int: value of the object
        """
        value = value or create_unicode_buffer(SHORT_STRING_SIZE + 1)
        length = length or SHORT_STRING_SIZE
        rslt = bool(
            self.bridge.getCurrentAccessibleValueFromContext(
                vmid, acc_ctx, value, SHORT_STRING_SIZE
            )
        )
        self.logger.debug(f"Get Number of events waiting => {rslt}")
        return value.value

    def get_maximum_accessible_value_from_context(
        self,
        vmid: int,
        acc_ctx: AccessibleContext,
        value: Optional[Array[c_wchar]] = None,
        length: Optional[int] = None,
    ) -> int:
        """Get the maximum value of this object as a Number.

        Args:
            vmid (int): _description_
            acc_ctx (AccessibleContext): _description_
            value (Optional[Array[c_wchar]], optional): _description_. Defaults to None.
            length (Optional[int], optional): _description_. Defaults to None.

        Returns:
            int: Maximum value of the object; null if this object does not have a maximum value
        """
        value = value or create_unicode_buffer(SHORT_STRING_SIZE + 1)
        length = length or SHORT_STRING_SIZE
        rslt = bool(
            self.bridge.getMaximumAccessibleValueFromContext(
                vmid, acc_ctx, value, SHORT_STRING_SIZE
            )
        )
        self.logger.debug(f"Get Number of events waiting => {rslt}")
        return value.value

    def get_minimum_accessible_value_from_context(
        self,
        vmid: int,
        acc_ctx: AccessibleContext,
        value: Optional[Array[c_wchar]] = None,
        length: Optional[int] = None,
    ) -> int:
        """Get the minimum value of this object as a Number.

        Args:
            vmid (int): _description_
            acc_ctx (AccessibleContext): _description_
            value (Optional[Array[c_wchar]], optional): _description_. Defaults to None.
            length (Optional[int], optional): _description_. Defaults to None.

        Returns:
            int: Minimum value of the object; null if this object does not have a minimum value
        """
        value = value or create_unicode_buffer(SHORT_STRING_SIZE + 1)
        length = length or SHORT_STRING_SIZE
        rslt = bool(
            self.bridge.getMinimumAccessibleValueFromContext(
                vmid, acc_ctx, value, SHORT_STRING_SIZE
            )
        )
        self.logger.debug(f"Get Number of events waiting => {rslt}")
        return value.value

    # Accessible Selection Functions
    # These functions get and manipulate AccessibleSelection information provided by the Java Accessibility API.
    # An AccessibleContext has AccessibleSelection information contained within it
    # if the flag accessibleSelection in the AccessibleContextInfo data structure is set to TRUE.
    # The AccessibleSelection support is the first place where the user interface can be manipulated,
    # as opposed to being queries, through adding and removing items from a selection.
    # Some of the functions use an index that is in child coordinates, while other use selection coordinates.
    # For example, add to remove from a selection by passing child indices
    # (for example, add the fourth child to the selection).
    # On the other hand, enumerating the selected children is done in selection coordinates
    # (for example, get the AccessibleContext of the first object selected).
    def add_accessible_selection_from_context(
        self, vmid: int, acc_ctx: AccessibleContext, i: int
    ) -> None:
        """Adds the specified Accessible child of the object to the object's selection.
        If the object supports multiple selections, the specified child is added to any existing selection,
        otherwise it replaces any existing selection in the object.
        If the specified child is already selected, this method has no effect.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.
            i (int): The zero-based index of the child.
        """
        self.logger.debug("Fire JAB API 'AddAccessibleSelectionFromContext'")
        self.bridge.addAccessibleSelectionFromContext(vmid, acc_ctx, i)

    def clear_accessible_selection_from_context(
        self, vmid: int, acc_ctx: AccessibleContext
    ) -> None:
        """Clears the selection in the object, so that no children in the object are selected.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.
        """
        self.logger.debug("Fire JAB API 'ClearAccessibleSelectionFromContext'")
        self.bridge.clearAccessibleSelectionFromContext(vmid, acc_ctx)

    def get_accessible_selection_from_context(
        self, vmid: int, acc_ctx: AccessibleContext, i: int
    ) -> AccessibleContext:
        """Returns an Accessible representing the specified selected child of the object.
        If there isn't a selection, or there are fewer children selected than the integer passed in,
        the return value will be null.
        Note that the index represents the i-th selected child, which is different from the i-th child.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.
            i (int): The zero-based index of selected children.

        Returns:
            AccessibleContext: The i-th selected child
        """
        self.logger.debug("Fire JAB API 'GetAccessibleSelectionFromContext'")
        acc_slctn: AccessibleContext = self.bridge.getAccessibleSelectionFromContext(
            vmid, acc_ctx, i
        )
        return acc_slctn

    def get_accessible_selection_count_from_context(
        self, vmid: int, acc_ctx: AccessibleContext
    ) -> int:
        """Returns the number of Accessible children currently selected.
        If no children are selected, the return value will be 0.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.

        Returns:
            int: The number of items currently selected.
        """
        self.logger.debug("Fire JAB API 'getAccessibleSelectionCountFromContext'")
        slctn_cnt: int = self.bridge.getAccessibleSelectionCountFromContext(
            vmid, acc_ctx
        )
        return slctn_cnt

    def is_accessible_child_selected_from_context(
        self, vmid: int, acc_ctx: AccessibleContext, i: int
    ) -> bool:
        """Determines if the current child of this object is selected.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.
            i (int): The zero-based index of the child in this Accessible object.

        Returns:
            bool: True if the current child of this object is selected; else False.
        """
        self.logger.debug("Fire JAB API 'isAccessibleChildSelectedFromContext'")
        is_sel: bool = self.bridge.isAccessibleChildSelectedFromContext(
            vmid, acc_ctx, i
        )
        return is_sel

    def remove_accessible_selection_from_context(
        self, vmid: int, acc_ctx: AccessibleContext, i: int
    ) -> None:
        """Removes the specified child of the object from the object's selection.
        If the specified item isn't currently selected, this method has no effect.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.
            i (int): The zero-based index of the child.
        """
        self.logger.debug("Fire JAB API 'removeAccessibleSelectionFromContext'")
        self.bridge.removeAccessibleSelectionFromContext(vmid, acc_ctx, i)

    def select_all_accessible_selection_from_context(
        self, vmid: int, acc_ctx: AccessibleContext
    ) -> None:
        """Causes every child of the object to be selected if the object supports multiple selections.

        Args:
            vmid (int): vmid of the given Java Object.
            acc_ctx (AccessibleContext): Current object of Accessible Context.
        """
        self.logger.debug("Fire JAB API 'selectAllAccessibleSelectionFromContext'")
        self.bridge.selectAllAccessibleSelectionFromContext(vmid, acc_ctx)
