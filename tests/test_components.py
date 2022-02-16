from datetime import date

from pyjab.common.role import Role
from pyjab.common.states import States
from pyjab.jabdriver import JABDriver
from logging import Logger


class TestComponents(object):
    logger = Logger("TestComponents")

    @staticmethod
    def _click_dialog_popup_button(jab_driver: JABDriver):
        push_button = [e for e in jab_driver.find_elements_by_role(Role.PUSH_BUTTON) if States.SHOWING in e.states][0]
        # Doesn't seem to recognise the new window unless click is simulated
        push_button.click(simulate=True)

    def test_alert(self, dialog_app):
        self._click_dialog_popup_button(dialog_app)
        # Switch to popup dialog
        popup_jab_driver = JABDriver("Message")
        alert = popup_jab_driver.find_element_by_role(Role.ALERT)
        assert alert
        self.logger.info(alert.get_element_information())

    def test_checkbox(self, checkbox_app):
        checkbox = checkbox_app.find_element_by_role(Role.CHECK_BOX)
        assert checkbox
        self.logger.info(checkbox.get_element_information())
        checkbox_chin = checkbox_app.find_element_by_name("Chin")
        checkbox_hair = checkbox_app.find_element_by_name("Hair")
        checkbox_chin.click()
        checkbox_hair.click(simulate=True)

    def test_color_chooser(self, color_chooser_app):
        alert = color_chooser_app.find_element_by_role(Role.COLOR_CHOOSER)
        assert alert
        self.logger.info(alert.get_element_information())

    def test_combo_box(self, combo_box_app):
        combo_box = combo_box_app.find_element_by_role(Role.COMBO_BOX)
        assert combo_box
        self.logger.info(combo_box.get_element_information())
        combo_box.select(option="Cat")
        assert combo_box.get_selected_element().name == "Cat"
        combo_box.select(option="Rabbit", simulate=True)
        assert combo_box.get_selected_element().name == "Rabbit"

    def test_dialog(self, dialog_app):
        self._click_dialog_popup_button(dialog_app)
        # Switch to popup dialog
        popup_jab_driver = JABDriver("Message")
        popup = popup_jab_driver.find_element_by_role(Role.DIALOG)
        assert popup
        self.logger.info(popup.get_element_information())

    def test_file_chooser(self, file_chooser_app):
        # sample from https://docs.oracle.com/javase/tutorial/uiswing/examples/zipfiles/components-FileChooserDemo2Project.zip
        jabdriver = JABDriver("Attach")
        file_chooser = jabdriver.find_element_by_role(Role.FILE_CHOOSER)
        assert file_chooser
        self.logger.info(file_chooser.get_element_information())

    def test_frame(self, frame_app):
        frame = frame_app.find_element_by_role(Role.FRAME)
        assert frame
        self.logger.info(frame.get_element_information())

    def test_internal_frame(self, internal_frame_app):
        internal_frame = internal_frame_app.find_element_by_role(Role.INTERNAL_FRAME)
        assert internal_frame
        self.logger.info(internal_frame.get_element_information())

    def test_label(self, label_app):
        label = label_app.find_element_by_role(Role.LABEL)
        assert label
        self.logger.info(label.get_element_information())

    def test_layered_pane(self, layered_pane_app):
        label = layered_pane_app.find_element_by_role(Role.LAYERED_PANE)
        assert label
        self.logger.info(label.get_element_information())

    def test_list(self, list_app):
        _list = list_app.find_element_by_role(Role.LIST)
        assert _list
        self.logger.info(_list.get_element_information())
        _list.select("John Smith")
        assert _list.get_selected_element().name == "John Smith"
        _list.select("Kathy Green", simulate=True)
        assert _list.get_selected_element().name == "Kathy Green"

    def test_menu(self, menu_app):
        menu = menu_app.find_element_by_xpath("//menu[@name='A Menu']")
        assert menu
        self.logger.info(menu.get_element_information())
        menu.select("Another one")
        menu.select("A check box menu item", simulate=True)

    def test_menu_bar(self, menu_app):
        menu_bar = menu_app.find_element_by_role(Role.MENU_BAR)
        assert menu_bar
        self.logger.info(menu_bar.get_element_information())

    def test_menu_item(self, menu_app):
        menu_item = menu_app.find_element_by_role(Role.MENU_ITEM)
        assert menu_item
        self.logger.info(menu_item.get_element_information())
        menu_item.click()

    def test_page_tab(self, color_chooser_app):
        page_tab_hsv = color_chooser_app.find_element_by_xpath("//page tab[@name='HSV']")
        assert page_tab_hsv
        self.logger.info(page_tab_hsv.get_element_information())
        page_tab_hsv.click(simulate=True)
        assert page_tab_hsv.is_selected()

    def test_page_tab_list(self, color_chooser_app):
        page_tab_list = color_chooser_app.find_element_by_role(Role.PAGE_TAB_LIST)
        assert page_tab_list
        self.logger.info(page_tab_list.get_element_information())
        page_tab_list.select("HSL")
        assert page_tab_list.get_selected_element().name == "HSL"
        page_tab_list.select("RGB", simulate=True)
        import time
        time.sleep(0.5)
        assert page_tab_list.get_selected_element().name == "RGB"

    def test_panel(self, color_chooser_app):
        panel = color_chooser_app.find_element_by_role(Role.PANEL)
        assert panel
        self.logger.info(panel.get_element_information())

    def test_password_text(self, password_app):
        password = password_app.find_element_by_role(Role.PASSWORD_TEXT)
        assert password
        self.logger.info(password.get_element_information())
        password.send_text("test password")
        assert password.text != "test password"
        password.send_text("test password2", simulate=True)
        assert password.text != "test password2"

    def test_popup_menu(self, popup_app):
        popup_app.find_element_by_name("A Menu").click()
        popup_menu = popup_app.find_element_by_role(Role.POPUP_MENU)
        assert popup_menu
        self.logger.info(popup_menu.get_element_information())

    def test_progress_bar(self, progress_bar_app):
        progress_bar = progress_bar_app.find_element_by_role(Role.PROGRESS_BAR)
        assert progress_bar
        self.logger.info(progress_bar.get_element_information())

    def test_push_button(self, button_app):
        left_button = button_app.find_element_by_name("Disable middle button")
        assert left_button
        self.logger.info(left_button.get_element_information())
        left_button.click()
        middle_button = button_app.find_element_by_name("Middle button")
        assert not middle_button.is_enabled()
        right_button = button_app.find_element_by_name("Enable middle button")
        right_button.click(simulate=True)
        assert middle_button.is_enabled()

    def test_radio_button(self, radio_button_app):
        cat = radio_button_app.find_element_by_name("Cat")
        assert cat
        self.logger.info(cat.get_element_information())
        cat.click(simulate=True)
        assert cat.is_checked()
        dog = radio_button_app.find_element_by_name("Dog")
        dog.click(simulate=True)
        assert dog.is_checked()

    def test_root_pane(self, root_layered_pane_app):
        root_pane = root_layered_pane_app.find_element_by_role(Role.ROOT_PANE)
        assert root_pane
        self.logger.info(root_pane.get_element_information())

    def test_scroll_bar(self, scroll_app):
        scroll_bar_ver = scroll_app.find_element_by_xpath(
            "//scroll bar[@states=contains('vertical')]"
        )
        assert scroll_bar_ver
        self.logger.info(scroll_bar_ver.get_element_information())
        scroll_bar_ver.scroll(to_bottom=True)
        scroll_bar_ver.scroll(to_bottom=False)
        scroll_bar_hor = scroll_app.find_element_by_xpath(
            "//scroll bar[@states=contains('horizontal')]"
        )
        scroll_bar_hor.scroll(to_bottom=True)
        scroll_bar_hor.scroll(to_bottom=False)

    def test_scroll_pane(self, scroll_app):
        scroll_pane = scroll_app.find_element_by_xpath("//scroll pane")
        assert scroll_pane
        self.logger.info(scroll_pane.get_element_information())

    def test_separator(self, menu_app):
        separator = menu_app.find_element_by_xpath("//separator")
        assert separator
        self.logger.info(separator.get_element_information())

    def test_slider(self, slider_app):
        slider = slider_app.find_element_by_role("slider")
        assert slider
        self.logger.info(slider.get_element_information())
        slider.slide(to_bottom=True)
        slider.slide(to_bottom=False)

    def test_slider2(self, slider_two_app):
        slider = slider_two_app.find_element_by_role("slider")
        assert slider
        self.logger.info(slider.get_element_information())
        slider.slide(to_bottom=True)
        slider.slide(to_bottom=False)

    def test_spinnbox(self, spinbox_app):
        spinner = spinbox_app.find_element_by_role("spinbox")
        assert spinner
        self.logger.info(spinner.get_element_information())
        spinner.spin(option="May")
        assert spinner.text == "May"
        spinner_year = spinbox_app.find_element_by_xpath(
            "//spinbox[@name=contains('Year')]"
        )
        spinner_year.spin(increase=True)
        assert spinner_year.text == str(date.today().year + 1)
        spinner_year.spin(increase=False, simulate=True)
        assert spinner_year.text == str(date.today().year)

    def test_split_pane(self, split_pane_app):
        split_pane = split_pane_app.find_element_by_role(Role.SPLIT_PANE)
        assert split_pane
        self.logger.info(split_pane.get_element_information())

    def test_status_bar(self, status_bar_app):
        # TODO: Which app?
        status_bar = status_bar_app.find_element_by_role(Role.STATUS_BAR)
        assert status_bar
        self.logger.info(status_bar.get_element_information())

    def test_table(self, table_app):
        table = table_app.find_element_by_role(Role.TABLE)
        assert table
        self.logger.info(table.get_element_information())
        assert table.get_cell(0, 0).name == "Kathy"
        assert table.get_cell(2, 2).name == "Knitting"

    def test_text_area(self, text_area_app):
        text = text_area_app.find_element_by_role("text")
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

    def test_tool_bar(self, tool_bar_app):
        tool_bar = tool_bar_app.find_element_by_role(Role.TOOL_BAR)
        assert tool_bar
        self.logger.info(tool_bar.get_element_information())

    def test_tree(self, tree_app):
        tree = tree_app.find_element_by_role(Role.TREE)
        assert tree
        self.logger.info(tree.get_element_information())
        tree.find_element_by_name("Books for Java Programmers").expand()
        assert tree.find_element_by_name("The Java Developers Almanac")

    def test_viewport(self, tree_app):
        viewport = tree_app.find_element_by_role(Role.VIEW_PORT)
        assert viewport
        self.logger.info(viewport.get_element_information())

    def test_table_edit(self, table_ftf_edit_app):
        table = table_ftf_edit_app.find_element_by_role(Role.TABLE)
        cell = table.get_cell(2, 2, True)
        assert cell
        self.logger.info(cell.name)
        cell._request_focus()
        cell.send_text("i", simulate=True)
        self.logger.info(cell.name)

    def test_component_info(self):
        # sample from java control panel
        driver = JABDriver("Java Control Panel")
        btn_about = driver.find_element_by_name("About...")
        btn_view = driver.find_element_by_name("View...")
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
