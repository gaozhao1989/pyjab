from ctypes import CFUNCTYPE, c_char_p, c_int, c_long, c_wchar_p

from pyjab.common.types import JOBJECT64

# API Callbacks
"""
The Java Access Bridge API callbacks are contained in the file AccessBridgeCallbacks.h. 
Your event handling functions must match these prototypes.

Note: All of the Java Access Bridge event handlers are defined and used in the Java Ferret example.

You must call the function ReleaseJavaObject on every JOBJECT64 
returned through these event handlers once you are finished with them to prevent memory leaks in the JVM.

Here, JOBJECT64 is defined as jlong on 64-bit systems and jobject on legacy versions of Java Access Bridge. 
For definitions, see the section ACCESSBRIDGE_ARCH_LEGACY in the AccessBridgePackages.h header file.

If using legacy APIs, define ACCESSBRIDGE_ARCH_LEGACY. See the AccessBridgePackages.h header file.
"""

# typedef void (*AccessBridge_FocusGainedFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
focus_gained_fp = CFUNCTYPE(None, c_long, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_FocusLostFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
focus_lost_fp = CFUNCTYPE(None, c_long, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_CaretUpdateFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
caret_update_fp = CFUNCTYPE(None, c_long, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_MouseClickedFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
mouse_clicked_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_MouseEnteredFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
mouse_entered_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_MouseExitedFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
mouse_exited_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_MousePressedFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
mouse_pressed_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_MouseReleasedFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
mouse_released_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_MenuCanceledFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
menu_canceled_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_MenuDeselectedFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
menu_deselected_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_MenuSelectedFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
menu_selected_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_PopupMenuCanceledFP) (long vmID JOBJECT64 event, JOBJECT64 source);
popup_menu_canceled_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_PopupMenuWillBecomeInvisibleFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
popup_menu_will_become_invisible_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_PopupMenuWillBecomeVisibleFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
popup_menu_will_become_visible_fp = CFUNCTYPE(None, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_PropertyNameChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source, wchar_t *oldName, wchar_t *newName);
property_name_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, c_char_p, c_wchar_p
)

# typedef void (*AccessBridge_PropertyDescriptionChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source, wchar_t *oldDescription, wchar_t *newDescription);
property_description_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, c_wchar_p, c_wchar_p
)

# typedef void (*AccessBridge_PropertyStateChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source, wchar_t *oldState, wchar_t *newState);
property_state_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, c_wchar_p, c_wchar_p
)

# typedef void (*AccessBridge_PropertyValueChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source, wchar_t *oldValue, wchar_t *newValue);
property_value_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, c_wchar_p, c_wchar_p
)

# typedef void (*AccessBridge_PropertySelectionChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
property_selection_change_fp = CFUNCTYPE(None, c_long, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_PropertyTextChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
property_text_change_fp = CFUNCTYPE(None, c_long, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_PropertyCaretChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source, int oldPosition, int newPosition);
property_caret_change_fp = CFUNCTYPE(None, c_long, JOBJECT64, JOBJECT64, c_int, c_int)

# typedef void (*AccessBridge_PropertyVisibleDataChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source);
property_visible_data_change_fp = CFUNCTYPE(None, c_long, JOBJECT64, JOBJECT64)

# typedef void (*AccessBridge_PropertyChildChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source, JOBJECT64 oldChild, JOBJECT64 newChild);
property_child_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, JOBJECT64, JOBJECT64
)

# typedef void (*AccessBridge_PropertyActiveDescendentChangeFP) (long vmID, JOBJECT64 event, JOBJECT64 source, JOBJECT64 oldActiveDescendent, JOBJECT64 newActiveDescendent);
property_active_descendent_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, JOBJECT64, JOBJECT64
)
