"""Java Access Bridge API Calls"""
from ctypes import (
    CDLL,
    byref,
    c_int,
    c_long,
    c_short,
    create_string_buffer,
    create_unicode_buffer,
)
from ctypes.wintypes import HWND
from typing import Sequence, Union
from pyjab.common.exceptions import JABException
from pyjab.jab.structure import (
    MAX_ACTIONS_TO_DO,
    SHORT_STRING_SIZE,
    AccessBridgeVersionInfo,
    AccessibleActionInfo,
    AccessibleActions,
    AccessibleActionsToDo,
    AccessibleContextInfo,
    AccessibleHyperlinkInfo,
    AccessibleHypertextInfo,
    AccessibleIconInfo,
    AccessibleIcons,
    AccessibleKeyBindingInfo,
    AccessibleKeyBindings,
    AccessibleRelationInfo,
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
from pyjab.jab.type import (
    JOBJECT64,
    AccessibleContext,
    AccessibleHyperlink,
    AccessibleHypertext,
    AccessibleSelection,
    AccessibleTable,
    AccessibleText,
    AccessibleValue,
    jint,
)


class API(object):
    """Java Access Bridge API calls in Python.
    The file AccessBridgeCalls.h contains the Java Access Bridge API calls.
    To use them, compile the file AccessBridgeCalls.c.
    The Java Access Bridge API calls act as the interface between
    your application and WindowsAccessBridge.dll.
    """

    def __init__(self, bridge: CDLL) -> None:
        self.bridge = bridge
        self.logger = Logger()

    # Gateway Functions

    def is_java_window(self, hwnd: HWND) -> bool:
        """Checks if the given HWND is a top-level Java Window.

        Notice: 
            Just because the Windnow is a top-level Java window, 
            that doesn't mean that it is accessible.
            Call getAccessibleContextFromHWND(HWND) to get the
            AccessibleContext, if any, for an HWND that is a Java Window.

        Args:
            hwnd (HWND): HWND for the window.

        Returns:
            bool: True for given HWND is Java Window False for NOT.
        """
        self.logger.debug(f"Run JAB API isJavaWindow with hwnd: {hwnd}")
        rslt = bool(self.bridge.isJavaWindow(hwnd))
        self.logger.debug(f"JAB API isJavaWindow return => {rslt}")
        return rslt

    def get_accessible_context_from_hwnd(
        self,
        hwnd: HWND
    ) -> tuple[AccessibleContext, c_long]:
        """Gets the AccessibleContext and vmid values for the given window.

        Notice:
            This routine can return null, even if the HWND is a Java Window,
            because the Java Window may not be accessible.

        Args:
            hwnd (HWND): HWND for the window.

        Raise:
            JABException: getAccessibleContextFromHWND result Failed.

        Returns:
            Tuple (AccessibleContext, c_long): Tuple of AccessibleContext
            and vmid for the given window.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleContextFromHWND with hwnd: {hwnd}"
        )
        vmid = c_long()
        acc_ctx = AccessibleContext()
        rslt = bool(self.bridge.getAccessibleContextFromHWND(
            hwnd, byref(vmid), byref(acc_ctx)
        ))
        if not rslt:
            raise JABException(
                "JAB API getAccessibleContextFromHWND result Failed")
        rtn = acc_ctx, vmid
        self.logger.debug(
            f"JAB API getAccessibleContextFromHWND return => {rtn}"
        )
        return rtn

    # General Functions
    def release_java_object(
        self, vmid: c_long, jobj: JOBJECT64
    ) -> None:
        """Release the memory used by the Java object object,
        where object is an object returned to you by Java Access Bridge.
        Java Access Bridge automatically maintains a reference to all Java objects that it returns to you in the JVM so they are not garbage collected.
        To prevent memory leaks, call ReleaseJavaObject on all Java objects returned to you by Java Access Bridge once you are finished with them.

        Args:
            vmid (c_long): VMID for the given Java Object.

            jobj (JOBJECT64): Java Object need to release.
        """
        self.logger.debug(
            f"Run JAB API releaseJavaObject with vmid: {vmid}, jobj: {jobj}"
        )
        self.bridge.releaseJavaObject(vmid, jobj)

    def get_version_info(
        self,
        vmid: c_long
    ) -> dict[str, str]:
        """Gets the version information of the instance of Java Access Bridge instance your application is using. 
        You can use this information to determine the available functionality of your version of Java Access Bridge.

        Args:
            vmid (c_long): VMID for the given Java Object.

        Raise:
            JABException: getVersionInfo result Failed.

        Returns:
            dict[str,str]: Dict of AccessBridgeVersionInfo, contains:
                vm_version (str): Version of the Java VM.

                bridge_java_class_version (str): Version of
                AccessBridge.class.

                bridge_java_dll_version (str): Version of
                JavaAccessBridge.dll.

                bridge_win_dll_version (str): Version of
                WindowsAccessBridge.dll.
        """
        self.logger.debug(
            f"Run JAB API getVersionInfo with vmid: {vmid}"
        )
        info = AccessBridgeVersionInfo()
        rslt = bool(self.bridge.getVersionInfo(vmid, byref(info)))
        if not rslt:
            raise JABException("JAB API getVersionInfo result Failed")
        dict_info = {
            "vm_version": info.VMVersion,
            "bridge_java_class_version": info.bridgeJavaClassVersion,
            "bridge_java_dll_version": info.bridgeJavaDLLVersion,
            "bridge_win_dll_version": info.bridgeWinDLLVersion,
        }
        self.logger.debug(f"JAB API getVersionInfo return => {dict_info}")
        return dict_info

    # Accessible Context Functions
    def get_accessible_context_at(
        self,
        vmid: c_long,
        par_ac: AccessibleContext,
        x: int,
        y: int,
    ) -> AccessibleContext:
        """Retrieves an AccessibleContext object of the window or object that is under the mouse pointer.

        Args:
            vmid (c_long): VMID for the given Java Object.

            par_ac (AccessibleContext): Parent AccessibleContext Object.

            x (int): Mouse pointer position x.

            y (int): Mouse pointer position y.

        Raise:
            JABException: getAccessibleContextAt result Failed.

        Returns:
            AccessibleContext: AccessibleContext under the mouse pointer.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleContextAt with "
            f"vmid: {vmid}, par_ac: {par_ac}, x: {x}, y: {y}"
        )
        acc_ctx = AccessibleContext()
        rslt = bool(self.bridge.getAccessibleContextAt(
            vmid, par_ac, jint(x), jint(y), byref(acc_ctx)))
        if not rslt:
            raise JABException("JAB API getAccessibleContextAt result Failed")
        self.logger.debug(
            f"JAB API getAccessibleContextAt return => {acc_ctx}")
        return acc_ctx

    def get_accessible_context_with_focus(
        self,
        hwnd: HWND
    ) -> AccessibleContext:
        """Retrieves an AccessibleContext object of the window or object that has the focus.

        Args:
            hwnd (HWND): HWND for the window.

        Raise:
            JABException: getAccessibleContextWithFocus result Failed.

        Returns:
            AccessibleContext: AccessibleContext that has the focus.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleContextWithFocus with hwnd: {hwnd}"
        )
        vmid = c_long()
        acc_ctx = AccessibleContext()
        rslt = bool(self.bridge.getAccessibleContextWithFocus(
            hwnd, byref(vmid), byref(acc_ctx)
        ))
        if not rslt:
            raise JABException(
                "JAB API getAccessibleContextWithFocus result Failed")
        self.logger.debug(
            f"JAB API getAccessibleContextWithFocus return => {acc_ctx}"
        )
        return acc_ctx

    def get_accessible_context_info(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, Union[str, int, bool, list[str]]]:
        """Retrieves an AccessibleContextInfo object of the AccessibleContext object ac.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Raise:
            JABException: getAccessibleContextInfo result Failed.

        Returns:
            dict[str, Union[str, int, bool, list]]:
            Dict of AccessibleContextInfo, contains:
                name (str): Localized String containing the name.

                description (str): Localized String containing the description.

                role (str): Localized String role.

                role_en_us (str): English String role.

                states (list[str]): Localized Strings states.

                states_en_us (list[str]): English Strings states.

                index_in_parent (int): 0-based index in its accessible parent.

                children_count (int): Number of accessible children.

                x (int): Screen x-axis co-ordinate in pixels.

                y (int): Screen y-axis co-ordinate in pixels.

                width (int): Pixel width of object.

                height (int): Pixel height of object.

                accessible_component (bool): Flag for support AccessibleCompoent.

                accessible_action (bool): Flag for support AccessibleAction.

                accessible_text (bool): Flag for support AccessibleText.

                accessible_interfaces (bool): Flag for support accessibleInterfaces.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleContextInfo with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        info = AccessibleContextInfo()
        rslt = bool(self.bridge.getAccessibleContextInfo(
            vmid, acc_ctx, byref(info)))
        if not rslt:
            raise JABException(
                "JAB API getAccessibleContextInfo result Failed")
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
        self.logger.debug(
            f"JAB API getAccessibleContextInfo return => {dict_info}"
        )
        return dict_info

    def get_accessible_child_from_context(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        idx: int,
    ) -> AccessibleContext:
        """Returns the specified Accessible child of the object. 
        The Accessible children of an Accessible object are zero-based, 
        so the first child of an Accessible child is at index 0, 
        the second child is at index 1, and so on.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            idx (int): Index number of specific child.

        Returns:
            AccessibleContext: The specified child of the object.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleChildFromContext with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, index: {idx}"
        )
        chd_ac: AccessibleContext = self.bridge.getAccessibleChildFromContext(
            vmid, acc_ctx, jint(idx)
        )
        self.logger.debug(
            f"JAB API getAccessibleChildFromContext return => {chd_ac}"
        )
        return chd_ac

    def get_accessible_parent_from_context(
        self, vmid: c_long, acc_ctx: AccessibleContext
    ) -> AccessibleContext:
        """Gets the Accessible parent of this object.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Returns:
            AccessibleContext: The parent object.
        """
        self.logger.debug(
            "Run JAB API getAccessibleParentFromContext with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        par_ac: AccessibleContext = self.bridge.getAccessibleParentFromContext(
            vmid, acc_ctx
        )
        self.logger.debug(
            f"JAB API getAccessibleParentFromContext return => {par_ac}"
        )
        return par_ac

    def get_hwnd_from_accessible_context(
        self, vmid: c_long, acc_ctx: AccessibleContext
    ) -> HWND:
        """Returns the HWND from the AccessibleContext of a top-level window.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Raise:
            JABException: getHWNDFromAccessibleContext return None.

        Returns:
            HWND: HWND for the window.
        """
        self.logger.debug(
            "Run JAB API getHWNDFromAccessibleContext with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        hwnd: HWND = self.bridge.getHWNDFromAccessibleContext(vmid, acc_ctx)
        if hwnd.value is None:
            raise JABException(
                "JAB API getHWNDFromAccessibleContext return None"
            )
        self.logger.debug(
            f"JAB API getHWNDFromAccessibleContext return => {hwnd}"
        )
        return hwnd

    # Accessible Text Functions
    def get_accessible_text_info(
        self,
        vmid: c_long,
        acc_txt: AccessibleText,
        x: int,
        y: int,
    ) -> dict[str, int]:
        """Retrieves an AccessibleTextInfo object from AccessibleText object.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_txt (AccessibleText): The given AccessibleText object.

            x (int, optional): Screen x-axis co-ordinate in pixels.

            y (int, optional): Screen y-axis co-ordinate in pixels.

        Raise:
            JABException: getAccessibleTextInfo result Failed.

        Returns:
            dict[str,int]: Dict of AccessibleText Infomation, contains:
                char_count (int): Number of characters in this text object.

                caret_index (int): Index of caret in this text object.

                index_at_point (int): Index at point in this text object.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTextInfo with "
            f"vmid: {vmid}, acc_txt: {acc_txt}, x: {x}, y: {y}"
        )
        info = AccessibleTextInfo()
        rslt = bool(self.bridge.getAccessibleTextInfo(
            vmid, acc_txt, byref(info), jint(x), jint(y)))
        if not rslt:
            raise JABException("JAB API getAccessibleTextInfo result Failed")
        dict_info = {
            "char_count": info.charCount,
            "caret_index": info.caretIndex,
            "index_at_point": info.indexAtPoint,
        }
        self.logger.debug(
            f"JAB API getAccessibleTextInfo return => {dict_info}"
        )
        return dict_info

    def get_accessible_text_items(
        self,
        vmid: c_long,
        acc_txt: AccessibleText,
        idx: int,
    ) -> dict[str, str]:
        """Retrieves an AccessibleTextItemsInfo object from AccessibleText object.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_txt (AccessibleText): The given AccessibleText object.

            idx (int): Index text in AccessibleText.

        Raise:
            JABException: getAccessibleTextItems result Failed.

        Returns:
            dict[str, str]:
            Dict of AccessibleTextItemsInfo, contains:
                letter (str): String of letter in this text object.

                word (str): String of word in this text object.

                sentence (str): String of sentence in this text object.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTextItems with "
            f"vmid: {vmid}, acc_txt: {acc_txt}, index: {idx}"
        )
        info = AccessibleTextItemsInfo()
        rslt = bool(self.bridge.getAccessibleTextItems(
            vmid, acc_txt, byref(info), jint(idx)))
        if not rslt:
            raise JABException("JAB API getAccessibleTextItems result Failed")
        dict_info = {
            "letter": info.letter,
            "word": info.word,
            "sentence": info.sentence,
        }
        self.logger.debug(
            f"JAB API getAccessibleTextItems return => {dict_info}"
        )
        return dict_info

    def get_accessible_text_selection_info(
        self,
        vmid: c_long,
        acc_txt: AccessibleText,
    ) -> dict[str, Union[int, str]]:
        """Retrieves an AccessibleTextSelectionInfo object from AccessibleText object.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_txt (AccessibleText): The given AccessibleText object.

        Raise:
            JABException: getAccessibleTextSelectionInfo result Failed.

        Returns:
            dict[str,Union[int,str]]:
            Dict of AccessibleTextSelectionInfo, contains:
                selection_start_index (int): Start index of selection text
                in this text object.

                selection_end_index (int): End index of selection text
                in this text object.

                selected_text (str): String of selection text in this text object.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTextSelectionInfo with "
            f"vmid: {vmid}, acc_txt: {acc_txt}"
        )
        info = AccessibleTextSelectionInfo()
        rslt = bool(self.bridge.getAccessibleTextSelectionInfo(
            vmid, acc_txt, byref(info)))
        if not rslt:
            raise JABException(
                "JAB API getAccessibleTextSelectionInfo result Failed")
        dict_info = {
            "selection_start_index": info.selectionStartIndex,
            "selection_end_index": info.selectionEndIndex,
            "selected_text": info.selectedText,
        }
        self.logger.debug(
            f"JAB API getAccessibleTextSelectionInfo return => {dict_info}"
        )
        return dict_info

    def get_accessible_text_attributes(
        self,
        vmid: c_long,
        acc_txt: AccessibleText,
        idx: int,
    ) -> dict[str, Union[bool, str, int, float]]:
        """Retrieves an AccessibleTextAttributesInfo object from AccessibleText object.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_txt (AccessibleText): The given AccessibleText object.

            idx (int): Index of text in AccessibleText.

        Raise:
            JABException: getAccessibleTextAttributes result Failed.

        Returns:
            dict[str, Union[bool, str, int, float]]:
            Dict of AccessibleTextAttributesInfo, contains:
                bold (bool): Text object is bold style or not.

                italic (bool): Text object is italic style or not.

                underline (bool): Text object is underline style or not.

                strikethrough (bool): Text object is strikethrough style or not.

                superscript (bool): Text object is superscript style or not.

                subscript (bool): Text object is subscript style or not.

                background_color (str): Text object background color.

                foreground_color (str): Text object foreground color.

                font_family (str): Text object font family.

                font_size (int): Text object font size.

                alignment (int): Text object alignment.

                bidi_level (int): Text object bidi level.

                first_line_indent (float): Text object first line indent.

                left_indent (float): Text object left indent.

                right_indent (float): Text object right indent.

                line_spacing (float): Text object line spacing.

                space_above (float): Text object space above.

                space_below (float): Text object space below.

                full_attributes_string (float): Text object full attributes string.
        """
        self.logger.debug(
            f"Run JAB API GetAccessibleTextAttributes with "
            f"vmid: {vmid}, acc_txt: {acc_txt}, index: {idx}"
        )
        info = AccessibleTextAttributesInfo()
        rslt = bool(self.bridge.getAccessibleTextAttributes(
            vmid, acc_txt, jint(idx), byref(info)))
        if not rslt:
            raise JABException(
                "JAB API GetAccessibleTextAttributes result Failed")
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
        self.logger.debug(
            f"JAB API GetAccessibleTextAttributes return => {dict_info}"
        )
        return dict_info

    def get_accessible_text_rect(
        self,
        vmid: c_long,
        acc_txt: AccessibleText,
        idx: int,
    ) -> dict[str, int]:
        """Retrieves an AccessibleTextRect object from AccessibleText object.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_txt (AccessibleText): The given AccessibleText object.

            index (int): Index of AccessibleText text.

        Raise:
            JABException: getAccessibleTextRect result Failed.

        Returns:
            dict[str,int]: Dict of AccessibleTextRect, contains:
                x (int): Bounding rectangle x-axis co-ordinate of char at index.

                y (int): Bounding rectangle y-axis co-ordinate of char at index.

                width (int): Bounding rectangle width in this text object.

                height (int): Bounding rectangle height in this text object.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTextRect with "
            f"vmid: {vmid}, acc_txt: {acc_txt}, index: {idx}"
        )
        info = AccessibleTextRectInfo()
        rslt = bool(self.bridge.getAccessibleTextRect(
            vmid, acc_txt, byref(info), jint(idx)))
        if not rslt:
            raise JABException("JAB API getAccessibleTextRect result Failed")
        dict_info = {
            "x": info.x,
            "y": info.y,
            "width": info.width,
            "height": info.height,
        }
        self.logger.debug(
            f"JAB API getAccessibleTextRect return => {dict_info}"
        )
        return dict_info

    def get_accessible_text_range(
        self,
        vmid: c_long,
        acc_txt: AccessibleText,
        start: int,
        end: int
    ) -> str:
        """Retrieves range of text from AccessibleText object.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_txt (AccessibleText): The given AccessibleText object.

            start (int): Start Index of range text at text object.

            end (int): End Index of range text at text object.

        Raise:
            JABException: getAccessibleTextRange result Failed.

        Returns:
            str: A range of text.
        """
        length = end + 1 - start
        if length <= 0:
            return ""
        # Use a string buffer, as from an unicode buffer, we can't get the raw data.
        buf = create_string_buffer((length + 1) * 2)
        self.logger.debug(
            "Run JAB API getAccessibleTextRange with "
            f"vmid: {vmid}, acc_txt: {acc_txt}, start: {start}, end: {end}, "
        )
        rslt = bool(self.bridge.getAccessibleTextRange(
            vmid, acc_txt, start, end, buf, c_short(length)
        ))
        if not rslt:
            raise JABException("JAB API getAccessibleTextRange result Failed")
        txt = TextReader.get_text_from_raw_bytes(
            buf.raw, length, WCHAR_ENCODING
        )
        self.logger.debug(f"JAB API getAccessibleTextRange return => {txt}")
        return txt

    def get_accessible_text_line_bounds(
        self,
        vmid: c_long,
        acc_txt: AccessibleText,
        idx: int,
    ) -> tuple[int, int]:
        """Retrieves line bounds from AccessibleText object.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_txt (AccessibleText): The given AccessibleText object.

            idx (int): Index of AccessibleText text.

        Raise:
            JABException: getAccessibleTextLineBounds result Failed.

        Returns:
            tuple (int, int): Line bounds of AccessibleText object.
        """
        idx = max(idx, 0)
        self.logger.debug(f"Line bounds index {idx}")
        start_idx = jint()
        end_idx = jint()
        # Java returns end as the last character, not end as past the last character
        self.logger.debug(
            "Run JAB API getAccessibleTextLineBounds with "
            f"vmid: {vmid}, acc_txt: {acc_txt}, idx: {idx}"
        )
        rslt = bool(
            self.bridge.getAccessibleTextLineBounds(
                vmid,
                acc_txt,
                jint(idx),
                byref(start_idx),
                byref(end_idx),
            )
        )
        if not rslt:
            raise JABException(
                "JAB API getAccessibleTextLineBounds result Failed")
        start_val = start_idx.value
        end_val = end_idx.value
        self.logger.debug(f"Line bounds: start {start_val}, end {end_val}")
        if end_val < start_val or start_val < 0:
            # Invalid or empty line.
            self.logger.debug("Reutrn tuple value: (0, -1)")
            return (0, -1)
        # OpenOffice sometimes returns offsets encompassing more than one line, so try to narrow them down.
        # Try to retract the end offset.
        flag_ok = False
        while not flag_ok:
            self.logger.debug(
                "Run JAB API getAccessibleTextLineBounds with "
                f"vmid: {vmid}, acc_txt: {acc_txt}, idx: {end_val}"
            )
            rslt = bool(self.bridge.getAccessibleTextLineBounds(
                vmid,
                acc_txt,
                jint(end_val),
                byref(start_idx),
                byref(end_idx),
            ))
            if not rslt:
                raise JABException(
                    "JAB API getAccessibleTextLineBounds result Failed")
            temp_start = max(start_idx.value, 0)
            temp_end = max(end_idx.value, 0)
            self.logger.debug(
                f"Line bounds: temp start {temp_start}, temp end {temp_end}"
            )
            if temp_start > (idx + 1):
                # This line starts after the requested index, so set end to point at the line before.
                end_val = temp_start - 1
            else:
                flag_ok = True
        flag_ok = False
        # Try to retract the start.
        while not flag_ok:
            self.logger.debug(
                "Run JAB API getAccessibleTextLineBounds with "
                f"vmid: {vmid}, acc_txt: {acc_txt}, idx: {start_val}"
            )
            rslt = bool(self.bridge.getAccessibleTextLineBounds(
                vmid,
                acc_txt,
                jint(start_val),
                byref(start_idx),
                byref(end_idx),
            ))
            if not rslt:
                raise JABException(
                    "JAB API getAccessibleTextLineBounds result Failed")
            temp_start = max(start_idx.value, 0)
            temp_end = max(end_idx.value, 0)
            self.logger.debug(
                f"Line bounds: temp start {temp_start}, temp end {temp_end}"
            )
            if temp_end < (idx - 1):
                # This line ends before the requested index, so set start to point at the line after.
                start_val = temp_end + 1
            else:
                flag_ok = True
        self.logger.debug(
            f"JAB API getAccessibleTextLineBounds return => {(start_val, end_val)}"
        )
        return (start_val, end_val)

    # Additional Text Functions
    def select_text_range(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        start: int,
        end: int,
    ) -> bool:
        """Selects text between two indices.
        Selection includes the text at the start index 
        and the text at the end index. 
        Returns whether successful.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            start (int): Start index of text need to selected.

            end (int): End index of text need to selected.

        Raise:
            JABException: selectTextRange result Failed.

        Returns:
            bool: True for select text range success False for not.
        """
        self.logger.debug(
            f"Run JAB API selectTextRange with "
            f"vmid: {vmid}, ac: {acc_ctx}, start: {start}, end: {end}"
        )
        rslt = bool(self.bridge.selectTextRange(
            vmid, acc_ctx, c_int(start), c_int(end)))
        if not rslt:
            JABException("JAB API selectTextRange result Failed")
        self.logger.debug(f"JAB API selectTextRange return => {rslt}")
        return rslt

    def get_text_attributes_in_range(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        start: int,
        end: int,
    ) -> dict[str, Union[bool, str, int, float]]:
        """Get text attributes between two indices.
        The attribute list includes the text at the start index and the text at the end index.
        Returns whether successful.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            start (int): Start index of text need to selected.

            end (int): End index of text need to selected.

        Raise:
            JABException: getTextAttributesInRange result Failed.

        Returns:
            dict[str,Union[bool, str, int]]:
            Dict of AccessibleTextAttributesInfo, contains:
                bold (bool): Text object is bold style or not.

                italic (bool): Text object is italic style or not.

                underline (bool): Text object is underline style or not.

                strikethrough (bool): Text object is strikethrough style or not.

                superscript (bool): Text object is superscript style or not.

                subscript (bool): Text object is subscript style or not.

                background_color (str): Text object background color.

                foreground_color (str): Text object foreground color.

                font_family (str): Text object font family.

                font_size (int): Text object font size.

                alignment (int): Text object alignment.

                bidi_level (int): Text object bidi level.

                first_line_indent (float): Text object first line indent.

                left_indent (float): Text object left indent.

                right_indent (float): Text object right indent.

                line_spacing (float): Text object line spacing.

                space_above (float): Text object space above.

                space_below (float): Text object space below.

                full_attributes_string (float): Text object of full attributes string.
        """
        self.logger.debug(
            "Run JAB API getTextAttributesInRange with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, start: {start}, end: {end}"
        )
        info = AccessibleTextAttributesInfo()
        length = c_short()
        rslt = bool(
            self.bridge.getTextAttributesInRange(
                vmid,
                acc_ctx,
                c_int(start),
                c_int(end),
                byref(info),
                byref(length),
            )
        )
        if not rslt:
            JABException(f"JAB API getTextAttributesInRange result Failed")
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
        self.logger.debug(f"JAB API getTextAttributesInRange return => {rslt}")
        return dict_info

    def set_caret_position(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        idx: int,
    ) -> None:
        """Set the caret to a text position.
        Returns whether successful.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            idx (int): Index of caret position at text object.
        """
        self.logger.debug(
            f"Run JAB API setCaretPosition with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, idx: {idx}"
        )
        rslt = bool(self.bridge.setCaretPosition(vmid, acc_ctx, c_int(idx)))
        if not rslt:
            JABException(f"JAB API setCaretPosition result Failed")

    def get_caret_location(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, int]:
        """Gets the text caret location.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Raise:
            JABException: getCaretLocation result Failed.

        Returns:
            dict[str, int]: Dict of the text caret location, contains:
                x (int): Bounding rectangle x-axis co-ordinate of char at index.

                y (int): Bounding rectangle y-axis co-ordinate of char at index.

                width (int): Bounding rectangle width in this text object.

                height (int): Bounding rectangle height in this text object.
        """
        self.logger.debug(
            f"Run JAB API getCaretLocation with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        info = AccessibleTextRectInfo()
        idx = jint()
        rslt = bool(
            self.bridge.getCaretLocation(
                vmid, acc_ctx, byref(info), idx)
        )
        if not rslt:
            JABException(f"JAB API getCaretLocation result Failed")
        dict_info = {
            "x": info.x,
            "y": info.y,
            "width": info.width,
            "height": info.height,
        }
        self.logger.debug(f"JAB API getCaretLocation return => {dict_info}")
        return dict_info

    def set_text_contents(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        txt: str,
    ) -> None:
        """Sets editable text contents.
        The AccessibleContext must implement AccessibleEditableText and be editable.
        The maximum text length that can be set is MAX_STRING_SIZE - 1.
        Returns whether successful.

        NOTICE: Use create_unicode_buffer to get text to input.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            txt (str): String of text need to set.

        Raise:
            JABException: setTextContents result Failed.
        """
        self.logger.debug(
            f"Run JAB API setTextContents with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, txt: {txt}"
        )
        rslt = bool(self.bridge.setTextContents(
            vmid, acc_ctx, create_unicode_buffer(txt)))
        if not rslt:
            raise JABException("JAB API setTextContents result Failed")

    # Accessible Table Functions
    def get_accessible_table_info(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, Union[JOBJECT64, int]]:
        """Returns information about the table,
        for example, caption, summary, row and column count,
        and the AccessibleTable.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Raise:
            JABException: getAccessibleTableInfo result Failed.

        Returns:
            dict[str, Union[JOBJECT64, int]]:
            Dict of information about the table, contains:
                caption (JOBJECT64): caption of table.

                summary (JOBJECT64): summary of table.

                row_count (int): row count number of table.

                column_count (int): column count number of table.

                accessible_context (JOBJECT64): AccessibleContext object.

                accessible_table (JOBJECT64): AccessibleTable object.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTableInfo with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        info = AccessibleTableInfo()
        rslt = bool(
            self.bridge.getAccessibleTableInfo(vmid, acc_ctx, byref(info))
        )
        if not rslt:
            JABException("JAB API getAccessibleTableInfo result Failed")
        dict_info = {
            "caption": info.caption,
            "summary": info.summary,
            "row_count": info.rowCount,
            "column_count": info.columnCount,
            "accessible_context": info.accessibleContext,
            "accessible_table": info.accessibleTable,
        }
        self.logger.debug(
            f"JAB API getAccessibleTableInfo return => {dict_info}"
        )
        return dict_info

    def get_accessible_table_cell_info(
        self,
        vmid: c_long,
        acc_tbl: AccessibleTable,
        row: int,
        column: int,
    ) -> dict[str, Union[AccessibleContext, int, bool]]:
        """Returns information about the specified table cell.
        The row and column specifiers are zero-based.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

            row (int): Index of cell in row.

            column (int): Index of cell in column.

        Raise:
            JABException: getAccessibleTableCellInfo result Failed.

        Returns:
            dict[str, Union[AccessibleContext, int, bool]]:
            Dict of information about the cell, contains:
                accessible_context (AccessibleContext): The given Java Object.

                index (int): Index of cell in table.

                row (int): Index of cell in row.

                column (int): Index of cell in column.

                row_extent (int): Extent of cell in row.

                column_extent (int): Extent of cell in column.

                is_selected (bool): Cell is selected or not.

        """
        self.logger.debug(
            f"Run JAB API getAccessibleTableCellInfo with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}, row: {row}, column: {column}"
        )
        info = AccessibleTableInfo()
        rslt = bool(
            self.bridge.getAccessibleTableCellInfo(
                vmid, acc_tbl, jint(row), jint(column), byref(info)
            )
        )
        if not rslt:
            JABException(f"JAB API getAccessibleTableCellInfo result Failed")
        dict_info = {
            "accessible_context": info.accessibleContext,
            "index": info.index,
            "row": info.row,
            "column": info.column,
            "row_extent": info.rowExtent,
            "column_extent": info.columnExtent,
            "is_selected": info.isSelected,
        }
        self.logger.debug(
            f"JAB API getAccessibleTableCellInfo return => {dict_info}"
        )
        return dict_info

    def get_accessible_table_row_header(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, Union[JOBJECT64, int]]:
        """Returns the table row headers of the specified table as a table.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): Parent Java object.

        Returns:
            dict[str, Union[JOBJECT64, int]]:
            Dict of information about the table row header, contains:
                caption (JOBJECT64): caption of table.

                summary (JOBJECT64): summary of table.

                row_count (int): row count number of table.

                column_count (int): column count number of table.

                accessible_context (JOBJECT64): AccessibleContext object.

                accessible_table (JOBJECT64): AccessibleTable object.
        """
        self.logger.debug(
            "Run JAB API getAccessibleTableRowHeader with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        info = AccessibleTableInfo()
        rslt = bool(
            self.bridge.getAccessibleTableRowHeader(vmid, acc_ctx, byref(info))
        )
        if not rslt:
            JABException("JAB API getAccessibleTableRowHeader result Failed")
        dict_info = {
            "caption": info.caption,
            "summary": info.summary,
            "row_count": info.rowCount,
            "column_count": info.columnCount,
            "accessible_context": info.accessibleContext,
            "accessible_table": info.accessibleTable,
        }
        self.logger.debug(
            f"JAB API getAccessibleTableRowHeader return => {dict_info}"
        )
        return dict_info

    def get_accessible_table_column_header(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, Union[JOBJECT64, int]]:
        """Returns the table column headers of the specified table as a table.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): Parent Java object.

        Returns:
            dict[str, Union[JOBJECT64, int]]:
            Dict of information about the table column header, contains:
                caption (JOBJECT64): caption of table.

                summary (JOBJECT64): summary of table.

                row_count (int): row count number of table.

                column_count (int): column count number of table.

                accessible_context (JOBJECT64): AccessibleContext object.

                accessible_table (JOBJECT64): AccessibleTable object.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTableColumnHeader with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        info = AccessibleTableInfo()
        rslt = bool(
            self.bridge.getAccessibleTableColumnHeader(
                vmid, acc_ctx, byref(info)
            )
        )
        if not rslt:
            JABException(
                "JAB API getAccessibleTableColumnHeader result Failed")
        dict_info = {
            "caption": info.caption,
            "summary": info.summary,
            "row_count": info.rowCount,
            "column_count": info.columnCount,
            "accessible_context": info.accessibleContext,
            "accessible_table": info.accessibleTable,
        }
        self.logger.debug(
            f"JAB API getAccessibleTableColumnHeader return => {dict_info}"
        )
        return dict_info

    def get_accessible_table_row_description(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        row: int,
    ) -> AccessibleContext:
        """Returns the description of the specified row in the specified table.
        The row specifier is zero-based.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): Parent Java object.

            row (int): Index of row. Start from 0.

        Returns:
            AccessibleContext: AccessibleContext of specified row description.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTableRowDescription with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, row: {row}"
        )
        row_ac: AccessibleContext = (
            self.bridge.getAccessibleTableRowDescription(
                vmid, acc_ctx, jint(row))
        )
        self.logger.debug(
            f"JAB API getAccessibleTableRowDescription return => {row_ac}"
        )
        return row_ac

    def get_accessible_table_column_description(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        col: int,
    ) -> AccessibleContext:
        """Returns the description of the specified column in the specified table.
        The column specifier is zero-based.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): Parent Java object.

            col (int): Index of column. Start from 0.

        Returns:
            AccessibleContext: AccessibleContext of specified column description.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTableRowDescription with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, col: {col}"
        )
        col_ac: AccessibleContext = (
            self.bridge.getAccessibleTableColumnDescription(
                vmid, acc_ctx, jint(col))
        )
        self.logger.debug(
            f"JAB API getAccessibleTableColumnDescription return => {col_ac}"
        )
        return col_ac

    def get_accessible_table_row_selection_count(
        self, vmid: c_long, acc_tbl: AccessibleTable
    ) -> int:
        """Returns how many rows in the table are selected.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

        Returns:
            int: How many rows in the table are selected.
        """
        self.logger.debug(
            "Run JAB API getAccessibleTableRowSelectionCount with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}"
        )
        cnt: int = self.bridge.getAccessibleTableRowSelectionCount(
            vmid, acc_tbl
        )
        self.logger.debug(
            f"JAB API getAccessibleTableRowSelectionCount return => {cnt}"
        )
        return cnt

    def is_accessible_table_row_selected(
        self,
        vmid: c_long,
        acc_tbl: AccessibleTable,
        row: int,
    ) -> bool:
        """Returns true if the specified zero based row is selected.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

            row (int): Index of row. Start from 0.

        Returns:
            bool: True if the specified row is selected False for Not.
        """
        self.logger.debug(
            "Run JAB API isAccessibleTableRowSelected with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}, row: {row}"
        )
        rslt = bool(
            self.bridge.isAccessibleTableRowSelected(vmid, acc_tbl, jint(row))
        )
        self.logger.debug(
            f"JAB API isAccessibleTableRowSelected return => {rslt}"
        )
        return rslt

    def get_accessible_table_row_selections(
        self,
        vmid: c_long,
        acc_tbl: AccessibleTable,
    ) -> int:
        """Returns an array of zero based indices of the selected rows.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

        Returns:
            int: Zero based indices of the selected rows.
        """
        self.logger.debug(
            "Run JAB API getAccessibleTableRowSelections with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}"
        )
        cnt = self.get_accessible_table_row_selection_count(
            vmid, acc_tbl
        )
        sels = jint()
        rslt = bool(
            self.bridge.getAccessibleTableRowSelections(
                vmid, acc_tbl, cnt, byref(sels)
            )
        )
        if not rslt:
            raise JABException(
                f"JAB API getAccessibleTableRowSelections result Failed"
            )
        self.logger.debug(
            f"JAB API getAccessibleTableRowSelections return => {sels.value}"
        )
        return sels.value

    def get_accessible_table_column_selection_count(
        self, vmid: c_long, acc_tbl: AccessibleTable
    ) -> int:
        """Returns how many columns in the table are selected.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

        Returns:
            int: How many columns in the table are selected.
        """
        self.logger.debug(
            "Run JAB API getAccessibleTableColumnSelectionCount with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}"
        )
        cnt: int = self.bridge.getAccessibleTableColumnSelectionCount(
            vmid, acc_tbl
        )
        self.logger.debug(
            f"JAB API getAccessibleTableColumnSelectionCount return => {cnt}"
        )
        return cnt

    def is_accessible_table_column_selected(
        self,
        vmid: c_long,
        acc_tbl: AccessibleTable,
        col: int,
    ) -> bool:
        """Returns true if the specified zero based column is selected.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

            col (int): Index of column. Start from 0.

        Returns:
            bool: True if the specified column is selected False for Not.
        """
        self.logger.debug(
            f"Run JAB API isAccessibleTableColumnSelected with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}, col: {col}"
        )
        rslt = bool(
            self.bridge.isAccessibleTableColumnSelected(
                vmid, acc_tbl, jint(col))
        )
        self.logger.debug(
            f"JAB API isAccessibleTableColumnSelected return => {rslt}"
        )
        return rslt

    def get_accessible_table_column_selections(
        self,
        vmid: c_long,
        acc_tbl: AccessibleTable,
    ) -> int:
        """Returns an array of zero based indices of the selected columns.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

        Raise:
            JABException: getAccessibleTableColumnSelections result Failed.

        Returns:
            int: Zero based indices of the selected columns.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTableColumnSelections with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}"
        )
        cnt = self.get_accessible_table_column_selection_count(
            vmid, acc_tbl
        )
        sels = jint()
        rslt = bool(
            self.bridge.getAccessibleTableColumnSelections(
                vmid, acc_tbl, jint(cnt), byref(sels)
            )
        )
        if not rslt:
            raise JABException(
                f"JAB API getAccessibleTableColumnSelections result => {rslt}"
            )
        self.logger.debug(
            f"JAB API getAccessibleTableColumnSelections return => {sels.value}"
        )
        return sels.value

    def get_accessible_table_row(
        self,
        vmid: c_long,
        acc_tbl: AccessibleTable,
        idx: int,
    ) -> int:
        """Returns the row number of the cell at the specified cell index. 
        The values are zero based.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

            idx (int): The specified cell index.

        Returns:
            int: The row number of the cell at the specified cell index.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTableRow with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}, idx: {idx}"
        )
        num: int = self.bridge.getAccessibleTableRow(vmid, acc_tbl, jint(idx))
        self.logger.debug(f"JAB API getAccessibleTableRow return => {num}")
        return num

    def get_accessible_table_column(
        self,
        vmid: c_long,
        acc_tbl: AccessibleTable,
        idx: int,
    ) -> int:
        """Returns the column number of the cell at the specified cell index. 
        The values are zero based.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

            idx (int): The specified cell index.

        Returns:
            int: The column number of the cell at the specified cell index.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleTableColumn with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}, idx: {idx}"
        )
        num: int = self.bridge.getAccessibleTableColumn(
            vmid, acc_tbl, jint(idx))
        self.logger.debug(f"JAB API getAccessibleTableColumn return => {num}")
        return num

    def get_accessible_table_index(
        self,
        vmid: c_long,
        acc_tbl: AccessibleTable,
        row: int,
        col: int,
    ) -> int:
        """Returns the cell index in the table of the specified row and column offset. 
        The values are zero based.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_tbl (AccessibleTable): The given Java Object.

            row (int): The specified cell index of row.

            col (int): The specified cell index of column.

        Returns:
            int: The index in the table of the specified row and column offset.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleHypertext with "
            f"vmid: {vmid}, acc_tbl: {acc_tbl}, row: {row}, column: {col}"
        )
        idx: int = self.bridge.getAccessibleTableIndex(
            vmid, acc_tbl, jint(row), jint(col)
        )
        self.logger.debug(f"JAB API getAccessibleHypertext return => {idx}")
        return idx

    # Accessible Relation Set Function
    def get_accessible_relation_set(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, Union[str, int, AccessibleContext]]:
        """Returns information about an object's related objects.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            info (AccessibleRelationInfo, optional): 
            AccessibleRelationInfo object.
            Defaults to AccessibleRelationInfo() (Passing pointer).

        Raise:
            JABException: getAccessibleHypertext result Failed.

        Returns:
            dict[str, Union[str, int, AccessibleContext]]: 
            Dict information about an object's related objects.
                key (str): String text of key for Accessible Relation Set.

                target_count (int): Count for Accessible Relation Set.

                targets (list[AccessibleContext]): 
                List of target AccessibleContext.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleHypertext with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        info = AccessibleRelationInfo()
        rslt = bool(
            self.bridge.getAccessibleRelationSet(vmid, acc_ctx, byref(info))
        )
        if not rslt:
            raise JABException(f"JAB API getAccessibleHypertext result Failed")
        dict_info = {
            "key": info.key,
            "target_count": info.targetCount,
            "targets": info.targets,
        }
        self.logger.debug(
            f"JAB API getAccessibleHypertext return => {dict_info}"
        )
        return dict_info

    # Accessible Hypertext Functions
    def get_accessible_hypertext(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, Union[int, list, AccessibleContext]]:
        """Returns hypertext information associated with a component.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Raise:
            JABException: getAccessibleHypertext result Failed.

        Returns:
            dict[str, Union[int, list, AccessibleContext]]: 
            Dict of hypertext information associated with a component.
                link_count (int): Number of hyperlinks.

                links (list[AccessibleContext]): 
                List of hyperlink AccessibleContext.

                accessible_hypertext (AccessibleContext): 
                AccessibleContext for Hypertext.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleHypertext with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        info = AccessibleHypertextInfo()
        rslt = bool(
            self.bridge.getAccessibleHypertext(vmid, acc_ctx, byref(info))
        )
        if not rslt:
            raise JABException(f"JAB API getAccessibleHypertext result Failed")
        dict_info = {
            "link_count": info.linkCount,
            "links": info.links,
            "accessible_hypertext": info.accessibleHypertext,
        }
        self.logger.debug(
            f"JAB API getAccessibleHypertext return => {dict_info}"
        )
        return dict_info

    def activate_accessible_hyperlink(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        acc_hlnk: AccessibleHyperlink,
    ) -> None:
        """Requests that a hyperlink be activated.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            acc_hlnk (AccessibleHyperlink): 
            The given AccessibleHyperlink Object.

        Raise:
            JABException: activateAccessibleHyperlink result Failed
        """
        self.logger.debug(
            f"Run JAB API activateAccessibleHyperlink with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, acc_hlnk: {acc_hlnk}"
        )
        rslt = bool(
            self.bridge.activateAccessibleHyperlink(vmid, acc_ctx, acc_hlnk)
        )
        if not rslt:
            raise JABException(
                "JAB API activateAccessibleHyperlink result Failed"
            )

    def get_accessible_hyperlink_count(
        self, vmid: c_long, acc_htxt: AccessibleHypertext
    ) -> int:
        """Returns the number of hyperlinks in a component.
        Returns -1 on error.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_htxt (AccessibleHypertext): The given Java Object.

        Raise:
            JABException: getAccessibleHypertextExt result Failed

        Returns:
            int: The number of hyperlinks in a component.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleHyperlinkCount with "
            f"vmid: {vmid}, acc_htxt: {acc_htxt}"
        )
        cnt: int = self.bridge.getAccessibleHyperlinkCount(vmid, acc_htxt)
        if cnt == -1:
            raise JABException(
                "JAB API getAccessibleHypertextExt result Failed")
        self.logger.debug(f"JAB API getAccessibleHypertextExt return => {cnt}")
        return cnt

    def get_accessible_hypertext_ext(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        idx: int,
    ) -> dict[str, Union[int, list, AccessibleContext]]:
        """Iterates through the hyperlinks in a component.
        Returns hypertext information for a component starting at hyperlink index nStartIndex.
        No more than MAX_HYPERLINKS AccessibleHypertextInfo objects will be returned for each call to this method.
        Returns False on error.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            idx (int): The component starting at hyperlink index.

        Raise:
            JABException: getAccessibleHypertextExt result Failed.

        Returns:
            dict[str, Union[int, list, AccessibleContext]]: 
            Dict of hypertext information associated with a component.
                link_count (int): Number of hyperlinks.

                links (list[AccessibleContext]): 
                List of hyperlink AccessibleContext.

                accessible_hypertext (AccessibleContext): 
                AccessibleContext for Hypertext.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleHypertextExt with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, idx:{idx}"
        )
        info = AccessibleHypertextInfo()
        rslt = bool(
            self.bridge.getAccessibleHypertextExt(
                vmid, acc_ctx, jint(idx), byref(info)
            )
        )
        if not rslt:
            raise JABException(
                "JAB API getAccessibleHypertextExt result Failed")
        dict_info = {
            "link_count": info.linkCount,
            "links": info.links,
            "accessible_hypertext": info.accessibleHypertext,
        }
        self.logger.debug(
            f"JAB API getAccessibleHypertextExt return => {dict_info}"
        )
        return dict_info

    def get_accessible_hypertext_link_index(
        self,
        vmid: c_long,
        acc_htxt: AccessibleHypertext,
        idx: int,
    ) -> int:
        """Returns the index into an array of hyperlinks that is associated with a character index in document.
        Maps to AccessibleHypertext.getLinkIndex.
        Returns -1 on error.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_htxt (AccessibleHypertext): The given Java Object.

            idx (int): The character index in document.

        Raise:
            JABException: getAccessibleHypertextLinkIndex result Failed.

        Returns:
            int: The index into an array of hyperlinks.
        """
        self.logger.debug(
            "Run JAB API getAccessibleHypertextLinkIndex with "
            f"vmid: {vmid}, acc_htxt: {acc_htxt}, idx:{idx}"
        )
        link_idx: int = self.bridge.getAccessibleHypertextLinkIndex(
            vmid, acc_htxt, jint(idx)
        )
        if link_idx == -1:
            raise JABException(
                "JAB API getAccessibleHypertextLinkIndex result Failed"
            )
        self.logger.debug(
            f"JAB API getAccessibleHypertextLinkIndex return => {link_idx}"
        )
        return link_idx

    def get_accessible_hyperlink(
        self,
        vmid: c_long,
        acc_htxt: AccessibleHypertext,
        idx: int,
    ) -> dict[str, Union[str, int, JOBJECT64]]:
        """Returns the nth hyperlink in a document.
        Maps to AccessibleHypertext.getLink.
        Returns False on error.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_htxt (AccessibleHypertext): The given Java Object.

            idx (int): The index of hyperlink in a document.

        Raise:

            JABException: getAccessibleHyperlink result Failed.

        Returns:
            dict[str, Union[str, int, JOBJECT64]]: 
            Dict of AccessibleHyperlink information associated with a component.
                text (str): Text of hyperlinks.

                start_index (list[AccessibleContext]): 
                Index in the hypertext document where the link begins.

                end_index (list[AccessibleContext]): 
                Index in the hypertext document where the link ends.

                accessible_hyperlink (AccessibleContext): 
                AccessibleHyperlink for hyperlink.
        """
        self.logger.debug(
            "Run JAB API getAccessibleHyperlink with "
            f"vmid: {vmid}, acc_htxt: {acc_htxt}, idx:{idx}"
        )
        info = AccessibleHyperlinkInfo()
        rslt = bool(
            self.bridge.getAccessibleHyperlink(
                vmid, acc_htxt, jint(idx), byref(info))
        )
        if not rslt:
            JABException("JAB API getAccessibleHyperlink result Failed")
        dict_info = {
            "text": info.text,
            "start_index": info.startIndex,
            "end_index": info.endIndex,
            "accessible_hyperlink": info.accessibleHyperlink,
        }
        self.logger.debug(
            f"JAB API getAccessibleHyperlink return => {dict_info}"
        )
        return dict_info

    # Accessible Key Binding Function
    def get_accessible_key_bindings(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, Union[int, AccessibleKeyBindingInfo]]:
        """Returns a list of key bindings associated with a component.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Raise:
            JABException: getAccessibleKeyBindings result Failed

        Returns:
            dict[str, Union[int, AccessibleKeyBindingInfo]]: 
            Dict of AccessibleKeyBindings information associated with a component.
                key_bindings_count (int): Number of key bindings.

                key_binding_info (AccessibleKeyBindingInfo): 
                AccessibleKeyBindingInfo of AccessibleContext.
        """
        self.logger.debug(
            "Run JAB API getAccessibleKeyBindings with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        binds = AccessibleKeyBindings()
        rslt = bool(
            self.bridge.getAccessibleKeyBindings(vmid, acc_ctx, byref(binds))
        )
        if not rslt:
            JABException(f"JAB API getAccessibleKeyBindings result Failed")
        dict_binds = {
            "key_bindings_count": binds.keyBindingsCount,
            "key_binding_info": binds.keyBindingInfo,
        }
        self.logger.debug(
            f"JAB API getAccessibleKeyBindings return => {dict_binds}"
        )
        return dict_binds

    # Accessible Icon Function
    def get_accessible_icons(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, Union[int, AccessibleIconInfo]]:
        """Returns a list of icons associate with a component.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Raise:
            JABException: getAccessibleIcons result Failed

        Returns:
            dict[str,Union[int, AccessibleIconInfo]]: 
                Dict of AccessibleIcons information associated with a component.
                    icons_count (int): Number of icons.

                    icon_info (AccessibleIconInfo): 
                    AccessibleIconInfo of AccessibleContext.
        """
        self.logger.debug(
            "Run JAB API getAccessibleIcons with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        acc_icons = AccessibleIcons()
        rslt = bool(self.bridge.getAccessibleIcons(
            vmid, acc_ctx, byref(acc_icons)))
        if not rslt:
            JABException(f"JAB API getAccessibleIcons result Failed")
        dict_icons = {"icons_count": acc_icons.iconsCount,
                      "icon_info": acc_icons.iconInfo}
        self.logger.debug(f"JAB API getAccessibleIcons return => {dict_icons}")
        return dict_icons

    # Accessible Action Functions
    def get_accessible_actions(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
    ) -> dict[str, Union[int, AccessibleActionInfo]]:
        """Returns a sequence of actions that a component can perform.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Returns:
            dict[str, Union[int, AccessibleActionInfo]]: 
                Dict of AccessibleActions information associated with a component.
                    actions_count (int): Number of actions.

                    action_info (AccessibleActionInfo): 
                    AccessibleActionInfo of AccessibleContext.
        """
        self.logger.debug(
            f"Run JAB API getAccessibleActions with vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        acc_acts = AccessibleActions()
        rslt = bool(
            self.bridge.getAccessibleActions(vmid, acc_ctx, byref(acc_acts))
        )
        if not rslt:
            JABException("JAB API isSameObject result Failed")
        dict_acts = {
            "actions_count": acc_acts.iconsCount,
            "action_info": acc_acts.iconInfo,
        }
        self.logger.debug(f"JAB API isSameObject return => {dict_acts}")
        return dict_acts

    def do_accessible_actions(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        acts_todo: Sequence[str],
    ) -> bool:
        """Request that a list of AccessibleActions be performed by a component.
        Returns TRUE if all actions are performed.
        Returns FALSE when the first requested action fails in which case "failure" contains the index of the action that failed.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            acts_todo (Sequence[str], optional): 
            AccessibleActionsToDo of actions to be performed.

        Returns:
            bool: True if all actions are performed False for Not.
        """
        acts_len = len(acts_todo)
        acc_act_info = AccessibleActionInfo * MAX_ACTIONS_TO_DO
        acts = [acc_act_info(acts_todo[i]) for i in range(acts_len)]
        acc_acts_todo = AccessibleActionsToDo(actionsCount=acts_len, actions=acts)
        self.logger.debug(
            "Run JAB API doAccessibleActions with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, acts_todo: {acts_todo}"
        )
        rslt = bool(
            self.bridge.doAccessibleActions(
                vmid, acc_ctx, acc_acts_todo, byref(jint())
            )
        )
        self.logger.debug(f"JAB API doAccessibleActions return => {rslt}")
        return rslt

    # Utility Functions
    def is_same_object(
        self, vmid: c_long, obj1: JOBJECT64, obj2: JOBJECT64
    ) -> bool:
        """Returns whether two object references refer to the same object.

        Args:
            vmid (c_long): VMID for the given Java Object.
            obj1 (JOBJECT64): Java object 1.
            obj2 (JOBJECT64): Java object 2.

        Returns:
            bool: True for two object references refer to the same object False for Not.
        """
        self.logger.debug(
            f"Run JAB API isSameObject with vmid: {vmid}, obj1: {obj1}, obj2: {obj2}"
        )
        rslt = bool(self.bridge.isSameObject(vmid, obj1, obj2))
        self.logger.debug(f"JAB API isSameObject return => {rslt}")
        return rslt

    def get_parent_with_role(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        role: str,
    ) -> AccessibleContext:
        """Returns the AccessibleContext with the specified role that is the ancestor of a given object.
        The role is one of the role strings defined in Java Access Bridge API Data Structures.
        If there is no ancestor object that has the specified role, returns (AccessibleContext)0.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            role (str): String text of role that is the ancestor of a given object.

        Raises:
            JABException: getParentWithRole result Failed.

        Returns:
            AccessibleContext: The Parent AccessibleContext with the specified role.
        """
        parent_role = create_unicode_buffer(role)
        self.logger.debug(
            "Run JAB API getParentWithRole with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, role: {role}"
        )
        par_ac: AccessibleContext = self.bridge.getParentWithRole(
            vmid, acc_ctx, parent_role
        )
        if par_ac == 0:
            raise JABException("JAB API getParentWithRole result Failed")
        self.logger.debug(f"JAB API getParentWithRole return => {par_ac}")
        return par_ac

    def get_parent_with_role_else_root(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        role: str,
    ) -> AccessibleContext:
        """Returns the AccessibleContext with the specified role that is the ancestor of a given object.
        The role is one of the role strings defined in Java Access Bridge API Data Structures.
        If an object with the specified role does not exist, returns the top level object for the Java window.
        Returns (AccessibleContext)0 on error.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            role (str): String text of role that is the ancestor of a given object.

        Raises:
            JABException: getParentWithRoleElseRoot result Failed.

        Returns:
            AccessibleContext: The Parent AccessibleContext with the specified role.
        """
        parent_role = create_unicode_buffer(role)
        self.logger.debug(
            "Run JAB API getParentWithRoleElseRoot with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, role: {role}"
        )
        par_ac: AccessibleContext = self.bridge.getParentWithRoleElseRoot(
            vmid, acc_ctx, parent_role
        )
        if par_ac == 0:
            raise JABException(
                "JAB API getParentWithRoleElseRoot result Failed")
        self.logger.debug(
            f"JAB API getParentWithRoleElseRoot return => {par_ac}"
        )
        return par_ac

    def get_top_level_object(
        self, vmid: c_long, acc_ctx: AccessibleContext
    ) -> AccessibleContext:
        """Returns the AccessibleContext for the top level object in a Java window.
        This is same AccessibleContext that is obtained from GetAccessibleContextFromHWND for that window.
        Returns (AccessibleContext)0 on error.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Raises:
            JABException: getTopLevelObject result Failed.

        Returns:
            AccessibleContext: The top level AccessibleContext.
        """
        self.logger.debug(
            f"Run JAB API getTopLevelObject with vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        top_ac: AccessibleContext = self.bridge.getTopLevelObject(
            vmid, acc_ctx)
        if top_ac == 0:
            raise JABException("JAB API getTopLevelObject result Failed")
        self.logger.debug(f"JAB API getTopLevelObject return => {top_ac}")
        return top_ac

    def get_object_depth(
        self, vmid: c_long, acc_ctx: AccessibleContext
    ) -> int:
        """Returns how deep in the object hierarchy a given object is.
        The top most object in the object hierarchy has an object depth of 0.
        Returns -1 on error.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.
        
        Raises:
            JABException: getObjectDepth result Failed.

        Returns:
            int: Integer of object depth.
        """
        self.logger.debug(
            f"Run JAB API getObjectDepth with vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        obj_dpth: int = self.bridge.getObjectDepth(vmid, acc_ctx)
        if obj_dpth == -1:
            raise JABException("JAB API getObjectDepth result Failed")
        self.logger.debug(f"JAB API getObjectDepth return => {obj_dpth}")
        return obj_dpth

    def get_active_descendent(
        self, vmid: c_long, acc_ctx: AccessibleContext
    ) -> AccessibleContext:
        """Returns the AccessibleContext of the current ActiveDescendent of an object.
        This method assumes the ActiveDescendent is the component that is currently selected in a container object.
        Returns (AccessibleContext)0 on error or if there is no selection.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.
        
        Raises:
            JABException: getActiveDescendent result Failed.

        Returns:
            AccessibleContext: The AccessibleContext of the current ActiveDescendent.
        """
        self.logger.debug(
            f"Run JAB API getActiveDescendent with vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        desc_ac: AccessibleContext = self.bridge.getActiveDescendent(
            vmid, acc_ctx
        )
        if desc_ac.value == 0:
            raise JABException("JAB API getActiveDescendent result Failed")
        self.logger.debug(
            f"JAB API getActiveDescendent return => {desc_ac}")
        return desc_ac

    def request_focus(
        self, vmid: c_long, acc_ctx: AccessibleContext
    ) -> bool:
        """Request focus for a component. Returns whether successful.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

        Returns:
            bool: True for request focus success Fale for Not.
        """
        self.logger.debug(
            f"Run JAB API requestFocus with vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        rslt = bool(self.bridge.requestFocus(vmid, acc_ctx))
        self.logger.debug(f"JAB API requestFocus return => {rslt}")
        return rslt

    def get_visible_children_count(
        self, vmid: c_long, acc_ctx: AccessibleContext
    ) -> int:
        """Returns the number of visible children of a component. 
        Returns -1 on error.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.
        
        Raises:
            JABException: getVisibleChildrenCount result Failed.

        Returns:
            int: Number of visible children count.
        """
        self.logger.debug(
            f"Run JAB API getVisibleChildrenCount with vmid: {vmid}, acc_ctx: {acc_ctx}"
        )
        chn_cnt: int = self.bridge.getVisibleChildrenCount(vmid, acc_ctx)
        if chn_cnt == -1:
            raise JABException("JAB API getVisibleChildrenCount result Failed")
        self.logger.debug(
            f"JAB API getVisibleChildrenCount return => {chn_cnt}"
        )
        return chn_cnt

    def get_visible_children(
        self,
        vmid: c_long,
        acc_ctx: AccessibleContext,
        idx: int,
    ) -> dict[str, Union[int, Sequence[str]]]:
        """Gets the visible children of an AccessibleContext. 
        Returns whether successful.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_ctx (AccessibleContext): The given AccessibleContext Object.

            idx (int): Start index of visible children.
        
        Raises:
            JABException: getVisibleChildren result Failed.

        Returns:
            dict[dict[str, Union[int, Sequence[str]]]]: Dict of VisibleChildrenInfo.
        """
        self.logger.debug(
            f"Run JAB API getVisibleChildren with "
            f"vmid: {vmid}, acc_ctx: {acc_ctx}, idx: {idx}"
        )
        info = VisibleChildrenInfo()
        rslt = bool(
            self.bridge.getVisibleChildren(
                vmid, acc_ctx, c_int(idx), byref(info))
        )
        if not rslt:
            raise JABException(f"JAB API getVisibleChildren Failed")
        dict_data = {
            "returned_children_count": info.returnedChildrenCount,
            "children": info.children
        }
        self.logger.debug(f"JAB API getVisibleChildren return => {dict_data}")
        return dict_data

    def get_events_waiting(self) -> int:
        """Gets the number of events waiting to fire.

        Returns:
            int: Number of events waiting.
        """
        self.logger.debug("Run JAB API getEventsWaiting")
        evts: int = self.bridge.getEventsWaiting()
        self.logger.debug(f"JAB API getEventsWaiting return => {evts}")
        return evts

    # Accessible Value Functions
    def get_current_accessible_value_from_context(
        self,
        vmid: c_long,
        acc_val: AccessibleValue,
    ) -> int:
        """Get the value of this object as a Number.
        If the value has not been set, the return value will be null.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_val (AccessibleValue): The given Java Object.
        
        Raises:
            JABException: getCurrentAccessibleValueFromContext result Failed.

        Returns:
            int: value of the object
        """
        self.logger.debug(
            "Run JAB API getCurrentAccessibleValueFromContext with "
            f"vmid: {vmid}, acc_val: {acc_val}"
        )
        val = create_unicode_buffer(SHORT_STRING_SIZE)
        rslt = bool(
            self.bridge.getCurrentAccessibleValueFromContext(
                vmid, acc_val, val, c_short(SHORT_STRING_SIZE)
            )
        )
        if not rslt:
            raise JABException(
                "JAB API getCurrentAccessibleValueFromContext Failed")
        self.logger.debug(
            f"JAB API getCurrentAccessibleValueFromContext return => {val.value}"
        )
        return val.value

    def get_maximum_accessible_value_from_context(
        self,
        vmid: c_long,
        acc_val: AccessibleValue,
    ) -> int:
        """Get the maximum value of this object as a Number.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_val (AccessibleValue): The given Java Object.
        
        Raises:
            JABException: getMaximumAccessibleValueFromContext result Failed.

        Returns:
            int: Maximum value of the object; null if this object does not have a maximum value.
        """
        self.logger.debug(
            f"Run JAB API getMaximumAccessibleValueFromContext with "
            f"vmid: {vmid}, acc_val: {acc_val}"
        )
        val = create_unicode_buffer(SHORT_STRING_SIZE)
        rslt = bool(
            self.bridge.getMaximumAccessibleValueFromContext(
                vmid, acc_val, val, c_short(SHORT_STRING_SIZE)
            )
        )
        if not rslt:
            raise JABException(
                "JAB API getMaximumAccessibleValueFromContext Failed")
        self.logger.debug(
            f"JAB API getMaximumAccessibleValueFromContext return => {val.value}"
        )
        return val.value

    def get_minimum_accessible_value_from_context(
        self,
        vmid: c_long,
        acc_val: AccessibleValue,
    ) -> int:
        """Get the minimum value of this object as a Number.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_val (AccessibleValue): The given Java Object.
        
        Raises:
            JABException: getMinimumAccessibleValueFromContext result Failed.

        Returns:
            int: Minimum value of the object; null if this object does not have a minimum value.
        """
        self.logger.debug(
            f"Run JAB API getMinimumAccessibleValueFromContext with "
            f"vmid: {vmid}, acc_val: {acc_val}"
        )
        val = create_unicode_buffer(SHORT_STRING_SIZE)
        rslt = bool(
            self.bridge.getMinimumAccessibleValueFromContext(
                vmid, acc_val, val, c_short(SHORT_STRING_SIZE)
            )
        )
        if not rslt:
            raise JABException(
                f"JAB API getMinimumAccessibleValueFromContext Failed"
            )
        self.logger.debug(
            f"JAB API getMinimumAccessibleValueFromContext return => {val.value}"
        )
        return val.value

    # Accessible Selection Functions
    def add_accessible_selection_from_context(
        self,
        vmid: c_long,
        acc_slctn: AccessibleSelection,
        idx: int,
    ) -> None:
        """Adds the specified Accessible child of the object to the object's selection.
        If the object supports multiple selections, the specified child is added to any existing selection,
        otherwise it replaces any existing selection in the object.
        If the specified child is already selected, this method has no effect.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_slctn (AccessibleSelection): The given Java Object.

            idx (int): The zero-based index of the child.
        """
        self.logger.debug(
            f"Run JAB API addAccessibleSelectionFromContext with "
            f"vmid: {vmid}, acc_slctn: {acc_slctn}, idx: {idx}"
        )
        self.bridge.addAccessibleSelectionFromContext(
            vmid, acc_slctn, c_int(idx))

    def clear_accessible_selection_from_context(
        self,
        vmid: c_long,
        acc_slctn: AccessibleSelection,
    ) -> None:
        """Clears the selection in the object, so that no children in the object are selected.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_slctn (AccessibleSelection): The given Java Object.
        """
        self.logger.debug(
            "Run JAB API clearAccessibleSelectionFromContext with "
            f"vmid: {vmid}, acc_slctn: {acc_slctn}"
        )
        self.bridge.clearAccessibleSelectionFromContext(vmid, acc_slctn)

    def get_accessible_selection_from_context(
        self,
        vmid: c_long,
        acc_slctn: AccessibleSelection,
        idx: int,
    ) -> JOBJECT64:
        """Returns an Accessible representing the specified selected child of the object.
        If there isn't a selection, or there are fewer children selected than the integer passed in,
        the return value will be null.
        Note that the index represents the i-th selected child, which is different from the i-th child.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_slctn (AccessibleSelection): The given Java Object.

            idx (int): The zero-based index of selected children.

        Returns:
            JOBJECT64: The i-th selected child
        """
        self.logger.debug(
            f"Run JAB API getAccessibleSelectionFromContext with "
            f"vmid: {vmid}, acc_slctn: {acc_slctn}, idx: {idx}"
        )
        jobj: JOBJECT64 = self.bridge.getAccessibleSelectionFromContext(
            vmid, acc_slctn, c_int(idx)
        )
        self.logger.debug(
            f"JAB API getAccessibleSelectionFromContext return => {jobj}"
        )
        return jobj

    def get_accessible_selection_count_from_context(
        self, vmid: c_long, acc_slctn: AccessibleSelection
    ) -> int:
        """Returns the number of Accessible children currently selected.
        If no children are selected, the return value will be 0.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_slctn (AccessibleSelection): The given Java Object.

        Returns:
            int: The number of items currently selected.
        """
        self.logger.debug(
            "Run JAB API getAccessibleSelectionCountFromContext with "
            f"vmid: {vmid}, acc_slctn: {acc_slctn}"
        )
        slctn_cnt: int = self.bridge.getAccessibleSelectionCountFromContext(
            vmid, acc_slctn
        )
        self.logger.debug(
            f"JAB API removeAccessibleSelectionFromContext return => {slctn_cnt}"
        )
        return slctn_cnt

    def is_accessible_child_selected_from_context(
        self,
        vmid: c_long,
        acc_slctn: AccessibleSelection,
        idx: Union[c_int, int],
    ) -> bool:
        """Determines if the current child of this object is selected.

        Args:
            vmid (Union[c_long,int]): VMID for the given Java Object.

            acc_slctn (AccessibleSelection): The given Java Object.

            idx (Union[c_int, int]): The zero-based index of the child in this Accessible object.

        Returns:
            bool: True if the current child of this object is selected else False.
        """
        self.logger.debug(
            f"Run JAB API isAccessibleChildSelectedFromContext with "
            f"vmid: {vmid}, acc_slctn: {acc_slctn}, idx: {idx}"
        )
        rslt = bool(
            self.bridge.isAccessibleChildSelectedFromContext(
                vmid, acc_slctn, idx
            )
        )
        self.logger.debug(
            f"JAB API removeAccessibleSelectionFromContext return => {rslt}"
        )
        return rslt

    def remove_accessible_selection_from_context(
        self,
        vmid: c_long,
        acc_slctn: AccessibleSelection,
        idx: Union[c_int, int],
    ) -> None:
        """Removes the specified child of the object from the object's selection.
        If the specified item isn't currently selected, this method has no effect.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_slctn (AccessibleSelection): The given Java Object.

            idx (Union[c_int, int]): The zero-based index of the child.
        """
        self.logger.debug(
            f"Run JAB API removeAccessibleSelectionFromContext with "
            f"vmid: {vmid}, acc_slctn: {acc_slctn}, idx: {idx}"
        )
        self.bridge.removeAccessibleSelectionFromContext(vmid, acc_slctn, idx)

    def select_all_accessible_selection_from_context(
        self, vmid: c_long, acc_slctn: AccessibleSelection
    ) -> None:
        """Causes every child of the object to be selected if the object supports multiple selections.

        Args:
            vmid (c_long): VMID for the given Java Object.

            acc_slctn (AccessibleSelection): The given Java Object.
        """
        self.logger.debug(
            "Run JAB API selectAllAccessibleSelectionFromContext "
            f"with vmid: {vmid}, acc_slctn: {acc_slctn}"
        )
        self.bridge.selectAllAccessibleSelectionFromContext(vmid, acc_slctn)
