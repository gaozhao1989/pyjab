"""A synthetic accessibility tree with a bridge that counts JAB calls.

pyjab's lookup cost is dominated by cross-process Java Access Bridge calls: every
property read on every node is its own ``getAccessibleContextInfo`` round-trip.
That is what makes a lookup take tens of seconds on a window with a large table
(issues #33, #29), and it is measurable *without* Windows by counting the calls a
traversal makes against a tree of a known shape.

``find_element_by_xpath`` never needed a live JVM to be slow; it needed a tree
with the right number of nodes.

Usage::

    root = panel("root pane", [
        layered("layered pane", [
            panel("panel", [button("Submit")], index_attr=0),
        ]),
    ])
    element, bridge = bind(root)

    element.find_element_by_xpath("//push button")

    print(bridge.calls["getAccessibleContextInfo"])   # round-trips, i.e. the cost

Every JAB entry point a traversal can reach is counted, and anything the fake
does not implement raises rather than returning a MagicMock, so a traversal that
starts calling something new fails loudly instead of quietly measuring nothing.
"""

import collections

from pyjab.accessibleinfo import AccessibleContextInfo
from pyjab.common.types import JOBJECT64

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

JABElement = _win32stubs.import_jabelement()


# ---------------------------------------------------------------------------
# Building a tree
# ---------------------------------------------------------------------------

class Node:
    """One accessible object."""

    def __init__(self, role, name="", children=(), row_count=0, column_count=0):
        self.role = role
        self.name = name
        self.children = []
        self.parent = None
        self.row_count = row_count
        self.column_count = column_count
        self.handle = None
        #: Cell indices in this object's accessible selection, for a table.  The
        #: real thing is a set of selected children kept by the JVM; a table is
        #: reached through it because JAB offers no select-a-row call.
        self.selection = set()
        for child in children:
            child.parent = self
            self.children.append(child)

    @property
    def depth(self) -> int:
        depth, node = 0, self.parent
        while node is not None:
            depth, node = depth + 1, node.parent
        return depth

    def index_in_parent(self) -> int:
        return self.parent.children.index(self) if self.parent else 0

    def __repr__(self):
        return f"<{self.role} {self.name!r} children={len(self.children)}>"


def node(role, *children, name="", row_count=0, column_count=0) -> Node:
    return Node(role, name=name, children=children,
                row_count=row_count, column_count=column_count)


def panel(*children, name="", index=None):
    """A panel whose ``indexInParent`` is what the caller wants it to be.

    Panels are how real Swing hierarchies express position, and xpath locators
    against them use ``@indexinparent``, so the fake has to model it.
    """
    made = node("panel", *children, name=name)
    made.forced_index = index
    return made


def table(rows, columns, name="", cell_role="label"):
    """A table of ``rows`` x ``columns`` cells, as Swing exposes it."""
    cells = [node(cell_role, name=f"r{r}c{c}")
             for r in range(rows) for c in range(columns)]
    return node("table", *cells, name=name,
                row_count=rows, column_count=columns)


def iter_nodes(root):
    yield root
    for child in root.children:
        yield from iter_nodes(child)


# ---------------------------------------------------------------------------
# The bridge
# ---------------------------------------------------------------------------

class CountingBridge:
    """Answers the JAB calls a traversal makes, and counts them."""

    def __init__(self, root: Node):
        self.root = root
        self.by_handle = {}
        for handle, item in enumerate(iter_nodes(root), start=1):
            item.handle = handle
            self.by_handle[handle] = item
        self.calls = collections.Counter()
        #: Outstanding references per handle. Java Access Bridge returns an
        #: object reference from every call that hands one out, and each of
        #: those must be released once -- obtaining the same Java object twice
        #: means releasing it twice. Modelling that is what lets a traversal
        #: re-enumerate a subtree legally, and what makes using a handle after
        #: its last release an error rather than a silent success.
        self.refs = collections.Counter({handle: 1 for handle in self.by_handle})

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _value(handle) -> int:
        return handle.value if hasattr(handle, "value") else int(handle or 0)

    def _take(self, handle) -> int:
        """Record one more outstanding reference, and return the raw value."""
        value = self._value(handle)
        self.refs[value] += 1
        return value

    def _node(self, handle) -> Node:
        value = self._value(handle)
        if self.refs[value] <= 0:
            raise AssertionError(
                f"handle {value} was released and then used again "
                "(use-after-free)"
            )
        return self.by_handle[value]

    def count(self, name: str) -> int:
        return self.calls[name]

    @property
    def total(self) -> int:
        return sum(self.calls.values())

    def reset(self):
        self.calls.clear()

    # -- the JAB entry points used by find_element_by_* -------------------

    def getAccessibleContextInfo(self, vmid, accessible_context, info_by_ref):
        self.calls["getAccessibleContextInfo"] += 1
        item = self._node(accessible_context)
        info = info_by_ref._obj
        info.name = item.name
        info.description = ""
        info.role = item.role
        info.role_en_US = item.role
        info.states = "enabled,showing" if item.children or item.name else "enabled"
        info.states_en_US = info.states
        index = getattr(item, "forced_index", None)
        info.indexInParent = item.index_in_parent() if index is None else index
        info.childrenCount = len(item.children)
        info.x, info.y, info.width, info.height = 0, 0, 10, 10
        info.accessibleComponent = 1
        info.accessibleAction = 1
        info.accessibleSelection = 1 if item.role == "table" else 0
        info.accessibleText = 1 if item.name else 0
        info.accessibleValue = 0
        return 1

    def getAccessibleChildFromContext(self, vmid, accessible_context, index):
        self.calls["getAccessibleChildFromContext"] += 1
        children = self._node(accessible_context).children
        if index >= len(children) or index < 0:
            return JOBJECT64(0)
        return JOBJECT64(self._take(children[index].handle))

    def getTopLevelObject(self, vmid, accessible_context):
        self.calls["getTopLevelObject"] += 1
        return JOBJECT64(self._take(self.root.handle))

    def isSameObject(self, vmid, first, second):
        self.calls["isSameObject"] += 1
        return int(self._value(first) == self._value(second))

    def getObjectDepth(self, vmid, accessible_context):
        self.calls["getObjectDepth"] += 1
        return self._node(accessible_context).depth

    def getAccessibleParentFromContext(self, vmid, accessible_context):
        self.calls["getAccessibleParentFromContext"] += 1
        parent = self._node(accessible_context).parent
        return JOBJECT64(self._take(parent.handle)) if parent else JOBJECT64(0)

    def releaseJavaObject(self, vmid, accessible_context):
        self.calls["releaseJavaObject"] += 1
        value = self._value(accessible_context)
        if self.refs[value] <= 0:
            raise AssertionError(
                f"handle {value} released more times than it was obtained"
            )
        self.refs[value] -= 1
        return 1

    def getAccessibleTableInfo(self, vmid, accessible_context, info_by_ref):
        self.calls["getAccessibleTableInfo"] += 1
        item = self._node(accessible_context)
        info = info_by_ref._obj
        info.rowCount = item.row_count
        info.columnCount = item.column_count
        return 1

    def getVisibleChildren(self, vmid, accessible_context, index, info_by_ref):
        """The children a table reports as on screen.

        The fake has no scrolling, so it reports every child -- but through
        ``returnedChildrenCount`` rather than a length taken from the element, which
        is the part pyjab has to get right (#59).
        """
        self.calls["getVisibleChildren"] += 1
        item = self._node(accessible_context)
        info = info_by_ref._obj
        info.returnedChildrenCount = len(item.children)
        for position, child in enumerate(item.children):
            info.children[position] = JOBJECT64(self._take(child.handle))
        return 1

    def getAccessibleTableRowHeader(self, vmid, accessible_context, info_by_ref):
        self.calls["getAccessibleTableRowHeader"] += 1
        return 1

    def getAccessibleTableColumnHeader(self, vmid, accessible_context, info_by_ref):
        self.calls["getAccessibleTableColumnHeader"] += 1
        return 1

    # -- the accessible selection, which is how a table is driven ---------
    #
    # A model of the API's shape, not a description of any one Swing table.  What
    # it encodes: selection is a set of cell indices; a row or column counts as
    # selected when one of its cells is; and the objects that come back out are
    # the cells the table holds.  Whether a real table reports a whole row as
    # selected after its cells are added is that table's business -- which is why
    # pyjab's documentation says to read the result back rather than assume it.

    def getAccessibleTableIndex(self, vmid, accessible_context, row, column):
        self.calls["getAccessibleTableIndex"] += 1
        item = self._node(accessible_context)
        if not (0 <= row < item.row_count and 0 <= column < item.column_count):
            return -1
        return row * item.column_count + column

    def addAccessibleSelectionFromContext(self, vmid, accessible_context, index):
        self.calls["addAccessibleSelectionFromContext"] += 1
        item = self._node(accessible_context)
        if not 0 <= index < len(item.children):
            raise AssertionError(
                f"index {index} is not a child of {item!r}: something tried to "
                "select a cell that is not in the table"
            )
        item.selection.add(index)
        return 1

    def clearAccessibleSelectionFromContext(self, vmid, accessible_context):
        self.calls["clearAccessibleSelectionFromContext"] += 1
        self._node(accessible_context).selection.clear()
        return 1

    def selectAllAccessibleSelectionFromContext(self, vmid, accessible_context):
        self.calls["selectAllAccessibleSelectionFromContext"] += 1
        item = self._node(accessible_context)
        item.selection = set(range(len(item.children)))
        return 1

    def getAccessibleSelectionCountFromContext(self, vmid, accessible_context):
        self.calls["getAccessibleSelectionCountFromContext"] += 1
        return len(self._node(accessible_context).selection)

    def getAccessibleSelectionFromContext(self, vmid, accessible_context, index):
        self.calls["getAccessibleSelectionFromContext"] += 1
        item = self._node(accessible_context)
        chosen = sorted(item.selection)
        if not 0 <= index < len(chosen):
            return JOBJECT64(0)
        return JOBJECT64(self._take(item.children[chosen[index]].handle))

    @staticmethod
    def _selected_rows(item) -> list:
        if not item.column_count:
            return []
        return sorted({index // item.column_count for index in item.selection})

    @staticmethod
    def _selected_columns(item) -> list:
        if not item.column_count:
            return []
        return sorted({index % item.column_count for index in item.selection})

    def getAccessibleTableRowSelectionCount(self, vmid, accessible_context):
        self.calls["getAccessibleTableRowSelectionCount"] += 1
        return len(self._selected_rows(self._node(accessible_context)))

    def getAccessibleTableColumnSelectionCount(self, vmid, accessible_context):
        self.calls["getAccessibleTableColumnSelectionCount"] += 1
        return len(self._selected_columns(self._node(accessible_context)))

    def getAccessibleTableRowSelections(self, vmid, ctx, count, selections):
        self.calls["getAccessibleTableRowSelections"] += 1
        chosen = self._selected_rows(self._node(ctx))
        for position in range(min(count, len(chosen))):
            selections[position] = chosen[position]
        return 1

    def getAccessibleTableColumnSelections(self, vmid, ctx, count, selections):
        self.calls["getAccessibleTableColumnSelections"] += 1
        chosen = self._selected_columns(self._node(ctx))
        for position in range(min(count, len(chosen))):
            selections[position] = chosen[position]
        return 1

    def isAccessibleTableRowSelected(self, vmid, accessible_context, row):
        self.calls["isAccessibleTableRowSelected"] += 1
        return int(row in self._selected_rows(self._node(accessible_context)))

    def isAccessibleTableColumnSelected(self, vmid, accessible_context, column):
        self.calls["isAccessibleTableColumnSelected"] += 1
        return int(column in self._selected_columns(self._node(accessible_context)))

    # Anything else is a traversal doing something new: fail loudly.
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def unexpected(*args, **kwargs):
            raise AssertionError(
                f"the fake bridge does not implement bridge.{name}(); "
                "add it here with a call counter so the traversal stays measurable"
            )

        return unexpected


def bind(root: Node):
    """Return ``(element, bridge)`` with element bound to *root*."""
    bridge = CountingBridge(root)
    element = JABElement(
        bridge=bridge, hwnd=1234, vmid=1,
        accessible_context=JOBJECT64(root.handle),
    )
    return element, bridge
