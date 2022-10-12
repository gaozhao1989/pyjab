from enum import Enum


class States(str, Enum):
    """
    The constants in this class present a strongly typed enumeration of common object States.
    """

    # Indicates a window is currently the active window.
    ACTIVE = "active"

    # Indicates that the object is armed.
    ARMED = "armed"

    # Indicates the current object is busy.
    BUSY = "busy"

    # Indicates this object is currently checked.
    CHECKED = "checked"

    # Indicates this object is collapsed.
    COLLAPSED = "collapsed"

    # Indicates the user can change the contents of this object.
    EDITABLE = "editable"

    # Indicates this object is enabled.
    ENABLED = "enabled"

    # Indicates this object allows progressive disclosure of its children.
    EXPANDABLE = "expandable"

    # Indicates this object is expanded.
    EXPANDED = "expanded"

    # Indicates this object can accept keyboard focus, which means all events resulting from typing on the keyboard will normally be passed to it when it has focus.
    FOCUSABLE = "focusable"

    # Indicates this object currently has the keyboard focus.
    FOCUSED = "focused"

    # Indicates the orientation of this object is horizontal.
    HORIZONTAL = "horizontal"

    # Indicates this object is minimized and is represented only by an icon.
    ICONIFIED = "iconified"

    # Indicates that the object state is indeterminate.
    INDETERMINATE = "indeterminate"

    # Indicates this object is responsible for managing its subcomponents.
    MANAGES_DESCENDANTS = "manages descendants"

    # Indicates something must be done with this object before the user can interact with an object in a different window.
    MODAL = "modal"

    # Indicates this (text) object can contain multiple lines of text.
    MULTI_LINE = "multi line"

    # Indicates this object allows more than one of its children to be selected at the same time.
    MULTISELECTABLE = "multiselectable"

    # Indicates this object paints every pixel within its rectangular region.
    OPAQUE = "opaque"

    # Indicates this object is currently pressed.
    PRESSED = "pressed"

    # Indicates the size of this object is not fixed.
    RESIZEABLE = "resizeable"

    # Indicates this object is the child of an object that allows its children to be selected, and that this child is one of those children that can be selected.
    SELECTABLE = "selectable"

    # Indicates this object is the child of an object that allows its children to be selected, and that this child is one of those children that has been selected.
    SELECTED = "selected"

    # Indicates this object, the object's parent, the object's parent's parent, and so on, are all visible.
    SHOWING = "showing"

    # Indicates this (text) object can contain only a single line of text
    SIGNLE_LINE = "single line"

    # Indicates this object is transient.
    TRANSIENT = "transient"

    # A state indicating that text is truncated by a bounding rectangle and that some of the text is not displayed on the screen.
    TRUNCATED = "truncated"

    # Indicates the orientation of this object is vertical.
    VERTICAL = "vertical"

    # Indicates this object is visible.
    VISIBLE = "visible"
