from enum import Enum
from tkinter import HORIZONTAL, VERTICAL

"""
The States implementation.
"""


class States(str, Enum):
    """
    Set of supported states strategies.
    """

    ACTIVE = "active"
    BUSY = "busy"
    CHECKED = "checked"
    COLLAPSED = "collapsed"
    EDITABLE = "editable"
    ENABLED = "enabled"
    EXPANDED = "expanded"
    FOCUSABLE = "focusable"
    FOCUSED = "focused"
    HORIZONTAL = "horizontal"
    ICONIFIED = "iconified"
    MODAL = "modal"
    MULTI_LINE = "multi line"
    OPAQUE = "opaque"
    RESIZEABLE = "resizeable"
    SELECTABLE = "selectable"
    SELECTED = "selected"
    SHOWING = "showing"
    SIGNLE_LINE = "single line"
    PRESSED = "pressed"
    UNKNOWN = "unknown"
    VERTICAL = "vertical"
    VISIBLE = "visible"
