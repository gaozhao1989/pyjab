"""The widget API, exercised against a real Swing application.

This module used to drive 27 Oracle demo applets downloaded from
docs.oracle.com.  That made the suite depend on a third party staying online, on
applets continuing to be served, and on the exact widget names inside somebody
else's demos.  The application is now in ``tests/java/PyjabTestApp.java``, is
compiled on demand by the ``test_app`` fixture, and its component names are part
of this repository.

Where an interaction has two paths -- the accessible action and simulated mouse
or keyboard input -- both are covered, because they fail differently.

Dialogs are separate top-level windows, so they are reached through a second
``JABDriver`` bound to the dialog's own title.  Those drivers are deliberately
*not* context managers: ``__exit__`` terminates the bound process by pid, and a
dialog belongs to the same JVM as the main window, so exiting one would kill the
application the ``test_app`` fixture is still using.
"""

import pytest

from pyjab.common.logger import Logger
from pyjab.common.role import Role
from pyjab.common.states import States
from pyjab.jabdriver import JABDriver

pytestmark = pytest.mark.gui


class TestComponents(object):
    logger = Logger("TestComponents")

    @staticmethod
    def open_dialog(test_app, button_name: str, dialog_title: str) -> JABDriver:
        """Click a button that opens a dialog and bind to that dialog."""
        test_app.find_element_by_name(button_name).click()
        return JABDriver(title=dialog_title, timeout=30)

    # ---------------------------------------------------------------- window

    def test_frame(self, test_app: JABDriver):
        frame = test_app.find_element_by_role(Role.FRAME)
        assert frame
        self.logger.info(frame.get_element_information())

    def test_root_pane(self, test_app: JABDriver):
        root_pane = test_app.find_element_by_role(Role.ROOT_PANE)
        assert root_pane
        self.logger.info(root_pane.get_element_information())

    def test_layered_pane(self, test_app: JABDriver):
        layered_pane = test_app.find_element_by_role(Role.LAYERED_PANE)
        assert layered_pane
        self.logger.info(layered_pane.get_element_information())

    def test_panel(self, test_app: JABDriver):
        panel = test_app.find_element_by_role(Role.PANEL)
        assert panel
        self.logger.info(panel.get_element_information())

    def test_label(self, test_app: JABDriver):
        label = test_app.find_element_by_name("A Label")
        assert label
        assert label.role_en_us == Role.LABEL
        self.logger.info(label.get_element_information())

    def test_internal_frame(self, test_app: JABDriver):
        internal_frame = test_app.find_element_by_role(Role.INTERNAL_FRAME)
        assert internal_frame
        self.logger.info(internal_frame.get_element_information())

    def test_split_pane(self, test_app: JABDriver):
        split_pane = test_app.find_element_by_role(Role.SPLIT_PANE)
        assert split_pane
        self.logger.info(split_pane.get_element_information())

    def test_tool_bar(self, test_app: JABDriver):
        tool_bar = test_app.find_element_by_role(Role.TOOL_BAR)
        assert tool_bar
        self.logger.info(tool_bar.get_element_information())

    def test_progress_bar(self, test_app: JABDriver):
        progress_bar = test_app.find_element_by_role(Role.PROGRESS_BAR)
        assert progress_bar
        self.logger.info(progress_bar.get_element_information())

    # ---------------------------------------------------------------- scrolling

    def test_scroll_pane(self, test_app: JABDriver):
        scroll_pane = test_app.find_element_by_xpath("//scroll pane")
        assert scroll_pane
        self.logger.info(scroll_pane.get_element_information())

    def test_viewport(self, test_app: JABDriver):
        viewport = test_app.find_element_by_role(Role.VIEW_PORT)
        assert viewport
        self.logger.info(viewport.get_element_information())

    def test_scroll_bar(self, test_app: JABDriver):
        vertical = test_app.find_element_by_xpath(
            "//scroll bar[@states=contains('vertical')]"
        )
        assert vertical
        vertical.scroll(to_bottom=True)
        vertical.scroll(to_bottom=False)

    # ---------------------------------------------------------------- buttons

    def test_push_button(self, test_app: JABDriver):
        """One button controls another's enabled state, both ways.

        The assertion is on the change rather than on the state it starts in,
        because one application now serves every test and a test that only makes
        sense against a pristine window cannot be re-run on its own.
        """
        disable = test_app.find_element_by_name("Disable middle button")
        middle = test_app.find_element_by_name("Middle button")
        enable = test_app.find_element_by_name("Enable middle button")

        disable.click()
        assert not middle.is_enabled(), "the disable button did not disable it"

        enable.click(simulate=True)
        assert middle.is_enabled(), "the enable button did not re-enable it"

    def test_checkbox(self, test_app: JABDriver):
        assert test_app.find_element_by_role(Role.CHECK_BOX)

        chin = test_app.find_element_by_name("Chin")
        hair = test_app.find_element_by_name("Hair")

        was_checked = chin.is_checked()
        chin.click()
        assert chin.is_checked() != was_checked, "clicking did not toggle it"
        chin.click(simulate=True)
        assert chin.is_checked() == was_checked, "clicking again did not toggle back"

        was_checked = hair.is_checked()
        hair.click(simulate=True)
        assert hair.is_checked() != was_checked

    def test_radio_button(self, test_app: JABDriver):
        cat = test_app.find_element_by_name("Cat")
        dog = test_app.find_element_by_name("Dog")

        dog.click()
        assert dog.is_checked()
        assert not cat.is_checked(), "selecting one did not clear the other"

        cat.click(simulate=True)
        assert cat.is_checked()
        assert not dog.is_checked()

    # ---------------------------------------------------------------- selection

    def test_combo_box(self, test_app: JABDriver):
        combo_box = test_app.find_element_by_name("Animals combo box")
        assert combo_box.role_en_us == Role.COMBO_BOX

        combo_box.select(option="Cat")
        assert combo_box.get_selected_element().name == "Cat"

        combo_box.select(option="Rabbit", simulate=True)
        assert combo_box.get_selected_element().name == "Rabbit"

    def test_list(self, test_app: JABDriver):
        names = test_app.find_element_by_name("Names list")
        assert names.role_en_us == Role.LIST

        names.select("John Smith")
        assert names.get_selected_element().name == "John Smith"

        names.select("Kathy Green", simulate=True)
        assert names.get_selected_element().name == "Kathy Green"

    def test_menu_bar(self, test_app: JABDriver):
        menu_bar = test_app.find_element_by_role(Role.MENU_BAR)
        assert menu_bar
        self.logger.info(menu_bar.get_element_information())

    def test_menu(self, test_app: JABDriver):
        menu = test_app.find_element_by_xpath("//menu[@name='A Menu']")
        assert menu
        self.logger.info(menu.get_element_information())

    def test_menu_item(self, test_app: JABDriver):
        menu_item = test_app.find_element_by_name("Another one")
        assert menu_item
        menu_item.click()

    def test_separator(self, test_app: JABDriver):
        separator = test_app.find_element_by_xpath("//separator")
        assert separator
        self.logger.info(separator.get_element_information())

    def test_popup_menu(self, test_app: JABDriver):
        test_app.find_element_by_name("Show popup").click()
        popup_menu = test_app.find_element_by_role(Role.POPUP_MENU)
        assert popup_menu
        self.logger.info(popup_menu.get_element_information())

    # ---------------------------------------------------------------- text

    def test_text_field(self, test_app: JABDriver):
        text = test_app.find_element_by_name("1122233455")
        assert text
        text.clear()
        text.send_text(1122233455)
        assert text.text == "1122233455"

    def test_text_area(self, test_app: JABDriver):
        text = test_app.find_element_by_name("Text area contents")
        assert text
        text.clear()
        text.send_text(1122233455)
        assert text.text == "1122233455"

        typed = "ashfueiw^&*$^%"
        text.send_text(typed)
        assert text.text == typed

        text.send_text("4321", simulate=True)
        assert text.text == "4321"

    def test_password_text(self, test_app: JABDriver):
        password = test_app.find_element_by_role(Role.PASSWORD_TEXT)
        assert password

        # A password field never reports what it holds, so the assertion is that
        # typing changes it at all.
        password.send_text("test password")
        first = password.text
        password.send_text("test password2", simulate=True)
        assert password.text != first

    # ---------------------------------------------------------------- data

    def test_table(self, test_app: JABDriver):
        table = test_app.find_element_by_role(Role.TABLE)
        assert table
        self.logger.info(table.get_element_information())

        assert table.table["row_count"] == 5
        assert table.table["column_count"] == 4
        assert table.get_cell(0, 0).name == "Kathy"
        assert table.get_cell(2, 1).name == "Knitting"

    def test_table_edit(self, test_app: JABDriver):
        """A cell can take focus and receive simulated input."""
        table = test_app.find_element_by_role(Role.TABLE)
        cell = table.get_cell(2, 0)
        assert cell

        cell._request_focus()
        self.logger.info(cell.name)

    def test_tree(self, test_app: JABDriver):
        tree = test_app.find_element_by_role(Role.TREE)
        assert tree
        self.logger.info(tree.get_element_information())

        # expand() is idempotent: the tree may already be showing its rows, and
        # it used to send a toggle, which collapsed the node it was called on and
        # hid the very children the next line looks for.
        node = tree.find_element_by_name("Child one")
        node.expand()
        assert node.is_expanded()
        assert tree.find_element_by_name("Child one leaf A")

    # ---------------------------------------------------------------- ranges

    def test_slider(self, test_app: JABDriver):
        slider = test_app.find_element_by_name("First slider")
        assert slider.role_en_us == "slider"
        slider.slide(to_bottom=True)
        slider.slide(to_bottom=False)

    def test_second_slider(self, test_app: JABDriver):
        """Two sliders exist; locate the second one by name, not by position."""
        slider = test_app.find_element_by_name("Second slider")
        assert slider.role_en_us == "slider"
        slider.slide(to_bottom=True)

    def test_spinner(self, test_app: JABDriver):
        """Both spin directions, measured against the value they started from.

        This used to assert absolute values after ``spin(option="2005")``, which
        does not work: that call writes into the spinner's editor, and whether
        the model adopts what was typed is the editor's business. The model
        stayed on its initial value, so the increment went to 2002 rather than
        the 2006 the test expected. Comparing against the starting value tests
        the thing that is actually pyjab's -- that spinning moves the value and
        that the two directions are inverses.
        """
        spinner = test_app.find_element_by_role("spinbox")
        assert spinner

        # The value lives in the spinner's text child.
        def value():
            return spinner.find_element_by_role("text").text

        start = value()

        spinner.spin(increase=True)
        increased = value()
        assert increased != start, "increment did not change the value"

        spinner.spin(increase=False, simulate=True)
        assert value() == start, "decrement did not restore the starting value"

    # ---------------------------------------------------------------- dialogs

    def test_dialog(self, test_app: JABDriver):
        dialog = self.open_dialog(test_app, "Show dialog", "A Dialog")

        assert dialog.find_element_by_role(Role.DIALOG)
        assert dialog.find_element_by_name("Dialog label")

        dialog.find_element_by_name("Close dialog").click()

    def test_alert(self, test_app: JABDriver):
        dialog = self.open_dialog(test_app, "Show alert", "An Alert")

        alert = dialog.find_element_by_role(Role.ALERT)
        assert alert
        self.logger.info(alert.get_element_information())

    def test_color_chooser(self, test_app: JABDriver):
        dialog = self.open_dialog(test_app, "Show color chooser", "A Color Chooser")

        color_chooser = dialog.find_element_by_role(Role.COLOR_CHOOSER)
        assert color_chooser
        self.logger.info(color_chooser.get_element_information())

    def test_page_tab_list(self, test_app: JABDriver):
        """The colour chooser carries a real page tab list.

        Its tab titles come from a resource bundle, so they are ``HSV``/``HSL``/
        ``RGB`` in English and ``HSV(H)``/``HSL(L)``/``RGB(G)`` elsewhere.  The
        conftest pins the test JVM to ``en_US``, and the assertions below use a
        substring match as well, so neither the locale nor a cosmetic rename
        breaks them.
        """
        dialog = self.open_dialog(test_app, "Show color chooser", "A Color Chooser")

        page_tab_list = dialog.find_element_by_role(Role.PAGE_TAB_LIST)
        assert page_tab_list
        self.logger.info(page_tab_list.get_element_information())

        page_tab_list.select("HSL")
        assert dialog.find_element_by_xpath(
            "//page tab[@name=contains('HSL')]"
        ).is_selected()

        page_tab_list.select("RGB", simulate=True)
        assert dialog.find_element_by_xpath(
            "//page tab[@name=contains('RGB')]"
        ).is_selected()

    def test_page_tab(self, test_app: JABDriver):
        dialog = self.open_dialog(test_app, "Show color chooser", "A Color Chooser")

        page_tab = dialog.find_element_by_xpath("//page tab[@name=contains('HSV')]")
        assert page_tab
        self.logger.info(page_tab.get_element_information())

        page_tab.click(simulate=True)
        assert page_tab.is_selected()

    # ---------------------------------------------------------------- misc

    def test_component_info(self, test_app: JABDriver):
        """Every locator the API documents resolves to something."""
        for by_role in [
            Role.FRAME, Role.ROOT_PANE, Role.LAYERED_PANE, Role.PANEL,
            Role.LABEL, Role.PUSH_BUTTON, Role.CHECK_BOX, Role.RADIO_BUTTON,
            Role.TABLE, Role.TREE, Role.LIST, Role.PROGRESS_BAR,
            Role.SPLIT_PANE, Role.TOOL_BAR, Role.VIEW_PORT,
        ]:
            element = test_app.find_element_by_role(by_role)
            assert element, f"no element with role {by_role}"

    def test_visible_only(self, test_app: JABDriver):
        """Filtering to showing elements does not lose the ones on screen."""
        buttons = [
            element
            for element in test_app.find_elements_by_role(Role.PUSH_BUTTON)
            if States.SHOWING in element.states
        ]

        assert buttons
        assert any(button.name == "Middle button" for button in buttons)
