from datetime import date

import pytest

from pyjab.common.role import Role
from pyjab.common.states import States
from pyjab.jabdriver import JABDriver
from logging import Logger

from tests.conftest import OracleApp


class TestComponents(object):
    logger = Logger("TestComponents")

    @staticmethod
    def _click_dialog_popup_button(jab_driver: JABDriver):
        push_button = [e for e in jab_driver.find_elements_by_role(Role.PUSH_BUTTON) if States.SHOWING in e.states][0]
        # Doesn't seem to recognise the new window unless click is simulated
        push_button.click(simulate=True)

    @pytest.mark.parametrize('oracle_app', [OracleApp.DIALOG], indirect=True)
    def test_alert(self, oracle_app: JABDriver):
        self._click_dialog_popup_button(oracle_app)
        # Switch to popup dialog
        popup_jab_driver = JABDriver("Message")
        alert = popup_jab_driver.find_element_by_role(Role.ALERT)
        assert alert
        self.logger.info(alert.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.CHECK_BOX], indirect=True)
    def test_checkbox(self, oracle_app: JABDriver):
        checkbox = oracle_app.find_element_by_role(Role.CHECK_BOX)
        assert checkbox
        self.logger.info(checkbox.get_element_information())
        checkbox_chin = oracle_app.find_element_by_name("Chin")
        checkbox_hair = oracle_app.find_element_by_name("Hair")
        checkbox_chin.click()
        checkbox_hair.click(simulate=True)

    @pytest.mark.parametrize('oracle_app', [OracleApp.COLOR_CHOOSER], indirect=True)
    def test_color_chooser(self, oracle_app: JABDriver):
        alert = oracle_app.find_element_by_role(Role.COLOR_CHOOSER)
        assert alert
        self.logger.info(alert.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.COMBO_BOX], indirect=True)
    def test_combo_box(self, oracle_app: JABDriver):
        combo_box = oracle_app.find_element_by_role(Role.COMBO_BOX)
        assert combo_box
        self.logger.info(combo_box.get_element_information())
        combo_box.select(option="Cat")
        assert combo_box.get_selected_element().name == "Cat"
        combo_box.select(option="Rabbit", simulate=True)
        assert combo_box.get_selected_element().name == "Rabbit"

    @pytest.mark.parametrize('oracle_app', [OracleApp.DIALOG], indirect=True)
    def test_dialog(self, oracle_app: JABDriver):
        self._click_dialog_popup_button(oracle_app)
        # Switch to popup dialog
        popup_jab_driver = JABDriver("Message")
        popup = popup_jab_driver.find_element_by_role(Role.DIALOG)
        assert popup
        self.logger.info(popup.get_element_information())

    # TODO: Allow to automatically run with setup as the other tests
    # @pytest.mark.parametrize('oracle_app', [OracleApp.FILE_CHOOSER], indirect=True)
    # def test_file_chooser(self, oracle_app: JABDriver):
    #     file_chooser = oracle_app.find_element_by_role(Role.FILE_CHOOSER)
    #     assert file_chooser
    #     self.logger.info(file_chooser.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.FRAME], indirect=True)
    def test_frame(self, oracle_app: JABDriver):
        frame = oracle_app.find_element_by_role(Role.FRAME)
        assert frame
        self.logger.info(frame.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.INTERNAL_FRAME], indirect=True)
    def test_internal_frame(self, oracle_app: JABDriver):
        internal_frame = oracle_app.find_element_by_role(Role.INTERNAL_FRAME)
        assert internal_frame
        self.logger.info(internal_frame.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.LABEL], indirect=True)
    def test_label(self, oracle_app: JABDriver):
        label = oracle_app.find_element_by_role(Role.LABEL)
        assert label
        self.logger.info(label.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.LAYERED_PANE], indirect=True)
    def test_layered_pane(self, oracle_app: JABDriver):
        label = oracle_app.find_element_by_role(Role.LAYERED_PANE)
        assert label
        self.logger.info(label.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.LIST], indirect=True)
    def test_list(self, oracle_app: JABDriver):
        _list = oracle_app.find_element_by_role(Role.LIST)
        assert _list
        self.logger.info(_list.get_element_information())
        _list.select("John Smith")
        assert _list.get_selected_element().name == "John Smith"
        _list.select("Kathy Green", simulate=True)
        assert _list.get_selected_element().name == "Kathy Green"

    @pytest.mark.parametrize('oracle_app', [OracleApp.MENU], indirect=True)
    def test_menu(self, oracle_app: JABDriver):
        menu = oracle_app.find_element_by_xpath("//menu[@name='A Menu']")
        assert menu
        self.logger.info(menu.get_element_information())
        menu.select("Another one")
        menu.select("A check box menu item", simulate=True)

    @pytest.mark.parametrize('oracle_app', [OracleApp.MENU], indirect=True)
    def test_menu_bar(self, oracle_app: JABDriver):
        menu_bar = oracle_app.find_element_by_role(Role.MENU_BAR)
        assert menu_bar
        self.logger.info(menu_bar.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.MENU], indirect=True)
    def test_menu_item(self, oracle_app: JABDriver):
        menu_item = oracle_app.find_element_by_role(Role.MENU_ITEM)
        assert menu_item
        self.logger.info(menu_item.get_element_information())
        menu_item.click()

    @pytest.mark.parametrize('oracle_app', [OracleApp.COLOR_CHOOSER], indirect=True)
    def test_page_tab(self, oracle_app: JABDriver):
        page_tab_hsv = oracle_app.find_element_by_xpath("//page tab[@name='HSV']")
        assert page_tab_hsv
        self.logger.info(page_tab_hsv.get_element_information())
        page_tab_hsv.click(simulate=True)
        assert page_tab_hsv.is_selected()

    @pytest.mark.parametrize('oracle_app', [OracleApp.COLOR_CHOOSER], indirect=True)
    def test_page_tab_list(self, oracle_app: JABDriver):
        page_tab_list = oracle_app.find_element_by_role(Role.PAGE_TAB_LIST)
        assert page_tab_list
        self.logger.info(page_tab_list.get_element_information())
        page_tab_list.select("HSL")
        assert page_tab_list.get_selected_element().name == "HSL"
        page_tab_list.select("RGB", simulate=True)
        import time
        time.sleep(0.5)
        assert page_tab_list.get_selected_element().name == "RGB"

    @pytest.mark.parametrize('oracle_app', [OracleApp.COLOR_CHOOSER], indirect=True)
    def test_panel(self, oracle_app: JABDriver):
        panel = oracle_app.find_element_by_role(Role.PANEL)
        assert panel
        self.logger.info(panel.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.PASSWORD], indirect=True)
    def test_password_text(self, oracle_app: JABDriver):
        password = oracle_app.find_element_by_role(Role.PASSWORD_TEXT)
        assert password
        self.logger.info(password.get_element_information())
        password.send_text("test password")
        assert password.text != "test password"
        password.send_text("test password2", simulate=True)
        assert password.text != "test password2"

    @pytest.mark.parametrize('oracle_app', [OracleApp.POPUP], indirect=True)
    def test_popup_menu(self, oracle_app: JABDriver):
        oracle_app.find_element_by_name("A Menu").click()
        popup_menu = oracle_app.find_element_by_role(Role.POPUP_MENU)
        assert popup_menu
        self.logger.info(popup_menu.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.PROGRESS_BAR], indirect=True)
    def test_progress_bar(self, oracle_app: JABDriver):
        progress_bar = oracle_app.find_element_by_role(Role.PROGRESS_BAR)
        assert progress_bar
        self.logger.info(progress_bar.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.BUTTON], indirect=True)
    def test_push_button(self, oracle_app: JABDriver):
        left_button = oracle_app.find_element_by_name("Disable middle button")
        assert left_button
        self.logger.info(left_button.get_element_information())
        left_button.click()
        middle_button = oracle_app.find_element_by_name("Middle button")
        assert not middle_button.is_enabled()
        right_button = oracle_app.find_element_by_name("Enable middle button")
        right_button.click(simulate=True)
        assert middle_button.is_enabled()

    @pytest.mark.parametrize('oracle_app', [OracleApp.RADIO_BUTTON], indirect=True)
    def test_radio_button(self, oracle_app: JABDriver):
        cat = oracle_app.find_element_by_name("Cat")
        assert cat
        self.logger.info(cat.get_element_information())
        cat.click(simulate=True)
        assert cat.is_checked()
        dog = oracle_app.find_element_by_name("Dog")
        dog.click(simulate=True)
        assert dog.is_checked()

    @pytest.mark.parametrize('oracle_app', [OracleApp.ROOT_LAYERED_PANE], indirect=True)
    def test_root_pane(self, oracle_app: JABDriver):
        root_pane = oracle_app.find_element_by_role(Role.ROOT_PANE)
        assert root_pane
        self.logger.info(root_pane.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.SCROLL], indirect=True)
    def test_scroll_bar(self, oracle_app: JABDriver):
        scroll_bar_ver = oracle_app.find_element_by_xpath(
            "//scroll bar[@states=contains('vertical')]"
        )
        assert scroll_bar_ver
        self.logger.info(scroll_bar_ver.get_element_information())
        scroll_bar_ver.scroll(to_bottom=True)
        scroll_bar_ver.scroll(to_bottom=False)
        scroll_bar_hor = oracle_app.find_element_by_xpath(
            "//scroll bar[@states=contains('horizontal')]"
        )
        scroll_bar_hor.scroll(to_bottom=True)
        scroll_bar_hor.scroll(to_bottom=False)

    @pytest.mark.parametrize('oracle_app', [OracleApp.SCROLL], indirect=True)
    def test_scroll_pane(self, oracle_app: JABDriver):
        scroll_pane = oracle_app.find_element_by_xpath("//scroll pane")
        assert scroll_pane
        self.logger.info(scroll_pane.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.MENU], indirect=True)
    def test_separator(self, oracle_app: JABDriver):
        separator = oracle_app.find_element_by_xpath("//separator")
        assert separator
        self.logger.info(separator.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.SLIDER], indirect=True)
    def test_slider(self, oracle_app: JABDriver):
        slider = oracle_app.find_element_by_role("slider")
        assert slider
        self.logger.info(slider.get_element_information())
        slider.slide(to_bottom=True)
        slider.slide(to_bottom=False)

    @pytest.mark.parametrize('oracle_app', [OracleApp.SLIDER_TWO], indirect=True)
    def test_slider2(self, oracle_app: JABDriver):
        slider = oracle_app.find_element_by_role("slider")
        assert slider
        self.logger.info(slider.get_element_information())
        slider.slide(to_bottom=True)
        slider.slide(to_bottom=False)

    @pytest.mark.parametrize('oracle_app', [OracleApp.SPINNER], indirect=True)
    def test_spinnbox(self, oracle_app: JABDriver):
        spinner = oracle_app.find_element_by_role("spinbox")
        assert spinner
        self.logger.info(spinner.get_element_information())
        spinner.spin(option="May")
        assert spinner.text == "May"
        spinner_year = oracle_app.find_element_by_xpath(
            "//spinbox[@name=contains('Year')]"
        )
        spinner_year.spin(increase=True)
        assert spinner_year.text == str(date.today().year + 1)
        spinner_year.spin(increase=False, simulate=True)
        assert spinner_year.text == str(date.today().year)

    @pytest.mark.parametrize('oracle_app', [OracleApp.SPLIT_PANE], indirect=True)
    def test_split_pane(self, oracle_app: JABDriver):
        split_pane = oracle_app.find_element_by_role(Role.SPLIT_PANE)
        assert split_pane
        self.logger.info(split_pane.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.STATUS_BAR], indirect=True)
    def test_status_bar(self, oracle_app: JABDriver):
        # TODO: Which app?
        status_bar = oracle_app.find_element_by_role(Role.STATUS_BAR)
        assert status_bar
        self.logger.info(status_bar.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.TABLE], indirect=True)
    def test_table(self, oracle_app: JABDriver):
        table = oracle_app.find_element_by_role(Role.TABLE)
        assert table
        self.logger.info(table.get_element_information())
        assert table.get_cell(0, 0).name == "Kathy"
        assert table.get_cell(2, 2).name == "Knitting"

    @pytest.mark.parametrize('oracle_app', [OracleApp.TEXT_AREA], indirect=True)
    def test_text_area(self, oracle_app: JABDriver):
        text = oracle_app.find_element_by_role("text")
        assert text
        text.clear()
        self.logger.info("clear text")
        text.send_text(1122233455)
        assert text.text == "1122233455"
        txt_chars = "ashfueiw^&*$^%$测试文本"
        text.send_text(txt_chars)
        assert text.text == txt_chars
        text.send_text(1122233455, simulate=True)
        assert text.text == "1122233455"
        text.send_text(txt_chars, simulate=True)
        assert text.text == txt_chars

    @pytest.mark.parametrize('oracle_app', [OracleApp.TOOLBAR], indirect=True)
    def test_tool_bar(self, oracle_app: JABDriver):
        tool_bar = oracle_app.find_element_by_role(Role.TOOL_BAR)
        assert tool_bar
        self.logger.info(tool_bar.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.TREE], indirect=True)
    def test_tree(self, oracle_app: JABDriver):
        tree = oracle_app.find_element_by_role(Role.TREE)
        assert tree
        self.logger.info(tree.get_element_information())
        tree.find_element_by_name("Books for Java Programmers").expand()
        assert tree.find_element_by_name("The Java Developers Almanac")

    @pytest.mark.parametrize('oracle_app', [OracleApp.TREE], indirect=True)
    def test_viewport(self, oracle_app: JABDriver):
        viewport = oracle_app.find_element_by_role(Role.VIEW_PORT)
        assert viewport
        self.logger.info(viewport.get_element_information())

    @pytest.mark.parametrize('oracle_app', [OracleApp.TABLE_FTF_EDIT], indirect=True)
    def test_table_edit(self, oracle_app: JABDriver):
        table = oracle_app.find_element_by_role(Role.TABLE)
        cell = table.get_cell(2, 2, True)
        assert cell
        self.logger.info(cell.name)
        cell._request_focus()
        cell.send_text("i", simulate=True)
        self.logger.info(cell.name)

    def test_component_info(self, java_control_app):
        btn_about = java_control_app.find_element_by_name("About...")
        btn_view = java_control_app.find_element_by_name("View...")
        self.logger.info(btn_about.name)
        self.logger.info(btn_view.name)
        self.logger.info(btn_about.description)
        self.logger.info(btn_view.description)
        self.logger.info(btn_about.role)
        self.logger.info(btn_view.role)
        self.logger.info(btn_about.role_en_us)
        self.logger.info(btn_view.role_en_us)
        self.logger.info(btn_about.states)
        self.logger.info(btn_view.states)
        self.logger.info(btn_about.states_en_us)
        self.logger.info(btn_view.states_en_us)
        self.logger.info(btn_about.bounds)
        self.logger.info(btn_view.bounds)
        self.logger.info(btn_about.object_depth)
        self.logger.info(btn_view.object_depth)
        self.logger.info(btn_about.index_in_parent)
        self.logger.info(btn_view.index_in_parent)
        self.logger.info(btn_about.children_count)
        self.logger.info(btn_view.children_count)
        self.logger.info(btn_about.accessible_component)
        self.logger.info(btn_view.accessible_component)
        self.logger.info(btn_about.accessible_action)
        self.logger.info(btn_view.accessible_action)
        self.logger.info(btn_about.accessible_selection)
        self.logger.info(btn_view.accessible_selection)
        self.logger.info(btn_about.accessible_text)
        self.logger.info(btn_view.accessible_text)
        self.logger.info(btn_about.text)
        self.logger.info(btn_view.text)
        self.logger.info(btn_about.table)
        self.logger.info(btn_view.table)
