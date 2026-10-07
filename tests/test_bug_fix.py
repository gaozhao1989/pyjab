"""Regression tests for previously fixed bugs.

These drive the Java Control Panel, which ships with JDK 8 as
``<JAVA_HOME>\\jre\\bin\\javacpl.exe``.
"""

import pytest

pytestmark = pytest.mark.gui


class TestBugFix(object):
    def test_fix_same_title(self, java_control_app) -> None:
        """A driver can be created for a window whose title is not unique."""
        assert java_control_app.hwnd

    def test_fix_jab_init(self, java_control_app) -> None:
        """JAB initialisation resolves the root element and its children."""
        tab_general = java_control_app.find_element_by_name("General")

        assert tab_general
        assert tab_general.role

    def test_multiple_key_press(self, java_control_app) -> None:
        """A modifier + key chord must not wedge the application.

        The original bug left the target unresponsive, so the assertion is that
        the window is still queryable afterwards.
        """
        java_control_app.find_element_by_name("General").click(simulate=True)
        java_control_app._press_hold_release_key("tab", "shift")

        assert java_control_app.find_element_by_role("page tab")
