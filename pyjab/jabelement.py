from __future__ import annotations

import sys
import warnings
from io import BytesIO

# See the matching guard in pyjab/jabdriver.py: fail with a clear message before
# any pywin32 import is attempted, instead of a bare ModuleNotFoundError.
if sys.platform != "win32":  # pragma: no cover - platform dependent
    raise ImportError(
        "pyjab drives the Windows Java Access Bridge and only runs on Windows.\n"
        "  detected platform: {!r}\n"
        "The package installs on every platform, but it can only run on "
        "Windows with a JDK installed.".format(sys.platform)
    )

import base64
from time import monotonic, sleep

from pyjab.common.logger import Logger
from pyjab.config import ELEMENT_POLL_INTERVAL
from pyjab.config import MAX_SEARCH_DEPTH
from pyjab.common.role import Role
from pyjab.common.states import States
from pyjab.common.textreader import TextReader
import re
from ctypes import Array, byref, CDLL, c_char, c_long, create_string_buffer
from ctypes.wintypes import HWND
from typing import Any, Generator, Optional, Union
from pyjab.common.by import By
from pyjab.common.png import bgra_to_png
from pyjab.common.exceptions import JABException
from pyjab.common.types import jint, JOBJECT64
from pyjab.common.win32utils import Win32Utils, physical_point
from pyjab.common.xpathparser import PARENT, XpathParser
from pyjab.accessibleinfo import (
    AccessibleActions,
    AccessibleActionsToDo,
    AccessibleContextInfo,
    AccessibleTableCellInfo,
    AccessibleTableInfo,
    AccessibleTextInfo,
    VisibleChildrenInfo,
)


class JABElement(object):
    int_func_err_msg = "Java Access Bridge func '{}' error"
    win32_utils = Win32Utils()
    xpath_parser = XpathParser()

    def __init__(
            self,
            bridge: CDLL = None,
            hwnd: HWND = None,
            vmid: c_long = None,
            accessible_context: JOBJECT64 = None,
    ) -> None:
        self.logger = Logger("pyjab")
        self._bridge = bridge
        # jab context attributes
        self._hwnd = hwnd
        self._vmid = vmid
        self._accessible_context = accessible_context
        self._acc_info = self._get_accessible_context_info

    @property
    def bridge(self) -> CDLL:
        return self._bridge

    @bridge.setter
    def bridge(self, bridge: CDLL) -> None:
        self._bridge = bridge

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

    @property
    def name(self) -> str:
        return self._acc_info().name

    @property
    def description(self) -> str:
        return self._acc_info().description

    @property
    def role(self) -> str:
        return self._acc_info().role

    @property
    def role_en_us(self) -> str:
        return self._acc_info().role_en_US

    @property
    def states(self) -> list[str]:
        return self._acc_info().states.split(",")

    @property
    def states_en_us(self) -> list[str]:
        return self._acc_info().states_en_US.split(",")

    @property
    def object_depth(self) -> int:
        return self._get_object_depth()

    @property
    def index_in_parent(self) -> int:
        return self._acc_info().indexInParent

    @property
    def children_count(self) -> int:
        """How many children the element has, **visible or not**.

        Read from the accessibility context info, so it costs nothing extra on an element
        whose info has already been fetched -- which is why it is the one :meth:`as_record`
        carries.

        **Not the same number as** :attr:`visible_children_count`, which is what a
        traversal yields and can be smaller when some children are hidden. Both are
        correct; a caller comparing this against ``len(list(element.walk()))`` and finding
        them different has found that difference rather than a bug.
        """
        return self._acc_info().childrenCount

    @property
    def visible_children_count(self) -> int:
        """How many children the bridge says are **visible**.

        Not the same number as :attr:`children_count`, and the difference is the point.

        * :attr:`children_count` comes from ``getAccessibleContextInfo`` and is the
          **total**, visible or not.
        * this one comes from ``getVisibleChildrenCount``, and it is what a traversal
          yields — :meth:`walk` steps through the visible children.

        So for an element with hidden children, ``children_count`` is larger than either
        this or ``len(list(element.walk()))``, and **both are correct**. Before this
        existed, a caller reading one and walking the other had no way to tell that apart
        from a bug or a truncated walk.

        Raises:
            JABException: the bridge refused the call. **A refused count is not a count of
                zero**, which is why this does not quietly return one — see
                :meth:`walk`, whose ``truncated`` is the other half of the same question.
        """
        # The same call _generate_childs_from_element makes, and the same check: the
        # symbol is registered without errorcheck, so a falsy return is a refused call
        # rather than an answer. AGENTS.md 2.7.
        result = self.bridge.getVisibleChildrenCount(self.vmid, self.accessible_context)
        if not result:
            raise JABException(self.int_func_err_msg.format("getVisibleChildrenCount"))
        return int(result)

    @property
    def bounds(self) -> dict:
        return {
            "x": self._acc_info().x,
            "y": self._acc_info().y,
            "height": self._acc_info().height,
            "width": self._acc_info().width,
        }

    @property
    def accessible_component(self) -> bool:
        return bool(self._acc_info().accessibleComponent)

    @property
    def accessible_action(self) -> bool:
        return bool(self._acc_info().accessibleAction)

    @property
    def accessible_selection(self) -> bool:
        return bool(self._acc_info().accessibleSelection)

    @property
    def accessible_text(self) -> bool:
        return bool(self._acc_info().accessibleText)

    @property
    def accessible_interfaces(self) -> bool:
        # TODO: need handle acc interface
        return False

    @property
    def text(self) -> Optional[str]:
        """The element's text, or None when it has no Accessible Text interface.

        An element that *does* support it but holds no characters returns "".
        It used to raise: charCount of 0 made chars_end -1, and JAB rejects a
        range of (0, -1). That turned "the field is empty now" -- exactly what
        ``clear()`` waits for -- into a RuntimeError.
        """
        if self.accessible_text:
            txt_info = self._get_accessible_text_info()
            if txt_info.charCount == 0:
                return ""
            chars_start = 0
            chars_end = txt_info.charCount - 1
            chars_len = chars_end + 1 - chars_start
            buffer = create_string_buffer((chars_len + 1) * 2)
            self._get_accessible_text_range(chars_start, chars_end, buffer, chars_len)
            return TextReader().get_text_from_raw_bytes(
                buffer=buffer, chars_len=chars_len, encoding="utf_16"
            )
        else:
            self.logger.warning("current JABElement does not support Accessible Text")

    @property
    def table(self) -> Optional[dict]:
        if self.role_en_us == Role.TABLE:
            info = self._get_accessible_table_info()
            tb = {
                "row_count": info.rowCount,
                "column_count": info.columnCount,
            }
            info = self._get_accessible_table_row_header()
            tb["row_headers"] = {
                "row_count": info.rowCount,
                "column_count": info.columnCount,
            }
            info = self._get_accessible_table_column_header()
            tb["column_headers"] = {
                "row_count": info.rowCount,
                "column_count": info.columnCount,
            }
            row_count = self._get_accessible_table_row_selection_count()
            column_count = self._get_accessible_table_column_selection_count()
            tb["selected"] = {
                "row_count": row_count,
                "column_count": column_count,
            }
            return tb
        else:
            self.logger.warning("current JABElement does not Accessible Table")

    # Jab Element actions
    def _generate_all_childs(
            self, jabelement: JABElement = None, visible: bool = False
    ) -> Generator[JABElement]:
        """generate all child jab elements from a jab element.

        Args:
            jabelement (JABElement, optional): The parent jab element to generate child jab elements.
            Defaults to None use current element.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Yields:
            Generator: Generator of all child jab elements from this parent jab element.
        """
        jabelement = jabelement or JABElement(
            self.bridge, self.hwnd, self.vmid, self.accessible_context
        )

        for _jabelement in self._generate_childs_from_element(
                jabelement=jabelement, visible=visible
        ):
            if _jabelement.children_count:
                yield from self._generate_all_childs(
                    jabelement=_jabelement, visible=visible
                )
            yield _jabelement

    def _search_element(
            self,
            root: JABElement,
            predicate,
            visible: bool = False,
            depth: int = 0,
    ) -> Optional[JABElement]:
        """Return the first element below *root* that satisfies *predicate*.

        Depth-first in document order, and each node is tested **before** its
        children are visited.

        That ordering is the point. Lookups used to go only through
        ``_generate_all_childs``, which yields a node *after* its whole subtree
        -- post-order. A match one level below the search root was therefore
        reached only once everything underneath it had been walked. On a window
        containing a large table that is the difference between a handful of
        cross-process calls and thousands, and it is what made a lookup take
        tens of seconds (issues #33, #29).

        Ownership: the returned element belongs to the caller. Every other
        element created here is released before returning. Children the
        generator had not produced yet simply never come into existence, because
        abandoning it is what stops the walk.
        """
        if depth >= MAX_SEARCH_DEPTH:
            # Not a failure: a lookup that has gone this deep is looking at a tree
            # that is not a tree.  Returning None lets the caller raise its usual
            # "not found", which is a better report than a hang and a better one
            # than a RecursionError from inside pyjab.
            self.logger.warning(
                "lookup stopped at depth %s without a match; the accessibility "
                "tree at this point is deeper than MAX_SEARCH_DEPTH (%s), or it "
                "contains a cycle",
                depth,
                MAX_SEARCH_DEPTH,
            )
            return None
        for child in self._generate_childs_from_element(
                jabelement=root, visible=visible
        ):
            if predicate(child):
                return child
            found = self._search_element(child, predicate, visible=visible,
                                         depth=depth + 1)
            self.release_jabelement(child)
            if found is not None:
                return found
        return None

    def _generate_childs_from_element(
            self, jabelement: JABElement = None, visible: bool = False
    ) -> Generator[JABElement]:
        """generate child jab elements from a jab element.

        Args:
            jabelement (JABElement, optional): The parent jab element to generate child jab elements.
            Defaults to None use current element.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Yields:
            Generator: Generator of child jab elements from this parent jab element.
        """
        jabelement = jabelement or JABElement(
            self.bridge, self.hwnd, self.vmid, self.accessible_context
        )

        if visible:
            # returnedChildrenCount describes the array we are about to index.
            # This used to call _get_visible_children_count() first and use *its*
            # answer to index this array, so two separate JAB calls had to agree
            # or the loop ran off the end into an IndexError.
            info = self._get_visible_children(jabelement.accessible_context)
            for index in range(info.returnedChildrenCount):
                yield JABElement(
                    jabelement.bridge,
                    jabelement.hwnd,
                    jabelement.vmid,
                    info.children[index],
                )
        else:
            for index in range(jabelement.children_count):
                child_acc = jabelement.bridge.getAccessibleChildFromContext(
                    jabelement.vmid, jabelement.accessible_context, index
                )
                yield JABElement(
                    jabelement.bridge, jabelement.hwnd, jabelement.vmid, child_acc
                )

    def send_keys(self, keys: str) -> None:
        """Send a keyboard shortcut to the window this element belongs to.

        Args:
            keys: the chord, such as ``"alt+y"``, with ``+`` between the key names. See
                :meth:`pyjab.common.win32utils.Win32Utils.send_keys` for the names.

        Raises:
            ValueError: a name is not a key, with the name it did not recognise.

        Note:
            **Nothing is focused first, and the element is not clicked.** The chord goes to
            whatever currently has the keyboard focus — which is deliberate, because
            clicking a control to focus its window would also activate that control, and a
            shortcut's whole purpose is usually to avoid doing that.
        """
        self.win32_utils.send_keys(keys)

    def focus(self) -> bool:
        """Bring this element's window to the foreground, and say whether it got there.

        Returns:
            bool: whether the window **is** the foreground window afterwards. **False is a
            normal answer** -- Windows refuses foreground activation from a service session,
            which is why this returns rather than raises. See #68.

        See :meth:`JABDriver.focus`. The element version exists because an element is what a
        caller usually has in hand after a lookup, and its ``hwnd`` is the same window.
        """
        return self.win32_utils.set_window_foreground(hwnd=self.hwnd)

    def as_record(self) -> dict:
        """This element's identity and geometry, as plain data.

        The fields are the ones a locator can match on, which is why they are these: a
        caller that wants to write a locator, or to check later that an element it holds a
        locator for is still the same element, needs exactly this set.

        Plain data on purpose. An element is a live JAB reference with a lifetime, and
        handing one to something that outlives the call is how this codebase has leaked
        twice. A dict cannot leak.
        """
        try:
            bounds = self.bounds or {}
        except Exception:                        # pragma: no cover - JAB dependent
            bounds = {}
        return {
            "role": self.role_en_us,
            "name": self.name or "",
            "description": self.description or "",
            "index_in_parent": self.index_in_parent,
            # `children_count` and not `visible_children_count`, deliberately. This is
            # the record a walk produces per node, and `children_count` comes from the
            # context info the walk has already fetched; the visible count is a second
            # bridge call per node. See visible_children_count for what the difference is
            # and why a caller that needs it should ask for it.
            "children_count": self.children_count,
            "object_depth": self.object_depth,
            "states": ",".join(self.states_en_us or []),
            "bounds": bounds,
        }

    def walk(self, max_depth: Optional[int] = None,
             limit: Optional[int] = None) -> "JABTree":
        """Walk this element's descendants, yielding ``(depth, record)``.

        **Ownership**: every record is plain data, and every JAB reference the walk takes
        is released before the next one is yielded. The caller never receives a reference
        and therefore cannot leak one -- which is the whole reason this yields records
        rather than ``JABElement``s. See :meth:`release_jabelement` for what goes wrong
        when a reference outlives its use.

        Args:
            max_depth (int, optional): How far below this element to go. ``0`` yields only
                the immediate children. Defaults to None, which does not limit depth.
            limit (int, optional): The most records to produce. Defaults to None.

        Returns:
            JABTree: an iterable of ``(depth, record)`` pairs. It is an object rather than
            a bare generator so that the caller can ask **whether the walk was cut short**
            -- see :attr:`JABTree.truncated`. A tree that was truncated and one that
            genuinely ends at the limit produce the same records, and a caller that cannot
            tell them apart will act on half a window.

        :Usage:
            tree = element.walk(max_depth=2, limit=200)
            for depth, item in tree:
                print("  " * depth, item["role"], item["name"])
            if tree.truncated:
                print("(partial: only the first", len(tree), "were read)")
        """
        return JABTree(self, max_depth=max_depth, limit=limit)

    def get_children(
        self, by: str = None, value: Optional[str] = None
    ) -> list[JABElement]:
        """Get the immediate children of this JABElement.

        Unlike the ``find_elements_by_*`` family this does not search
        descendants, and it does not raise when nothing matches: an element with
        no children is an ordinary state, so an empty list is returned.

        Args:
            by (str, optional): A ``By`` strategy used to filter the children.
            Defaults to None, which returns every immediate child.
            value (optional): The locator to filter by. Defaults to None.

        Returns:
            list[JABElement]: The immediate children. The caller owns these; pass
            each to :meth:`release_jabelement` when finished with it.
        """
        children = []
        for child in self._generate_childs_from_element():
            if by and not self._is_element_matched(
                jabelement=child, by=by, value=value
            ):
                # A filtered-out child is never handed to the caller, so it has
                # to be released here. JAB keeps its own reference to every
                # object it returns, so dropping it silently accumulates Java
                # objects for the life of the process -- see release_jabelement.
                self.release_jabelement(child)
                continue
            children.append(child)
        return children

    # JAB apis
    def release_jabelement(self, jabelement: JABElement = None) -> None:
        """Release the memory used by the Java object object,
        where object is an object returned to you by Java Access Bridge.
        Java Access Bridge automatically maintains a reference
        to all Java objects that it returns to you in the JVM
        so they are not garbage collected. To prevent memory leaks,
        you must call ReleaseJavaObject on all Java objects returned
        to you by Java Access Bridge once you are finished with them.
        See JavaFerret.c for an illustration of how to do this.

        Args:
            jabelement (JABElement): The JABElement need to release
        """
        accessible_context = (
            jabelement.accessible_context if jabelement else self.accessible_context
        )
        self.bridge.releaseJavaObject(self.vmid, accessible_context)

    def _request_focus(self, accessible_context: JOBJECT64 = None) -> None:
        """Request focus for a component. Returns whether successful."""
        accessible_context = accessible_context or self.accessible_context
        self.bridge.requestFocus(self.vmid, accessible_context)

    def _get_accessible_selection_from_context_index(
            self, index: int, accessible_context: JOBJECT64 = None
    ) -> JOBJECT64:
        """The accessible context of the ``index``-th selected child.

        JAB returns a reference it keeps, so the caller owns one release -- see
        :meth:`release_jabelement`.
        """
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleSelectionFromContext(
            self.vmid, accessible_context, index
        )

    def _get_accessible_selection_from_context(
            self, accessible_context: JOBJECT64 = None
    ) -> JOBJECT64:
        """The first selected child.

        Kept because several callers use it; this is the ``index=0`` case of
        :meth:`_get_accessible_selection_from_context_index`, which has the note
        about releasing what it returns.
        """
        return self._get_accessible_selection_from_context_index(0, accessible_context)

    def _add_accessible_selection_from_context(
            self, index: int, accessible_context: JOBJECT64 = None
    ) -> None:
        accessible_context = accessible_context or self.accessible_context
        self.bridge.addAccessibleSelectionFromContext(
            self.vmid, accessible_context, index
        )

    def _clear_accessible_selection_from_context(
            self, accessible_context: JOBJECT64
    ) -> None:
        accessible_context = accessible_context or self.accessible_context
        self.bridge.clearAccessibleSelectionFromContext(self.vmid, accessible_context)

    def _is_same_object(self, obj1: JOBJECT64, obj2: JOBJECT64) -> bool:
        """Returns whether two object references are for the same object.

        Args:
            obj1 (JOBJECT64): Object 1.
            obj2 (JOBJECT64): Object 2.

        Returns:
            bool: Rerturns whether two object is same or not.
        """
        return bool(self.bridge.isSameObject(self.vmid, obj1, obj2))

    def _get_top_level_object(self, accessible_context: JOBJECT64 = None) -> JOBJECT64:
        """Returns the AccessibleContext for the top level object in a Java window.
        This is same AccessibleContext that is obtained from GetAccessibleContextFromHWND for that window.
        Returns (AccessibleContext)0 on error.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get top level object error.

        Returns:
            JOBJECT64: Top level object.
        """
        accessible_context = accessible_context or self.accessible_context
        top_object = self.bridge.getTopLevelObject(self.vmid, accessible_context)
        if top_object == 0:
            raise JABException(self.int_func_err_msg.format("getTopLevelObject"))
        return top_object

    def _get_accessible_parent_from_context(
            self, accessible_context: JOBJECT64 = None
    ) -> JOBJECT64:
        """Returns an AccessibleContext object that represents the parent of object ac.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Returns:
            JOBJECT64: Parent Accessible Context.
        """
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleParentFromContext(self.vmid, accessible_context)

    def _get_accessible_context_info(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleContextInfo:
        """Retrieves an AccessibleContextInfo object of the AccessibleContext object ac.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accessible Context Info error.

        Returns:
            AccessibleContextInfo: Accessible Context Info.
        """
        info = AccessibleContextInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleContextInfo(
            self.vmid, accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("GetAccessibleContextInfo"))
        return info

    def _get_object_depth(self, accessible_context: JOBJECT64 = None) -> int:
        """Returns how deep in the object hierarchy a given object is.
        The top most object in the object hierarchy has an object depth of 0.
        Returns -1 on error.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Object Depth error.

        Returns:
            int: Object depth.
        """
        accessible_context = accessible_context or self.accessible_context
        object_depth = self.bridge.getObjectDepth(self.vmid, accessible_context)
        if object_depth == -1:
            raise JABException(self.int_func_err_msg.format("getObjectDepth"))
        return object_depth

    def _get_accessible_text_info(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleTextInfo:
        info = AccessibleTextInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTextInfo(
            self.vmid, accessible_context, byref(info), 0, 0
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleTextInfo"))
        return info

    def _get_accessible_text_range(
            self,
            start: int,
            end: int,
            text: Array[c_char],
            length: int,
            accessible_context: JOBJECT64 = None,
    ) -> None:
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTextRange(
            self.vmid, accessible_context, start, end, text, length
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getAccessibleTextRange"))

    def _get_accessible_table_info(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleTableInfo:
        """Returns information about the table, for example, caption, summary,
        row and column count, and the AccessibleTable.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accessible Table Info error.

        Returns:
            AccessibleTableInfo: Accessible Table Info.
        """
        info = AccessibleTableInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTableInfo(
            self.vmid, accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(self.int_func_err_msg.format("getAccessibleTableInfo"))
        return info

    def _get_accessible_table_row_header(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleTableInfo:
        """Returns the table row headers of the specified table as a table.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accessible Table Info error.

        Returns:
            AccessibleTableInfo: Accessible Table Info.
        """
        info = AccessibleTableInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTableRowHeader(
            self.vmid, accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableRowHeader")
            )
        return info

    def _get_accessible_table_column_header(
            self, accessible_context: JOBJECT64 = None
    ) -> AccessibleTableInfo:
        """Returns the table column headers of the specified table as a table.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accessible Table Info error.

        Returns:
            AccessibleTableInfo: Accessible Table Info.
        """
        info = AccessibleTableInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTableColumnHeader(
            self.vmid, accessible_context, byref(info)
        )
        if result == 0:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableColumnHeader")
            )
        return info

    def _get_accessible_table_row_selection_count(
            self, accessible_context: JOBJECT64 = None
    ) -> int:
        """Returns how many rows in the table are selected.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Returns:
            int: Accessible table row selection count.
        """
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleTableRowSelectionCount(
            self.vmid, accessible_context
        )

    def _get_accessible_table_column_selection_count(
            self, accessible_context: JOBJECT64 = None
    ) -> int:
        """Returns how many columns in the table are selected.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Returns:
            int: Accessible table column selection count.
        """
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleTableColumnSelectionCount(
            self.vmid, accessible_context
        )

    def _get_accessible_table_cell_info(
            self, row: int, column: int, accessible_context: JOBJECT64 = None
    ) -> AccessibleTableCellInfo:
        """Returns information about the specified table cell. The row and column specifiers are zero-based.

        Args:
            row (int): Row index in table.
            column (int): Column index in table.
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Raises:
            JABException: Get Accesible Table Cell Info error.

        Returns:
            AccessibleTableCellInfo: Accessible Table Cell Info.
        """
        info = AccessibleTableCellInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getAccessibleTableCellInfo(
            self.vmid, accessible_context, row, column, byref(info)
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableCellInfo")
            )
        return info

    # --- AccessibleTable selection ---------------------------------------
    #
    # A table is not like a list.  JAB has no call that selects a row, a column or
    # a cell: the only way in is the table's own AccessibleSelection, and the index
    # it wants is the one getAccessibleTableIndex maps (row, column) onto.  Adding
    # that index to the selection selects the cell; reading the selection back
    # gives the cell objects, which -- unlike the ones get_cell returns for many
    # tables -- are the ones the application will actually respond to.  That is the
    # difference between the "Cells" and "Select Cells" properties in #57 and #61.

    def _get_accessible_table_row_selections(
            self, accessible_context: JOBJECT64 = None
    ) -> list:
        """The row indices this table reports as selected.

        Returns:
            list: zero-based row indices, empty when the table reports none.

        Raises:
            JABException: getAccessibleTableRowSelections error.
        """
        accessible_context = accessible_context or self.accessible_context
        count = self._get_accessible_table_row_selection_count(accessible_context)
        if count <= 0:
            return []
        selections = (jint * count)()
        result = self.bridge.getAccessibleTableRowSelections(
            self.vmid, accessible_context, count, selections
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableRowSelections")
            )
        return list(selections)

    def _get_accessible_table_column_selections(
            self, accessible_context: JOBJECT64 = None
    ) -> list:
        """The column indices this table reports as selected.

        Returns:
            list: zero-based column indices, empty when the table reports none.

        Raises:
            JABException: getAccessibleTableColumnSelections error.
        """
        accessible_context = accessible_context or self.accessible_context
        count = self._get_accessible_table_column_selection_count(accessible_context)
        if count <= 0:
            return []
        selections = (jint * count)()
        result = self.bridge.getAccessibleTableColumnSelections(
            self.vmid, accessible_context, count, selections
        )
        if not result:
            raise JABException(
                self.int_func_err_msg.format("getAccessibleTableColumnSelections")
            )
        return list(selections)

    def _is_accessible_table_row_selected(
            self, row: int, accessible_context: JOBJECT64 = None
    ) -> bool:
        """Whether one row is selected.

        No errorcheck on the binding, so a False here is the bridge's answer rather
        than a swallowed exception -- see the comment beside it in
        ``pyjab/jabfixedfunc.py``.
        """
        accessible_context = accessible_context or self.accessible_context
        return bool(
            self.bridge.isAccessibleTableRowSelected(
                self.vmid, accessible_context, row
            )
        )

    def _is_accessible_table_column_selected(
            self, column: int, accessible_context: JOBJECT64 = None
    ) -> bool:
        """Whether one column is selected."""
        accessible_context = accessible_context or self.accessible_context
        return bool(
            self.bridge.isAccessibleTableColumnSelected(
                self.vmid, accessible_context, column
            )
        )

    def _get_accessible_selection_count_from_context(
            self, accessible_context: JOBJECT64 = None
    ) -> int:
        """How many children the accessible selection holds.

        Zero is the ordinary answer for a freshly-opened list or table.
        """
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleSelectionCountFromContext(
            self.vmid, accessible_context
        )

    def _is_accessible_child_selected(
            self, index: int, accessible_context: JOBJECT64 = None
    ) -> bool:
        """Whether the selection child at ``index`` is selected.

        False is the bridge's answer rather than a swallowed failure: the binding
        is declared without errorcheck, exactly as
        :meth:`_is_accessible_table_row_selected` is.

        This exists because ``addAccessibleSelectionFromContext`` is a **toggle**,
        not an add.  ``AccessibleJTable.addAccessibleSelection(i)`` calls
        ``JTable.changeSelection(row, column, true, false)``, so adding a cell that
        is already selected removes it again.  Asking first is what makes a loop of
        adds terminate on the answer the caller wanted.
        """
        accessible_context = accessible_context or self.accessible_context
        return bool(
            self.bridge.isAccessibleChildSelectedFromContext(
                self.vmid, accessible_context, index
            )
        )

    def _get_accessible_table_index(
            self, row: int, column: int, accessible_context: JOBJECT64 = None
    ) -> int:
        """The selection index of the cell at (row, column).

        This is the number ``addAccessibleSelectionFromContext`` wants.  It *is*
        the row-major position: JAB computes it as ``row * columnCount + column``
        (``JABAccessBridge.java``, ``getAccessibleTableIndex``), and
        ``AccessibleJTable.getAccessibleColumnAtIndex`` divides it back the same
        way.  It used to say here that it was not the row-major position, which was
        wrong -- the ask is still worth making, because the column count comes from
        the application rather than from pyjab, but not because the arithmetic
        differs.
        """
        accessible_context = accessible_context or self.accessible_context
        return self.bridge.getAccessibleTableIndex(
            self.vmid, accessible_context, row, column
        )

    def _select_accessible_table_index(
            self, index: int, accessible_context: JOBJECT64 = None
    ) -> None:
        """Add one selection index to the table's selection."""
        accessible_context = accessible_context or self.accessible_context
        self.bridge.addAccessibleSelectionFromContext(
            self.vmid, accessible_context, index
        )

    def _get_visible_children_count(self, accessible_context: JOBJECT64 = None) -> int:
        """Returns the number of visible children of a component. Returns -1 on error.

        Args:
            accessible_context (JOBJECT64, optional): Accessible Context. Defaults to None.

        Returns:
            int: [description]
        """
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getVisibleChildrenCount(self.vmid, accessible_context)
        if result == -1:
            raise JABException(self.int_func_err_msg.format("getVisibleChildrenCount"))
        return result

    def _get_visible_children(
            self, accessible_context: JOBJECT64 = None
    ) -> VisibleChildrenInfo:
        info = VisibleChildrenInfo()
        accessible_context = accessible_context or self.accessible_context
        result = self.bridge.getVisibleChildren(
            self.vmid, accessible_context, 0, byref(info)
        )
        if not result:
            raise JABException(self.int_func_err_msg.format("getVisibleChildren"))
        return info

    def _do_accessible_action(self, action: str = None) -> None:
        """Do Accessible Action with current JABElement.

        Args:
            action (str): Accessible Action name.

        Raises:
            JABException: Raise JABException if current JABElement does not support this action.
        """
        acc_acts = AccessibleActions()
        self.bridge.getAccessibleActions(
            self.vmid, self.accessible_context, byref(acc_acts)
        )
        acc_acts_count = acc_acts.actionsCount
        acc_acts_info = acc_acts.actionInfo
        act_todo = AccessibleActionsToDo()
        if acc_acts_count < 1:
            raise JABException("JABElement does not support Accessible Action")
        if acc_acts_count > 1:
            if action is None:
                raise JABException(
                    "JABElement support multiple Accessible Action, please specifc"
                )
            act_todo.actions[0].name = action
            for index in range(acc_acts_count):
                if acc_acts_info[index].name.lower() == action:
                    break
            else:
                raise JABException(f"JABElement does not support action '{action}'")
        if acc_acts_count == 1:
            act_todo.actions[0].name = acc_acts_info[0].name
        act_todo.actionsCount = 1
        # 'failure' receives the index of an action that failed. A bare jint()
        # instance used to be passed here: ctypes accepts that (it passes the
        # instance's own address), so nothing raised -- but the value was written
        # into a temporary and thrown away. Passing it properly costs nothing and
        # makes it observable.
        #
        # doAccessibleActions is registered with errorcheck=True, so a refused
        # call already raises RuntimeError; this is diagnostic only.
        failure = jint()
        self.bridge.doAccessibleActions(
            self.vmid, self.accessible_context, byref(act_todo), byref(failure)
        )
        self.logger.debug(
            "doAccessibleActions action '%s' reported failure index %s",
            action,
            failure.value,
        )

    def click(self, simulate: bool = False) -> None:
        """Simulates clicking to JABElement.

        Default will use JAB Accessible Action.
        Set parameter 'simulate' to True if internal action does not work.

        Args:
            simulate (bool, optional): Simulate user click action by mouse event. Defaults to False.

        Raises:
            ValueError: Raise ValueError when JABElement width or height is 0.

        Use this to send simple mouse events or to click form fields::

            form_button = driver.find_element_by_name('button')
            form_button.click()
            form_button.click(simulate=True)
        """
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            position_x, position_y = self._physical_point(*self._click_point())
            self.win32_utils._click_mouse(x=position_x, y=position_y)
        else:
            self._do_accessible_action(action="click")

    def double_click(self) -> None:
        """Double-click this JABElement with the mouse.

        Note:
            There is no accessibility action for a double click, so unlike
            :meth:`click` this always moves the mouse and therefore needs usable
            bounds.  It does nothing for a table cell, which reports bounds of -1.

            See :meth:`context_click` for the right button, and
            :mod:`docs/6-Troubleshooting` for the recipe this replaces: two
            ``click()`` calls, which only work if they happen to land inside the
            system's double-click interval.

        Example:
            ``element.double_click()``
        """
        self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        position_x, position_y = self._physical_point(*self._click_point())
        self.win32_utils._double_click_mouse(x=position_x, y=position_y)

    def context_click(self) -> None:
        """Right-click this JABElement, to open its context menu.

        As with :meth:`double_click` there is no accessibility action for this,
        so it moves the mouse and needs usable bounds.

        Example:
            ``element.context_click()``
        """
        self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        position_x, position_y = self._physical_point(*self._click_point())
        self.win32_utils._click_mouse(x=position_x, y=position_y, button="right")

    def _without_duplicates(self, elements: list) -> list:
        """One entry per node, releasing the repeats.

        XPath defines a node-set as "an unordered collection of nodes without
        duplicates", and a path can reach the same node twice: `//panel/..` reaches
        a parent once per child, and two branches of a union can overlap. Both are
        ordinary, and both have to collapse here.

        The repeat is *released*, not dropped. The caller owns one reference to each
        element it is handed, so a second reference to the same node would be
        released twice -- use-after-free, which tests/_fakejab.py treats as an error
        rather than letting it pass.
        """
        kept: list = []
        for element in elements:
            if any(self._is_same_object(element.accessible_context,
                                        other.accessible_context)
                   for other in kept):
                self.release_jabelement(element)
                continue
            kept.append(element)
        return kept

    def _physical_point(self, x: int, y: int) -> tuple:
        """JAB's point for this element, in the coordinates the mouse API wants.

        The two are not always the same -- see
        :func:`pyjab.common.win32utils.physical_point` and issue #62. Everything
        that moves the real mouse goes through here, so the conversion happens once
        per click rather than once per caller.
        """
        return physical_point(x, y, hwnd=self.hwnd)

    def _click_point(self) -> tuple:
        """The screen position to move the mouse to in order to click this element.

        Returns:
            tuple: ``(x, y)``, the element's centre.

        Raises:
            JABException: when the element reports no usable bounds.  Anything
                JAB does not actually place on screen -- a table cell, most
                often -- reports ``-1`` for x, y, width and height, and using
                those values moves the cursor to the corner of the display
                instead of failing.  Only the accessibility action works for such
                an element.
        """
        bounds = self.bounds
        x, y = bounds.get("x"), bounds.get("y")
        width, height = bounds.get("width"), bounds.get("height")

        if None in (x, y, width, height) or width <= 0 or height <= 0:
            raise JABException(
                "JABElement reports no usable bounds "
                f"(x={x}, y={y}, width={width}, height={height}), so it cannot be "
                "clicked with the mouse. Table cells and anything else JAB does "
                "not place on screen report -1 here; use the accessibility action "
                "instead (simulate=False for click())."
            )

        return round(x + width / 2), round(y + height / 2)

    def clear(self, simulate: bool = False, wait_for_text_update: bool = True) -> None:
        """Clear existing text from JABElement.

        Default will use JAB Accessible Action.
        Set parameter 'simulate' to True if internal action does not work.

        Args:
            simulate (bool, optional): Simulate user input action by keyboard event. Defaults to False.
            wait_for_text_update (bool, optional): Waits for the text attribute to be empty. Defaults to True.

        Use this to send simple key events or to fill out form fields::

            form_textfield = driver.find_element_by_name('username')
            form_textfield.clear()
            from_textfield.send_text(simulate=True)
        """
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            self._request_focus()
            if self.accessible_text and self.text:
                self.win32_utils._press_key("end")
                for _ in self.text:
                    self.win32_utils._press_key("backspace")
        else:
            self.send_text(value="", simulate=False)
        if not wait_for_text_update or self.role != Role.TEXT:
            return
        self._wait_for_value_to_be(
            None, lambda: self.text, error_msg_function="clear text"
        )

    # --- scroll into view (issue #15) ------------------------------------
    #
    # JAB exposes no scroll position: there is no call that says where a scroll bar
    # is, and the PropertyVisibleDataChange event fires without saying where it
    # went.  So this cannot compute an offset and jump to it.  What it can do is
    # compare rectangles, nudge the scroll bar, and look again -- which is the
    # approach the reporter of #15 proposed and the only one available.

    def bounds_within(self, container: JABElement) -> bool:
        """Whether this element's rectangle lies inside ``container``'s.

        A rectangle fully inside another is the geometric half of "on screen".
        Two caveats that matter in practice:

        * Swing reports ``-1`` for each of x, y, width and height on controls it
          has no rectangle for -- a table cell scrolled out of view is the usual
          case (#20, #61).  There is nothing to compare, so this answers False
          rather than trying arithmetic on -1.
        * It is not the same question as :meth:`is_visible`, which reads the
          ``visible`` *state*.  A control can be visible and scrolled out of its
          viewport, which is the whole problem here.

        Args:
            container (JABElement): the rectangle to test against, usually a
                scroll pane.

        Returns:
            bool: True when this element's rectangle is inside the container's.
        """
        inner = self.bounds
        outer = container.bounds
        if any(inner[key] < 0 for key in ("x", "y", "width", "height")):
            return False
        if any(outer[key] < 0 for key in ("x", "y", "width", "height")):
            return False
        return (
            inner["x"] >= outer["x"]
            and inner["y"] >= outer["y"]
            and inner["x"] + inner["width"] <= outer["x"] + outer["width"]
            and inner["y"] + inner["height"] <= outer["y"] + outer["height"]
        )

    def _scrollable_ancestor(self, max_depth: int = 12):
        """The nearest ancestor that can scroll, or None.

        A scroll pane is the usual answer.  A panel that merely contains a scroll
        bar also counts, because that is how some applications lay one out.
        """
        current = self
        walker = None
        for _ in range(max_depth):
            try:
                parent = current.parent
            except JABException:
                return None
            if parent is None or not parent.accessible_context:
                return None

            found = parent.role_en_us == Role.SCROLL_PANE
            if not found:
                probe = None
                try:
                    probe = parent.find_element_by_role(Role.SCROLL_BAR)
                    found = True
                except JABException:
                    found = False
                finally:
                    # find_element_by_role hands out an object the caller owns; not
                    # releasing it leaks one reference per call.
                    self._release_walk(probe)
            if found:
                # Anything taken on the way up is dead now -- JAB keeps a
                # reference to every object it hands out, so leaking them here
                # would accumulate one per call for the life of the process,
                # which is the shape of #43.
                self._release_walk(walker)
                return parent

            self._release_walk(walker)
            walker = parent
            current = parent
        self._release_walk(walker)
        return None

    @staticmethod
    def _release_walk(element) -> None:
        """Release an ancestor that the walk has finished with, if there is one."""
        if element is not None:
            try:
                element.release_jabelement()
            except JABException:
                # A failed load, or an already-released object: nothing to do, and
                # raising here would turn "could not scroll" into a crash.
                pass

    def scroll_into_view(
            self,
            max_steps: int = 10,
            hold: int = 1,
            poll_interval: float = ELEMENT_POLL_INTERVAL,
    ) -> bool:
        """Scroll until this element is inside its scrollable ancestor.

        Best effort, and it returns what it achieved rather than assuming success.
        There is no scroll position to compute from -- see the note above the
        class of methods -- so this nudges the vertical scroll bar one step at a
        time and re-reads the rectangle, stopping when the element is inside, when
        the rectangle stops changing (the bar is at its end), or after
        ``max_steps``.

        Args:
            max_steps (int, optional): how many scroll steps to try. Defaults to 10.
            hold (int, optional): mouse hold time for each scroll step, in the same
                units as :meth:`scroll`. Defaults to 1.
            poll_interval (float, optional): pause between steps, to let the
                application repaint before the rectangle is read again. Defaults
                to ``ELEMENT_POLL_INTERVAL``.

        Returns:
            bool: whether the element ended up inside its scrollable ancestor.
            False also means "there is no scrollable ancestor", which is not an
            error -- a control that does not scroll is simply not this problem.

        Note:
            Needs valid bounds on both this element and the ancestor.  A table
            whose cells report ``-1`` cannot be scrolled this way, and the
            accessibility action path is the only option -- see
            :meth:`select_cell`.
        """
        ancestor = self._scrollable_ancestor()
        if ancestor is None:
            return False
        try:
            if self.bounds_within(ancestor):
                return True

            try:
                scroll_bar = ancestor.find_element_by_role(Role.SCROLL_BAR)
            except JABException:
                return False
            try:
                for _ in range(max_steps):
                    before = self.bounds
                    scroll_bar.scroll(to_bottom=True, hold=hold)
                    sleep(poll_interval)
                    if self.bounds_within(ancestor):
                        return True
                    if self.bounds == before:
                        # The bar is at its end, or the mouse action did not take.
                        # More steps would be the same step.
                        return False
                return self.bounds_within(ancestor)
            finally:
                self._release_walk(scroll_bar)
        finally:
            # Both find_element_by_role and the ancestor walk hand out objects the
            # caller owns.  Leaving them unreleased accumulates a Java object per
            # call, which is the shape of #43.
            self._release_walk(ancestor)

    def scroll(self, to_bottom: bool = True, hold: int = 2) -> None:
        """Scroll a scoll bar to top or to bottom.

        Need improvement for scroll to specific position.

        Args:
            to_bottom (bool, optional): Scroll to bottom or not, otherwise scroll to top. Defaults to True.
            hold (int, optional): Mouse hold time to scroll to bar. Default to 2.

        Raises:
            JABException: Raise a JABException when JABElement role is not a scroll bar.
        """
        if self.role_en_us != Role.SCROLL_BAR:
            raise JABException("JABElement is not 'scroll bar'")
        is_horizontal = "horizontal" in self.states_en_us
        x = self.bounds["x"]
        y = self.bounds["y"]
        height = self.bounds["height"]
        width = self.bounds["width"]
        self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        # horizontal scroll to bottom(right)
        if to_bottom and is_horizontal:
            x = x + width - height - 5
            y = y + height / 2
        elif to_bottom:
            x = x + width / 2
            y = y + height - width - 5
        elif is_horizontal:
            x = x + height + 5
            y = y + height / 2
        else:
            x = x + width / 2
            y = y + width + 5
        click_x, click_y = self._physical_point(int(x), int(y))
        self.win32_utils._click_mouse(x=click_x, y=click_y, hold=hold)

    def slide(self, to_bottom: bool = True, hold: int = 5) -> None:
        """Slide a slider to top or to bottom.

        Need improvement for slide to specific position.

        Args:
            to_bottom (bool, optional): Slide to bottom or not, otherwise slide to top. Defaults to True.
            hold (int, optional): Mouse hold time to slide. Default to 2.

        Raises:
            JABException: Raise a JABException when JABElement role is not a slider.
        """
        if self.role_en_us != "slider":
            raise JABException("JABElement is not 'slider'")
        is_horizontal = "horizontal" in self.states_en_us
        x = self.bounds["x"]
        y = self.bounds["y"]
        height = self.bounds["height"]
        width = self.bounds["width"]
        self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        # horizontal slide to bottom(right)
        if to_bottom and is_horizontal:
            x = x + width - 5
            y = y + height / 2
        elif to_bottom:
            x = x + width / 2
            y = y + height - 5
        elif is_horizontal:
            y = y + height / 2
        else:
            x = x + width / 2
        click_x, click_y = self._physical_point(int(x), int(y))
        self.win32_utils._click_mouse(x=click_x, y=click_y, hold=hold)

    def select(self, option: str, simulate: bool = False, wait_for_selection: bool = True) -> None:
        """Select an item from JABElement selector.
        Support select action from combo box, page tab list, list and menu.

        Args:
            option (str): Item selection from selector.
            simulate (bool, optional): Simulate user input action by mouse event. Defaults to False.
            wait_for_selection (bool, optional): Waits for selection equal to the option value. Defaults to True.

        Raises:
            JABException: this element is not one of the four supported roles.  A
                table is told so by name, and pointed at the methods that do apply
                to it, rather than raising KeyError('table') (#57).
        """
        handlers = {
            "combo box": self._select_from_combobox,
            "page tab list": self._select_from_page_tab_list,
            "list": self._select_from_list,
            "menu": self._select_from_menu,
        }
        if self.role_en_us not in handlers:
            if self.role_en_us == Role.TABLE:
                # A table has no named options: what you select is a position.
                # This used to be KeyError('table'), which said what went wrong
                # but not what to do about it.
                raise JABException(
                    "select() does not apply to a table -- a table is selected by "
                    "position, not by name. Use select_cell(row, column), "
                    "select_row(row), select_column(column) or select_all(), then "
                    "read the result back with get_selected_elements()."
                )
            raise JABException(
                f"select() does not support a '{self.role_en_us}'; it works on a "
                "combo box, page tab list, list or menu"
            )
        handlers[self.role_en_us](option=option, simulate=simulate)
        if wait_for_selection:
            self._wait_for_value_to_contain(
                [States.SELECTED, States.CHECKED],
                lambda: self.find_element_by_name(option).states_en_us,
            )

    def _add_selection_from_accessible_context(
            self, parent: JABElement, option: str
    ) -> None:
        try:
            item = parent.find_element_by_name(value=option)
        except JABException as e:
            raise JABException(
                f"{parent.role_en_us} option '{option}' not found"
            ) from e

        self._add_accessible_selection_from_context(
            item.index_in_parent, parent.accessible_context
        )

    def _select_from_checkbox(self, simulate: bool = False) -> None:
        if self.role_en_us != "check box":
            raise JABException("JABElement is not 'check box'")
        self._request_focus()
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        self.click(simulate=simulate)

    def _select_from_combobox(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "combo box":
            raise JABException("JABElement is not 'combo box'")
        self._request_focus()
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            self._do_accessible_action(action="togglepopup")
            self._add_selection_from_accessible_context(
                parent=self.find_element_by_role("list"), option=option
            )
            self.win32_utils._press_key("enter")
            return
        self._clear_accessible_selection_from_context(self.accessible_context)
        self._add_selection_from_accessible_context(parent=self, option=option)

    def _select_from_page_tab_list(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "page tab list":
            raise JABException("JABElement is not 'page tab list'")
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            self.find_element_by_name(option).click(simulate=True)
            return
        self._add_selection_from_accessible_context(self, option=option)

    def _select_from_list(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != Role.LIST:
            raise JABException("JABElement is not 'list'")
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
        self.find_element_by_name(value=option).click(simulate=simulate)

    def _select_from_menu(self, option: str, simulate: bool = False) -> None:
        if self.role_en_us != "menu":
            raise JABException("JABElement is not 'menu'")
        if simulate:
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            self.click(simulate=True)
            for item in self.find_elements_by_object_depth(self.object_depth + 1):
                if not item.accessible_action:
                    continue
                self.win32_utils._press_key("down_arrow")
                if item.name == option:
                    self.win32_utils._press_key("enter")
                    break
        else:
            self.find_element_by_name(value=option).click(simulate=False)

    def spin(
            self, option: str = None, increase: bool = True, simulate: bool = False
    ) -> None:
        if self.role_en_us != "spinbox":
            raise JABException("JABElement is not 'spinbox'")
        # select spinbox by set text
        if option:
            try:
                text = self.find_element_by_role("text")
            except JABException as e:
                raise JABException(
                    "Current spinbox does not support set 'option', try with 'increase'"
                ) from e
            text.send_text(value=option, simulate=simulate)
            return
        # select spinbox by accessible action or simulate click
        if increase:
            action = "increment"
            offset_y_position = -5
        else:
            action = "decrement"
            offset_y_position = 5
        if simulate:
            x = self.bounds["x"]
            y = self.bounds["y"]
            height = self.bounds["height"]
            width = self.bounds["width"]
            self.win32_utils._set_window_foreground(hwnd=self.hwnd)
            x = x + width - 5
            y = y + height / 2 + offset_y_position
            click_x, click_y = self._physical_point(int(x), int(y))
            self.win32_utils._click_mouse(x=click_x, y=click_y)
            return
        self._do_accessible_action(action=action)

    def expand(self, simulate: bool = False) -> None:
        """Expand this JABElement, if it is not already expanded.

        Note:
            This used to send the accessibility action ``toggleexpand``
            unconditionally, and to click **twice** when asked to simulate.  Both
            do the opposite of what the name promises once the element is already
            expanded: the action collapses it, and two clicks cancel each other
            out.  Expanding an already-expanded node therefore left it collapsed
            and hid the children the call was made for.

            ``simulate=True`` sends a single click now.  Whether that expands
            anything depends on the click landing on the expand handle rather
            than the row, which is why the accessibility action is the default.
        """
        if "expandable" not in self.states_en_us:
            raise JABException("JABElement does not support 'expand'")
        if States.EXPANDED in self.states_en_us:
            return
        if simulate:
            self.click(simulate=True)
            return
        self._do_accessible_action("toggleexpand")

    def send_text(self, value: Union[str, int], simulate: bool = False, wait_for_text_update: bool = True) -> None:
        """Type into the JABElement.

        Default will use JAB Accessible Action.
        Set parameter 'simulate' to True if internal action does not work.

        :Args:
            value (str, int): A string for typing.
            simulate (bool, optional): Simulate user input action by keyboard event. Defaults to False.
            wait_for_text_update (bool, optional): Waits for the text attribute to be equal to the input value. Defaults to True.

        Use this to send simple key events or to fill out form fields::

            form_textfield = driver.find_element_by_name('username')
            form_textfield.send_text("admin")
            from_textfield.send_text("admin", simulate=True)
        """
        value = str(value)
        if simulate:
            self.clear(True, wait_for_text_update)
            self.win32_utils._send_keys(value)
        else:
            result = self.bridge.setTextContents(
                self.vmid, self.accessible_context, value
            )
            if result == 0:
                raise JABException(
                    self.int_func_err_msg.format("setTextContents")
                    + ", try set parameter 'simulate' with True"
                )
        if not wait_for_text_update or self.role != Role.TEXT:
            return
        self._wait_for_value_to_be(
            value,
            lambda: self.text,
            error_msg_function=f"update text attribute to '{value}'",
        )

    def is_checked(self) -> bool:
        """Returns whether the JABElement is checked.

        Can be used to check if a checkbox or radio button is checked.
        """
        return States.CHECKED in self.states_en_us

    def is_enabled(self) -> bool:
        """Returns whether the JABElement is enabled."""
        return States.ENABLED in self.states_en_us

    def is_visible(self) -> bool:
        """Returns whether the JABElement is visible."""
        return States.VISIBLE in self.states_en_us

    def is_showing(self) -> bool:
        """Returns whether the JABElement is showing."""
        return States.SHOWING in self.states_en_us

    def is_expanded(self) -> bool:
        """Returns whether the JABElement is expanded.

        The companion to :meth:`expand`, and to :meth:`is_checked`,
        :meth:`is_enabled` and :meth:`is_visible`.  A tree node, a combo box or
        any other element that can be opened reports ``expanded`` while it is.
        """
        return States.EXPANDED in self.states_en_us

    def is_selected(self) -> bool:
        """Returns whether the JABElement is selected."""
        return States.SELECTED in self.states_en_us

    def is_editable(self) -> bool:
        """Returns whether the JABElement is editable."""
        return States.EDITABLE in self.states_en_us

    def find_element_by_name(self, value: str, visible: bool = False) -> JABElement:
        """find child JABElement by name

        Args:
            value (str): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.NAME, value=value, visible=visible)

    def find_element_by_description(
            self, value: str, visible: bool = False
    ) -> JABElement:
        """find child JABElement by description

        Args:
            value (str): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.DESCRIPTION, value=value, visible=visible)

    def find_element_by_role(self, value: str, visible: bool = False) -> JABElement:
        """find child JABElement by role

        Args:
            value (str): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.ROLE, value=value, visible=visible)

    def find_element_by_states(self, value: Union[list, str], visible: bool = False) -> JABElement:
        """find child JABElement by states

        Args:
            value (list): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.STATES, value=value, visible=visible)

    def find_element_by_object_depth(
            self, value: int, visible: bool = False
    ) -> JABElement:
        """find child JABElement by object depth

        Args:
            value (int): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.OBJECT_DEPTH, value=value, visible=visible)

    def find_element_by_children_count(
            self, value: int, visible: bool = False
    ) -> JABElement:
        """find child JABElement by children count

        Args:
            value (int): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.CHILDREN_COUNT, value=value, visible=visible)

    def find_element_by_index_in_parent(
            self, value: int, visible: bool = False
    ) -> JABElement:
        """find child JABElement by index in parent

        Args:
            value (int): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The JABElement find by locator
        """
        return self.find_element(by=By.INDEX_IN_PARENT, value=value, visible=visible)

    @staticmethod
    def _is_match_attr_name(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by name.

        Args:
            attr_val (str): Attribute name value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        if attr_val[0] in ["'", '"'] and attr_val[-1] in ["'", '"']:
            attr_val = attr_val[1:-1]
        pattern = re.compile(r"^contains\([\"'](.*?)[\"']\)")
        if content := pattern.findall(attr_val):
            return content[0] in jabelement.name
        else:
            return attr_val == jabelement.name

    @staticmethod
    def _is_match_attr_description(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by description.

        Args:
            attr_val (str): Attribute description value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        if attr_val[0] in ["'", '"'] and attr_val[-1] in ["'", '"']:
            attr_val = attr_val[1:-1]
        pattern = re.compile(r"^contains\([\"'](.*?)[\"']\)")
        if content := pattern.findall(attr_val):
            return content[0] in jabelement.description
        else:
            return attr_val == jabelement.description

    @staticmethod
    def _is_match_attr_role(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by role.

        Args:
            attr_val (str): Attribute description value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        if attr_val[0] in ["'", '"'] and attr_val[-1] in ["'", '"']:
            attr_val = attr_val[1:-1]
        pattern = re.compile(r"^contains\([\"'](.*?)[\"']\)")
        if content := pattern.findall(attr_val):
            return content[0] in jabelement.role
        else:
            return attr_val == jabelement.role

    @staticmethod
    def _is_match_attr_states(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by states.

        Args:
            attr_val (str): Attribute states value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        if attr_val[0] in ["'", '"'] and attr_val[-1] in ["'", '"']:
            attr_val = attr_val[1:-1]
        pattern = re.compile(r"^contains\([\"'](.*?)[\"']\)")
        if content := pattern.findall(attr_val):
            return all(stat in jabelement.states_en_us for stat in content[0].split(","))
        else:
            return set(attr_val.split(",")) == set(jabelement.states_en_us)

    @staticmethod
    def _is_match_attr_objectdepth(attr_val: str, jabelement: JABElement) -> bool:
        """Return the attribute value is matched or not by object depth.

        Args:
            attr_val (str): Attribute object depth value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        return int(attr_val) == jabelement.object_depth

    @staticmethod
    def _is_match_attr_childrencount(
            attr_val: str, jabelement: JABElement
    ) -> bool:
        """Return the attribute value is matched or not by children count.

        Args:
            attr_val (str): Attribute children count value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        return int(attr_val) == jabelement.children_count

    @staticmethod
    def _is_match_attr_indexinparent(
            attr_val: str, jabelement: JABElement
    ) -> bool:
        """Return the attribute value is matched or not by index in parent.

        Args:
            attr_val (str): Attribute index in parent value
            jabelement (JABElement): The JABElement

        Returns:
            bool: True for attribute matched False for not
        """
        return int(attr_val) == jabelement.index_in_parent

    def _is_match_attributes(
            self, attributes: list[dict], jabelement: JABElement
    ) -> bool:
        """Return the node attributes is matched or not with specific JABElement.


        Args:
            attributes (list[dict]): List of attribute contains
            "name" of attribute and "value" of attribute conditions
            jabelement (JABElement): The JABElement

        Raises:
            JABException: Incorrect attribute name found

        Returns:
            bool: True for attributes matched False for not
        """
        dict_attribute = {
            By.NAME: self._is_match_attr_name,
            By.ROLE: self._is_match_attr_role,
            By.DESCRIPTION: self._is_match_attr_description,
            By.STATES: self._is_match_attr_states,
            By.OBJECT_DEPTH: self._is_match_attr_objectdepth,
            By.CHILDREN_COUNT: self._is_match_attr_childrencount,
            By.INDEX_IN_PARENT: self._is_match_attr_indexinparent,
        }
        # `and` binds tighter than `or`, as it does in XPath: the predicates are
        # split into groups at each `or` and the groups are ORed, so
        # `[@a and @b or @c]` means `(a and b) or c` rather than anything else.
        #
        # `or` used to be discarded by the parser, so every predicate was ANDed --
        # a locator written with `or` matched nothing and reported "no element",
        # which reads as the element being absent rather than the locator being
        # wrong. Rejecting it would have been better than that; honouring it is
        # better still.
        groups = [[]]
        for attribute in attributes:
            if groups[-1] and attribute.get("operator") == "or":
                groups.append([attribute])
            else:
                groups[-1].append(attribute)

        for group in groups:
            matched = True
            for attribute in group:
                name = attribute.get("name")
                value = attribute.get("value")
                if name not in dict_attribute.keys():
                    raise JABException(f"incorrect attribute name '{name}'")
                comparison = attribute.get("comparison", "=")
                if comparison == "=":
                    # Equality keeps going through the matchers, which also understand
                    # contains(...) -- something a comparison has no meaning for.
                    ok = dict_attribute[name](value, jabelement)
                else:
                    ok = self._compare_attribute(name, comparison, value, jabelement)
                if not ok:
                    matched = False
                    break
            if matched:
                return True
        return False

    #: The JAB attribute each By constant names, as a property of JABElement.
    _ATTRIBUTE_PROPERTY = {
        By.NAME: "name",
        By.DESCRIPTION: "description",
        By.ROLE: "role",
        By.STATES: "states_en_us",
        By.OBJECT_DEPTH: "object_depth",
        By.CHILDREN_COUNT: "children_count",
        By.INDEX_IN_PARENT: "index_in_parent",
    }

    def _compare_attribute(
            self, name: str, comparison: str, value: str, jabelement: JABElement
    ) -> bool:
        """`@x <op> value` for an operator other than `=`.

        XPath compares two values as numbers when both are numbers and as strings
        otherwise, and this does the same: an attribute the element reports as an int
        is compared numerically, so `[@indexinparent > 9]` means what it looks like
        rather than putting "10" before "9". Anything else is compared as a string,
        which is what XPath does with strings -- `[@name < 'm']` is a lexicographic
        comparison, not an error.

        `!=` is inequality on the same terms, so `[@role != 'panel']` is the
        complement of `[@role = 'panel']` rather than a second way of writing it.
        """
        actual = getattr(jabelement, self._ATTRIBUTE_PROPERTY[name])
        expected = value.strip()
        if len(expected) >= 2 and expected[0] in "'\"" and expected[-1] == expected[0]:
            expected = expected[1:-1]

        if isinstance(actual, (list, tuple)):
            # states is a list; its natural string form is what `=` compares against.
            actual = ",".join(actual)

        if isinstance(actual, int) and not isinstance(actual, bool):
            try:
                expected_value = int(expected)
            except ValueError:
                raise JABException(
                    f"'{name}' is an integer on the element, and '{expected}' is not "
                    f"a number to compare it with"
                ) from None
            return {
                "!=": actual != expected_value,
                "<": actual < expected_value,
                "<=": actual <= expected_value,
                ">": actual > expected_value,
                ">=": actual >= expected_value,
            }[comparison]

        actual = str(actual)
        return {
            "!=": actual != expected,
            "<": actual < expected,
            "<=": actual <= expected,
            ">": actual > expected,
            ">=": actual >= expected,
        }[comparison]

    def _get_node_element(self, jabelement: JABElement = None) -> JABElement:
        """Get node JABElement.

        Args:
            jabelement (JABElement, optional): The JABElement. Defaults to None.

        Returns:
            JABElement: Node JABElement
        """
        jabelement = jabelement or JABElement(self.bridge, self.hwnd, self.vmid, self.accessible_context)
        is_same = self._is_same_object(
            self.accessible_context, jabelement.accessible_context
        )
        if not is_same:
            return jabelement
        top_object = self._get_top_level_object(self.accessible_context)
        is_top_level = self._is_same_object(self.accessible_context, top_object)
        if is_top_level:
            return jabelement
        # An absolute locator issued from a child element searches the whole
        # window, which is what XPath's '//' means. This used to substitute
        # self.parent, so a lookup from a child silently began one level up
        # (issue #54). Use a leading '.' for a search relative to this element.
        return JABElement(self.bridge, self.hwnd, self.vmid, top_object)

    def find_element_by_xpath(self, value: str, visible: bool = False) -> JABElement:
        """Find child JABElement by xpath

        Args:
            value (str): Locator of JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Example:
            find_element_by_xpath("//internal frame/panel")\n
            find_element_by_xpath("//*/panel")\n
            find_element_by_xpath("//internal frame[@name='FRM-999']")\n
            find_element_by_xpath("//internal frame[@name=contains('FRM-999')]")\n
            find_element_by_xpath("//internal frame[@states='enable,focusable,visible,showing']")\n
            find_element_by_xpath("//internal frame[@states=contains('enable,focusable')]")\n
            find_element_by_xpath("//internal frame[@objectdepth=7]")\n
            find_element_by_xpath("//internal frame[@childrencount=2]")\n
            find_element_by_xpath("//internal frame[@indexinparent=3]")\n
            find_element_by_xpath("//internal frame[@name=contains('FRM-999') and @objectdepth=7]")\n

        Returns:
            JABElement: The JABElement find by locator
        """
        # Reachable directly by callers, so it needs its own pump even though
        # find_element() also routes through here.
        self.win32_utils.pump_messages()

        branches = self.xpath_parser.split_union(value)
        if len(branches) > 1:
            # A union is a node-set, and this returns one element -- so the branches
            # are tried in the order they were written and the first match wins.
            # That is not the same as "first in document order", which is what XPath
            # would say, and it is documented rather than approximated silently.
            for branch in branches:
                try:
                    return self.find_element_by_xpath(branch, visible=visible)
                except JABException:
                    continue
            raise JABException(f"no JABElement found by xpath '{value}'")

        relative = value.startswith(".")
        nodes = self.xpath_parser.split_nodes(value[1:] if relative else value)
        root = self if relative else self._xpath_search_root()
        examined = []
        try:
            found = self._search_path(nodes, 0, root, visible, examined)
        finally:
            # The search may have created and abandoned any number of objects;
            # none of them belongs to the caller, so all of them go back here.
            for element in examined:
                self.release_jabelement(element)
            if not relative:
                # The top-level object came from a JAB call and is not the caller's
                # -- it leaked on every absolute lookup, success or failure, which
                # is one Java object per search for the life of the process. See
                # _xpath_search_root.
                self.release_jabelement(root)
        if found is not None:
            return found
        raise JABException(f"no JABElement found by xpath '{value}'")

    def _xpath_search_root(self) -> JABElement:
        """The element an absolute locator starts from.

        XPath reads ``//x`` as "any x in the document", so an absolute locator
        starts at the window's top-level accessible object. A locator beginning
        with ``.`` is relative and starts at this element instead -- which is
        what a caller searching under a subtree wants, and what issue #54 was
        asking for.
        """
        top_object = self._get_top_level_object()
        return JABElement(self.bridge, self.hwnd, self.vmid, top_object)

    def _search_path(
            self,
            nodes: list,
            index: int,
            parent: JABElement,
            visible: bool,
            examined: list,
            depth: int = 0,
            found: Optional[list] = None,
    ) -> Optional[JABElement]:
        """Walk ``nodes[index:]`` under *parent*, in one of two modes.

        *found* is None to return the first match, or a list to append every match to.
        Both modes prune the walk the same way and both answer for the same references;
        they differ only in whether a match ends the search. They were two functions
        until the ownership bookkeeping -- the part that is hard to get right -- was
        written out twice, which is how a leak gets in.

        The path prunes the walk: **the first node may match at any depth, and every
        node after it is a direct child of the previous match.** Once a node has
        matched, only its own subtree is considered rather than the whole tree again.
        When the rest of the path does not fit under a match, the search continues with
        the next candidate instead of giving up, which is what the implementation before
        1.4.0 did: it took the first role-and-attribute match and raised if the
        remainder of the path was not underneath it.

        Ownership, in both modes: anything that ends up in *found* belongs to the
        caller, and everything else created here is appended to *examined* and released
        by the caller once the whole search is over -- exactly one of the two, exactly
        once.

        That deferral is not laziness. A node matching the first path segment gets
        enumerated twice when the rest of the path does not fit under it -- once looking
        for the next segment, once looking for a deeper match of this one -- and
        releasing during the first pass would leave the second pass reading handles that
        are already gone. Java Access Bridge hands out a fresh reference on every call,
        so both passes are legal as long as every reference is released, and releasing
        them together at the end is what makes that true.

        Listing every match used to run through ``_get_elements_by_node``, a level-by-
        level traversal that tested every node for every path segment, so a path naming
        an early control cost the whole tree: 33 calls for ``find_element_by_xpath``
        against 1555 for the same locator, on a window with forty panels.
        """
        collecting = found is not None

        if depth >= MAX_SEARCH_DEPTH:
            # See MAX_SEARCH_DEPTH: the tree is not guaranteed to be one, and an
            # unbounded walk of a cyclic one is a hang rather than an error.
            self.logger.warning(
                "xpath lookup stopped at depth %s without a match; the "
                "accessibility tree at this point is deeper than MAX_SEARCH_DEPTH "
                "(%s), or it contains a cycle",
                depth,
                MAX_SEARCH_DEPTH,
            )
            return None

        info = self.xpath_parser.get_node_information(nodes[index])
        last = index == len(nodes) - 1
        role = info.get("role")

        if role == PARENT:
            # `..`, short for `parent::node()`: exactly one node, or none if the
            # context is already the top. It steps upwards rather than fanning out,
            # which is why it is handled here and not in the child loop further down.
            ancestor_context = self._get_accessible_parent_from_context(
                parent.accessible_context
            )
            if not ancestor_context:
                return None
            ancestor = JABElement(self.bridge, self.hwnd, self.vmid, ancestor_context)
            if last:
                if not collecting:
                    return ancestor
                found.append(ancestor)
                return None
            result = self._search_path(nodes, index + 1, ancestor, visible, examined,
                                       depth + 1, found)
            # The ancestor came from a JAB call and belongs to the search unless it is
            # the answer; see the ownership note above.
            examined.append(ancestor)
            return result

        predicates = info.get("predicates") or []

        # One counter per step, shared by every candidate this step is offered --
        # which is what makes a position mean "the nth candidate of this parent".
        # XPath counts within the node-set the previous predicates left behind, so a
        # candidate that fails an earlier predicate does not advance the count.
        position = [0]

        def matches(candidate) -> bool:
            if role not in ("*", candidate.role_en_us):
                return False
            for predicate in predicates:
                if "attributes" in predicate:
                    if not self._is_match_attributes(predicate["attributes"], candidate):
                        return False
                    continue
                # A bare position, 1-based. Counted here rather than in the caller so
                # that `[2][@name='x']` means "the second child, if it is named x" and
                # `[@name='x'][2]` means "the second of those named x" -- two different
                # questions that a flat attribute list cannot tell apart.
                position[0] += 1
                if position[0] != predicate["position"]:
                    return False
            return True

        if index > 0:
            # A step after the first means "direct child of the previous match".
            for child in self._generate_childs_from_element(
                    jabelement=parent, visible=visible
            ):
                if matches(child):
                    if last:
                        if not collecting:
                            return child
                        found.append(child)
                        # Recorded, so it is the caller's and not the search's.
                        continue
                    result = self._search_path(nodes, index + 1, child, visible,
                                               examined, depth + 1, found)
                    if result is not None:
                        examined.append(child)
                        return result
                examined.append(child)
            return None

        # The first step may match at any depth, and when collecting, more than once.
        for child in self._generate_childs_from_element(
                jabelement=parent, visible=visible
        ):
            recorded = False
            if matches(child):
                if last:
                    if not collecting:
                        return child
                    found.append(child)
                    recorded = True
                else:
                    result = self._search_path(nodes, 1, child, visible, examined,
                                               depth + 1, found)
                    if result is not None:
                        examined.append(child)
                        return result
            # Match or not, this node may have descendants that match the first
            # segment -- `//label` matches at every depth, not only the shallowest.
            result = self._search_path(nodes, 0, child, visible, examined,
                                       depth + 1, found)
            if result is not None:
                examined.append(child)
                return result
            if not recorded:
                examined.append(child)
        return None

    def find_element(
            self, by: str = By.NAME, value: Any = None, visible: bool = False
    ) -> JABElement:
        """Find a jab element given a By strategy and locator.

        Args:
            by (str, optional): By strategy of element need to find. Defaults to By.NAME.
            value (Any, optional): Locator of element need to find.
            Defaults to None will select the first child jab element.
            visible (bool, optional): The switch for find only visible child jab element or not.
            Defaults to False to find available child element.

        Returns:
            JABElement: The element find by locator
        """
        # Every find_element_by_* delegates here, so pumping once at this entry
        # covers the whole lookup API. Without it, pyjab never serviced COM
        # after the first window was found, which is why a window or dialog
        # that opened later was invisible (issues #56, #74).
        self.win32_utils.pump_messages()
        if by not in [
            By.NAME,
            By.DESCRIPTION,
            By.ROLE,
            By.STATES,
            By.OBJECT_DEPTH,
            By.CHILDREN_COUNT,
            By.INDEX_IN_PARENT,
            By.XPATH,
        ]:
            raise JABException(f"incorrect by strategy '{by}'")
        if by == By.XPATH:
            return self.find_element_by_xpath(value=value, visible=visible)
        found = self._search_element(
            self,
            lambda element: self._is_element_matched(
                by=by, value=value, jabelement=element
            ),
            visible=visible,
        )
        if found is not None:
            return found
        raise JABException(
            f"jab element not found by '{by}' with locator '{value}'"
        )

    def find_elements_by_name_pattern(
        self, pattern: str, visible: bool = False, ignorecase: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by name pattern

        Args:
            pattern (str): A regex pattern.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement found by locator
        """
        jabelements = []
        re_flag = re.IGNORECASE if ignorecase else 0
        for jabelement in self._generate_all_childs(visible=visible):
            if re.search(pattern, jabelement.name, flags=re_flag):
                jabelements.append(jabelement)
                continue
            self.release_jabelement(jabelement)
        if not jabelements:
            raise JABException(
                f"no JABElement found by 'NAME' with pattern '{pattern}'"
            )
        return jabelements
    
    def find_element_by_name_pattern(
        self, pattern: str, visible: bool = False, ignorecase: bool = False
    ) -> JABElement:
        """Find JABElement by name pattern

        Args:
            pattern (str): A regex pattern.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            JABElement: JABElement found by locator
        """
        re_flag = re.IGNORECASE if ignorecase else 0
        for jabelement in self._generate_all_childs(visible=visible):
            if re.search(pattern, jabelement.name, flags=re_flag):
                return jabelement
            self.release_jabelement(jabelement)
        raise JABException(
            f"no JABElement found by 'NAME' with pattern '{pattern}'"
        )
    
    def find_elements_by_name(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by name

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.NAME, value=value, visible=visible)

    def find_elements_by_description(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by description

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.DESCRIPTION, value=value, visible=visible)

    def find_elements_by_role(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by role

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.ROLE, value=value, visible=visible)

    def find_elements_by_states(
            self, value: Union[list, str], visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by states

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.STATES, value=value, visible=visible)

    def find_elements_by_object_depth(
            self, value: int, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by object depth

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.OBJECT_DEPTH, value=value, visible=visible)

    def find_elements_by_children_count(
            self, value: int, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by children count

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.CHILDREN_COUNT, value=value, visible=visible)

    def find_elements_by_index_in_parent(
            self, value: int, visible: bool = False
    ) -> list[JABElement]:
        """Find list of child JABElement by index inparent

        Args:
            value (str): Locator of list JABElement need to find.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list[JABElement]: List of JABElement find by locator
        """
        return self.find_elements(by=By.INDEX_IN_PARENT, value=value, visible=visible)

    def find_elements_by_xpath(
            self, value: str, visible: bool = False
    ) -> list[JABElement]:
        """Every JABElement under this one matching an xpath.

        Args:
            value (str): Locator of the JABElements to find.
            visible (bool, optional): Search only children that are on screen.
                Defaults to False, which searches all of them.

        Returns:
            list[JABElement]: every match.  The caller owns these; pass each to
            :meth:`release_jabelement` when finished with it.

        Raises:
            JABException: nothing matched.  **This is the same contract as the rest
                of the family** -- ``find_elements()``, ``find_elements_by_role()``
                and the others all raise rather than returning an empty list, and
                :meth:`get_children` is the deliberate exception, documented as one.
                This method used to be neither: it raised when the *first* path
                segment failed and returned ``[]`` when a later one did, so the
                answer depended on the length of the locator.
        """
        # See find_elements(): reachable directly by callers.
        self.win32_utils.pump_messages()

        branches = self.xpath_parser.split_union(value)
        if len(branches) > 1:
            merged: list = []
            for branch in branches:
                try:
                    merged.extend(self.find_elements_by_xpath(branch, visible=visible))
                except JABException:
                    continue
            if not merged:
                raise JABException(f"no JABElement found by xpath '{value}'")
            return self._without_duplicates(merged)

        relative = value.startswith(".")
        nodes = self.xpath_parser.split_nodes(value[1:] if relative else value)
        root = self if relative else self._xpath_search_root()
        examined = []
        found = []
        try:
            self._search_path(nodes, 0, root, visible, examined, found=found)
        finally:
            # Everything the walk created and did not keep belongs to the search,
            # not to the caller -- see _search_path.
            for element in examined:
                self.release_jabelement(element)
            if not relative:
                # See find_element_by_xpath: the top-level object is not the
                # caller's and used to leak on every absolute lookup.
                self.release_jabelement(root)
        if not found:
            raise JABException(f"no JABElement found by xpath '{value}'")
        return self._without_duplicates(found)

    def find_elements(
            self, by: str = By.NAME, value: Union[list, str, int] = None, visible: bool = False
    ) -> list[JABElement]:
        """Find list of JABElement given a By strategy and locator.

        Args:
            by (str, optional): By strategy of element need to find. Defaults to By.NAME.
            value (Any, optional): Locator of element need to find.
            Defaults to None will select the first child jab element.
            visible (bool, optional): The switch for find only visible child jab elements or not.
            Defaults to False to find all child elements.

        Returns:
            list: List of JABElement find by locator
        """
        # See find_element(): this is the other choke point every
        # find_elements_by_* funnels through.
        self.win32_utils.pump_messages()
        if by not in [
            By.NAME,
            By.DESCRIPTION,
            By.ROLE,
            By.STATES,
            By.OBJECT_DEPTH,
            By.CHILDREN_COUNT,
            By.INDEX_IN_PARENT,
            By.XPATH,
        ]:
            raise JABException(f"incorrect by strategy '{by}'")
        if by == By.XPATH:
            return self.find_elements_by_xpath(value=value, visible=visible)
        jabelements = []
        for jabelement in self._generate_all_childs(visible=visible):
            if self._is_element_matched(by=by, value=value, jabelement=jabelement):
                jabelements.append(jabelement)
                continue
            self.release_jabelement(jabelement)
        if not jabelements:
            raise JABException(
                f"no JABElement found by '{by}' with locator '{value}'"
            )
        return jabelements

    @staticmethod
    def _states_as_set(value) -> set:
        """Normalise a states locator to a set of state names.

        ``find_element_by_states`` documents that it accepts a ``str`` as well as
        a list, but ``set("enabled")`` is a set of *characters*, so a string
        could never match anything. A comma-separated string is the natural
        spelling -- it is what ``states`` and ``states_en_us`` hold before they
        are split.
        """
        if isinstance(value, str):
            value = [state.strip() for state in value.split(",") if state.strip()]
        return set(value)

    @staticmethod
    def _is_element_matched(jabelement: JABElement, by: str, value: Optional[str]):
        return any(
            [
                value is None,
                by == By.NAME and jabelement.name == value,
                by == By.ROLE and jabelement.role == value,
                by == By.DESCRIPTION and jabelement.description == value,
                by == By.STATES
                and set(jabelement.states_en_us) == JABElement._states_as_set(value),
                by == By.OBJECT_DEPTH
                and jabelement.object_depth == int(value),
                by == By.CHILDREN_COUNT
                and jabelement.children_count == int(value),
                by == By.INDEX_IN_PARENT
                and jabelement.index_in_parent == int(value),
            ]
        )

    @property
    def size(self) -> dict:
        """The size of the element."""
        return dict(height=self.bounds.get("height"), width=self.bounds.get("width"))

    @property
    def location(self) -> dict:
        """The location of the element in the renderable canvas."""
        return dict(x=self.bounds.get("x"), y=self.bounds.get("y"))

    def get_screenshot_as_file(self, filename: str) -> None:
        """Write a PNG of this element to ``filename``.

        Args:
            filename (str): where to write it, as a full path ending in ``.png``.
                A relative path is relative to the working directory, which is
                rarely what a test wants.

        Returns:
            None.  Raises OSError if the file cannot be written; there is no
            True/False to check.

        The bytes are the same ones :meth:`get_screenshot_as_png` returns, so a
        caller who wants them in hand rather than on disk should ask for those.
        """
        with open(filename, "wb") as handle:
            handle.write(self.get_screenshot_as_png())

    def get_screenshot(self):
        """A Pillow ``Image`` of the screenshot.

        .. deprecated:: 1.9.0
            Pillow is no longer a dependency of pyjab, so this method only works when it
            is installed separately, and it is **removed in 2.0.0**.

            Use :meth:`get_screenshot_as_png` and an image library of your own:

            .. code-block:: python

                from io import BytesIO
                from PIL import Image

                image = Image.open(BytesIO(driver.get_screenshot_as_png()))

            That is the same pixels with one line on your side, and it puts the imaging
            dependency where it belongs -- yours to choose, and yours to keep up to date.

        Returns:
            PIL.Image.Image: the screenshot.

        Raises:
            ImportError: Pillow is not installed, with what to do about it.
        """
        warnings.warn(
            "get_screenshot() returns a Pillow Image and is removed in 2.0.0. Use "
            "get_screenshot_as_png() -- Image.open(BytesIO(png)) is the same thing "
            "without making Pillow pyjab's dependency. Install pyjab[pillow] to keep "
            "this working until then.",
            DeprecationWarning,
            stacklevel=2,
        )
        try:
            from PIL import Image
        except ImportError as error:                 # pragma: no cover - env dependent
            raise ImportError(
                "get_screenshot() needs Pillow, which pyjab no longer installs. Either "
                "install it with `pip install pyjab[pillow]`, or use "
                "get_screenshot_as_png() and an image library of your choice -- "
                "Image.open(BytesIO(png)) is one line."
            ) from error

        return Image.open(BytesIO(self.get_screenshot_as_png()))

    @property
    def parent(self):
        """The accessible parent of this element, as a :class:`JABElement`.

        Not the driver: an element does not hold one.  This walks up the
        accessibility tree, so the parent is one object closer to the window, and
        calling it repeatedly walks up rather than out.

        The reference JAB hands out must be released -- see
        :meth:`release_jabelement`.
        """
        parent_acc = self._get_accessible_parent_from_context()
        return JABElement(
            bridge=self.bridge,
            hwnd=self.hwnd,
            vmid=self.vmid,
            accessible_context=parent_acc,
        )

    def get_cell(self, row: int, column: int, visible: bool = False) -> JABElement:
        """Get cell JABElement from table

        Args:
            row (int): Row index of cell, start from 0.
            column (int): Column index of cell, start from 0.
            visible (bool, optional): The switch for find only visible cell element or not.
            Defaults to False to find available cell element.

        Raises:
            JABException: Raise JABException if JAB internal function error

        Returns:
            JABElement: Return specific cell JABElement
        """
        if self.role_en_us != "table":
            raise JABException("JABElement is not table, does not support this func")
        info = self._get_accessible_table_cell_info(row, column)
        index = info.index
        accessible_context = info.accessibleContext
        if visible:
            info = self._get_visible_children()
            accessible_context = info.children[index]
        return JABElement(self.bridge, self.hwnd, self.vmid, accessible_context)

    # --- AccessibleTable selection, public -------------------------------
    #
    # Why these exist rather than a single `select(name)`: what you select in a
    # table is a position, not a name.  And why they are worth having at all:
    # get_cell() returns the cell from the table's own cell list, which many Java
    # tables report with bounds of -1 -- so the element is real but cannot be
    # clicked.  The cells reached through the selection are the ones the
    # application responds to (#57, #61).

    def _require_table(self, action: str) -> None:
        """Refuse table-only calls on anything else, by name."""
        if self.role_en_us != Role.TABLE:
            raise JABException(
                f"{action}() needs a table; this element is a "
                f"'{self.role_en_us}'"
            )

    @property
    def selected_rows(self) -> list:
        """Zero-based indices of the selected rows. Empty when none are."""
        self._require_table("selected_rows")
        return self._get_accessible_table_row_selections()

    @property
    def selected_columns(self) -> list:
        """Zero-based indices of the selected columns. Empty when none are."""
        self._require_table("selected_columns")
        return self._get_accessible_table_column_selections()

    @property
    def selected_row_count(self) -> int:
        """How many rows the table reports as selected."""
        self._require_table("selected_row_count")
        return self._get_accessible_table_row_selection_count()

    @property
    def selected_column_count(self) -> int:
        """How many columns the table reports as selected."""
        self._require_table("selected_column_count")
        return self._get_accessible_table_column_selection_count()

    def is_row_selected(self, row: int) -> bool:
        """Whether one row is selected, without reading the whole selection.

        Args:
            row (int): zero-based row index.
        """
        self._require_table("is_row_selected")
        return self._is_accessible_table_row_selected(row)

    def is_column_selected(self, column: int) -> bool:
        """Whether one column is selected.

        Args:
            column (int): zero-based column index.
        """
        self._require_table("is_column_selected")
        return self._is_accessible_table_column_selected(column)

    def get_selected_elements(self) -> list:
        """Every selected child, as a list of :class:`JABElement`.

        The table's selection holds the cells the application is actually
        presenting as selected -- the "Select Cells" the issues asked for.  For a
        list or a combo box this is the selected item(s), so it is not table-only.

        Returns:
            list: :class:`JABElement` objects.  **Release each one** with
            :meth:`release_jabelement` when finished, as with any object JAB hands
            out -- see the note there.

        Note:
            An empty list means nothing is selected, which is the ordinary state
            of a freshly-opened component rather than an error.
        """
        count = self._get_accessible_selection_count_from_context()
        elements = []
        for index in range(count):
            accessible_context = self._get_accessible_selection_from_context_index(
                index
            )
            if not accessible_context:
                # JAB handed back nothing for this slot; skip rather than build an
                # element around a null handle, which would fail later and
                # somewhere else.
                continue
            elements.append(
                JABElement(
                    bridge=self.bridge,
                    hwnd=self.hwnd,
                    vmid=self.vmid,
                    accessible_context=accessible_context,
                )
            )
        return elements

    def get_selected_element(self) -> JABElement:
        """The first selected child, as a :class:`JABElement`.

        Kept for compatibility.  Prefer :meth:`get_selected_elements`, which can
        tell "nothing is selected" apart from "the first selected thing" -- this
        one returns an element wrapping a null handle when the selection is empty.

        Returns:
            JABElement: the first selected element.
        """
        selected_acc = self._get_accessible_selection_from_context(
            self.accessible_context
        )
        return JABElement(
            bridge=self.bridge,
            hwnd=self.hwnd,
            vmid=self.vmid,
            accessible_context=selected_acc,
        )

    def select_cell(self, row: int, column: int, clear: bool = True) -> None:
        """Select the cell at (row, column).

        The cell is reached through the table's accessible selection, which is the
        only route JAB offers and the one the application reacts to.  If you need
        the resulting element rather than the selection, follow this with
        :meth:`get_selected_elements`.

        Args:
            row (int): zero-based row index.
            column (int): zero-based column index.
            clear (bool, optional): clear the existing selection first, so this
                cell ends up the only one selected. Defaults to True; pass False
                to extend a multi-selection.

        Raises:
            JABException: not a table, or the index could not be resolved.
        """
        self._require_table("select_cell")
        if clear:
            self._clear_accessible_selection_from_context(self.accessible_context)
        index = self._get_accessible_table_index(row, column)
        if index < 0:
            raise JABException(
                f"table has no cell at row {row}, column {column}"
            )
        self._select_accessible_table_index(index)

    def select_row(self, row: int, clear: bool = True) -> None:
        """Select every cell in one row.

        There is no JAB call that selects a row, so the row is selected by adding
        its cells to the table's selection -- but adding a cell is a **toggle**, so
        the cells that are already selected are skipped rather than added again.
        On a Swing table in its default row-selection mode the first cell selects
        the whole row, and the rest are then found to be selected already; on a
        cell-selection table every cell is added, as before.

        Whether the application reports the *row* as selected is still up to its
        implementation -- check :attr:`selected_rows` afterwards rather than
        assuming.

        Args:
            row (int): zero-based row index.
            clear (bool, optional): clear the existing selection first. Defaults
                to True.  With ``clear=False``, cells already selected are left
                alone instead of being toggled off.
        """
        self._require_table("select_row")
        if clear:
            self._clear_accessible_selection_from_context(self.accessible_context)
        for column in range(self._get_accessible_table_info().columnCount):
            index = self._get_accessible_table_index(row, column)
            if index >= 0 and not self._is_accessible_child_selected(index):
                self._select_accessible_table_index(index)

    def select_column(self, column: int, clear: bool = True) -> None:
        """Select every cell in one column. See :meth:`select_row`."""
        self._require_table("select_column")
        if clear:
            self._clear_accessible_selection_from_context(self.accessible_context)
        for row in range(self._get_accessible_table_info().rowCount):
            index = self._get_accessible_table_index(row, column)
            if index >= 0 and not self._is_accessible_child_selected(index):
                self._select_accessible_table_index(index)

    def clear_selection(self) -> None:
        """Clear the table's selection."""
        self._require_table("clear_selection")
        self._clear_accessible_selection_from_context(self.accessible_context)

    def select_all(self) -> None:
        """Ask the table to select everything it can.

        On a Swing ``JTable`` the bridge's own call does **nothing unless cell
        selection is enabled**: ``AccessibleJTable.selectAllAccessibleSelection()``
        is ``if (cellSelectionEnabled) { selectAll(); }`` and falls through
        otherwise.  A default table is in row-selection mode, so that call is a
        no-op which raises nothing.

        So what it did is read back, and when nothing was selected the table is
        walked instead: every cell that is not already selected is added, which
        selects every row, every column, or every cell, whichever the table allows.
        Reading the result costs one call on the path where the bridge's own call
        worked.

        There is no ``clear`` argument, so a table that already had a selection
        keeps it and gains the rest.
        """
        self._require_table("select_all")
        self.bridge.selectAllAccessibleSelectionFromContext(
            self.vmid, self.accessible_context
        )
        if self._get_accessible_selection_count_from_context():
            return
        info = self._get_accessible_table_info()
        for row in range(info.rowCount):
            for column in range(info.columnCount):
                index = self._get_accessible_table_index(row, column)
                if index >= 0 and not self._is_accessible_child_selected(index):
                    self._select_accessible_table_index(index)

    def get_visible_children(self) -> list:
        """The children currently on screen, as :class:`JABElement` objects.

        A large table only has the rows that are visible in the accessibility
        tree: the rest have no handles to read.  That is why the count here is
        ``getVisibleChildren``'s own answer and not ``row_count * column_count``
        -- indexing past what actually came back is what crashes the target
        application, which is the report in #59.

        Returns:
            list: :class:`JABElement` objects.  **Release each one** with
            :meth:`release_jabelement` when finished, as with any object JAB hands
            out.

        Note:
            This is the supported form of what the troubleshooting page used to
            reach for as ``table._get_visible_children()``, which is private and
            can change without notice.
        """
        info = self._get_visible_children()
        count = info.returnedChildrenCount
        children = []
        for index in range(count):
            handle = info.children[index]
            if not handle:
                continue
            children.append(
                JABElement(
                    bridge=self.bridge,
                    hwnd=self.hwnd,
                    vmid=self.vmid,
                    accessible_context=handle,
                )
            )
        return children

    def get_screenshot_as_png(self) -> bytes:
        """The screenshot as PNG data, the way Selenium returns it.

        This is what :meth:`get_screenshot_as_base64` encodes, and what
        :meth:`get_screenshot_as_file` writes.  Use :meth:`get_screenshot` when
        you want the Pillow ``Image`` itself.

        Returns:
            bytes: a complete PNG file, magic number and all.
        """
        bounds = self.root_element.bounds if hasattr(self, "root_element") else self.bounds
        x, y = bounds["x"], bounds["y"]
        width, height = bounds["width"], bounds["height"]
        win32 = self.win32utils if hasattr(self, "win32utils") else self.win32_utils
        return bgra_to_png(win32.grab_rect(x, y, width, height), width, height)

    def get_screenshot_as_base64(self) -> str:
        """The screenshot as a base64-encoded PNG, for embedding in HTML or JSON.

        Returns:
            str: the same bytes :meth:`get_screenshot_as_png` returns, base64
            encoded as ASCII.
        """
        return base64.b64encode(self.get_screenshot_as_png()).decode("ascii")

    def get_element_information(self) -> dict:
        """Get dict information of current JABElement.

        Notice:
            This dict of component value will NOT update after property changes.

        Returns:
            dict: Dict information of current JABElement
        """
        info = {
            "name": self.name,
            "description": self.description,
            "role": self.role,
            "role_en_us": self.role_en_us,
            "states": self.states,
            "states_en_us": self.states_en_us,
            "bounds": self.bounds,
            "object_depth": self.object_depth,
            "index_in_parent": self.index_in_parent,
            "children_count": self.children_count,
            "accessible_component": self.accessible_component,
            "accessible_action": self.accessible_action,
            "accessible_selection": self.accessible_selection,
            "accessible_text": self.accessible_text,
        }
        if self.accessible_text:
            info["text"] = self.text
        if self.role_en_us == Role.TABLE:
            info["table"] = self.table
        return info

    @staticmethod
    def _poll(actual_value):
        """Read a polled value: call it if it is a callable, otherwise use it.

        The wait helpers take a *callable* so that each iteration re-reads the
        property under test. They previously took an already-evaluated value,
        which meant the comparison result could never change -- the loop was a
        CPU spin until it timed out, and could not have succeeded.
        """
        return actual_value() if callable(actual_value) else actual_value

    @staticmethod
    def _wait_for_value_to_be(expected_value, actual_value, timeout: int = 5,
                              error_msg_function: str = None,
                              poll_interval: float = ELEMENT_POLL_INTERVAL):
        start = monotonic()
        while True:
            current_value = JABElement._poll(actual_value)
            if (
                    expected_value
                    and current_value == expected_value
                    or not expected_value
                    and not current_value
            ):
                return
            if monotonic() - start >= timeout:
                if error_msg_function:
                    _error_msg = f"Failed to {error_msg_function} in '{timeout}' seconds"
                else:
                    _error_msg = f"Failed to wait for expected value '{expected_value}' in '{timeout}' seconds"
                raise TimeoutError(_error_msg)
            sleep(poll_interval)

    @staticmethod
    def _wait_for_value_to_contain(expected_values: Union[str, list[str]], actual_values, timeout: int = 5,
                                   error_msg_function: str = None,
                                   poll_interval: float = ELEMENT_POLL_INTERVAL):
        start = monotonic()
        while True:
            current_values = JABElement._poll(actual_values) or []
            if any(v in expected_values for v in current_values):
                return
            if monotonic() - start >= timeout:
                if error_msg_function:
                    _error_msg = f"Failed to {error_msg_function} in '{timeout}' seconds"
                else:
                    _expected_values = ", ".join(expected_values)
                    _error_msg = f"Failed to wait for expected values '{_expected_values}' in '{timeout}' seconds"
                raise TimeoutError(_error_msg)
            sleep(poll_interval)

class JABTree:
    """An iteration over a subtree, which knows whether it finished.

    Yields ``(depth, record)`` from :meth:`JABElement.walk`. Records are plain dicts and
    every JAB reference taken during the walk is released as the walk advances, so nothing
    the caller sees has a lifetime to manage.

    The reason this is an object rather than a generator is the three attributes below.
    **A truncated walk and a complete one produce the same records**, and the difference
    is the whole question a caller is asking: "is the tree like this, or did I stop
    reading?" A caller that cannot tell them apart will act on half a window and believe
    it saw the whole thing.

    Attributes:
        truncated (bool): True if any limit stopped the walk before the subtree was
            exhausted. This is the one to check.
        limit_hit (bool): True if *limit* was reached.
        max_depth_hit (bool): True if a node was not descended into because of
            *max_depth*. Note that reaching *max_depth* is not itself truncation -- a walk
            asked for two levels and given two levels did what it was asked.
    """

    def __init__(self, element, max_depth: Optional[int] = None,
                 limit: Optional[int] = None) -> None:
        self._element = element
        self._max_depth = max_depth
        self._limit = limit
        self.limit_hit = False
        self.max_depth_hit = False
        self.count = 0

    #: True if a limit stopped the walk. This is the attribute to check.
    @property
    def truncated(self) -> bool:
        return self.limit_hit

    def __len__(self) -> int:
        """Records produced so far -- only meaningful after iterating."""
        return self.count

    def __iter__(self):
        if self._max_depth is not None and self._max_depth < 0:
            return

        def descend(node, depth):
            # _generate_childs_from_element, not get_children: the latter materialises
            # every child and each carries a reference. A walk that stops early has then
            # taken references to children it will never reach, and nothing releases them
            # -- the caller asked for the first two of twenty and leaked eighteen. The
            # generator asks for one child at a time, so an abandoned walk has taken only
            # what it released in the finally below.
            for child in node._generate_childs_from_element(jabelement=node):
                try:
                    if self._limit is not None and self.count >= self._limit:
                        # Set on the object, not returned from this frame: `return` here
                        # ends this frame only, and the parent's loop would carry on
                        # calling back in. The check at the top of the loop is what
                        # actually stops the walk.
                        self.limit_hit = True
                        return
                    self.count += 1
                    yield depth, child.as_record()
                    if self._max_depth is None or depth < self._max_depth:
                        yield from descend(child, depth + 1)
                    else:
                        self.max_depth_hit = True
                finally:
                    # Released here rather than collected and released at the end, because
                    # a walk can be abandoned part-way -- the caller may stop iterating,
                    # and a generator that is closed does not run code after the yield
                    # unless it is in a finally.
                    node.release_jabelement(child)

        yield from descend(self._element, 0)
