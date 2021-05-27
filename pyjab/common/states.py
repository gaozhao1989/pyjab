from enum import Enum

"""
The States implementation.
"""


class States(str, Enum):
    """
    Set of supported states strategies.
    """

    BUSY = "busy"
    CHECKED = "checked"
    ENABLED = "enabled"
    FOCUSED = "focused"
    SELECTED = "selected"
    PRESSED = "pressed"
    EXPANDED = "expanded"
    COLLAPSED = "collapsed"
    ICONIFIED = "iconified"
    MODAL = "modal"
    MULTI_LINE = "multi_line"
    FOCUSABLE = "focusable"
    EDITABLE = "editable"
    VISIBLE = "visible"
    SHOWING = "showing"
    UNKNOWN = "unknown"
