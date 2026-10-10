"""`accessible_interfaces` answered `False` for every element (#207).

It was `return False` with a `TODO` above it, while its three siblings read the real value
from the accessibility context info. The tests here pin the contract that was missing, so
that the next person to write `return False` has to delete a test to do it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _win32stubs  # noqa: F401

JABElement = _win32stubs.import_jabelement()


def element_with(**flags):
    """An element whose context info reports exactly *flags*.

    `_acc_info` is **bound to the instance at construction**, not defined on the class --
    `tests/test_element_logic.py` says so and does the same thing, and patches the instance
    for that reason. `patch.object(JABElement, "_acc_info", ...)` raises `AttributeError`:
    the class does not have that attribute at all.
    """
    element = JABElement.__new__(JABElement)
    element._acc_info = lambda: SimpleNamespace(
        accessibleComponent=flags.get("component", True),
        accessibleAction=flags.get("action", False),
        accessibleSelection=flags.get("selection", False),
        accessibleText=flags.get("text", False),
        accessibleValue=flags.get("value", False),
    )
    return element


@pytest.mark.parametrize("flag", ["text", "action", "selection", "value"])
def test_any_one_interface_makes_it_true(flag):
    element = element_with(**{flag: True})
    assert element.accessible_interfaces is True


def test_none_of_them_is_false_rather_than_always_false():
    """A painted panel has none of the four. This is the case that must not be lost."""
    element = element_with()
    assert element.accessible_interfaces is False


def test_the_component_interface_alone_is_not_enough():
    """`accessibleComponent` is what every element has.

    If it counted, this property could never answer `False` -- the same defect as
    `return False`, pointed the other way.
    """
    element = element_with(component=True)
    assert element.accessible_interfaces is False


def test_it_is_not_the_old_constant():
    """The regression guard: the old implementation returned False unconditionally."""
    element = element_with(text=True)
    assert element.accessible_interfaces is True, "still answering False for everything"
