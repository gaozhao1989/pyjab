"""Regression tests for previously fixed bugs.

These used to drive the Java Control Panel, which only exists in a JDK 8 install
and lives at a hardcoded path.  They now drive the Swing application in
``tests/java``, which the ``test_app`` fixture compiles and launches.
"""

import pytest

pytestmark = pytest.mark.gui


class TestBugFix(object):
    def test_fix_same_title(self, test_app) -> None:
        """A driver can be created for a window whose title is not unique."""
        assert test_app.hwnd

    def test_fix_jab_init(self, test_app) -> None:
        """JAB initialisation resolves the root element and its children."""
        label = test_app.find_element_by_name("A Label")

        assert label
        assert label.role

    def test_multiple_key_press(self, test_app) -> None:
        """A modifier + key chord must not wedge the application.

        The original bug left the target unresponsive, so the assertion is that
        the window is still queryable afterwards.
        """
        test_app.find_element_by_name("A Label").click(simulate=True)
        test_app._press_hold_release_key("tab", "shift")

        assert test_app.find_element_by_role("push button")
