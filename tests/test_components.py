from pyjab.jabdriver import JABDriver
from logging import Logger


class TestComponents(object):

    logger = Logger("TestComponents")

    def test_alert(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/DialogDemoProject/DialogDemo.jnlp
        jabdriver = JABDriver("Message")
        alert = jabdriver.find_element_by_role("alert")
        assert alert
        self.logger.info(alert.get_element_information())

    def test_checkbox(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/CheckBoxDemoProject/CheckBoxDemo.jnlp
        jabdriver = JABDriver("CheckBoxDemo")
        checkbox = jabdriver.find_element_by_role("check box")
        assert checkbox
        self.logger.info(checkbox.get_element_information())
        checkbox_chin = jabdriver.find_element_by_name("Chin")
        checkbox_hair = jabdriver.find_element_by_name("Hair")
        checkbox_chin.click()
        checkbox_hair.click(simulate=True)

    def test_color_chooser(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ColorChooserDemoProject/ColorChooserDemo.jnlp
        jabdriver = JABDriver("ColorChooserDemo")
        alert = jabdriver.find_element_by_role("color chooser")
        assert alert
        self.logger.info(alert.get_element_information())

    def test_combo_box(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ComboBoxDemoProject/ComboBoxDemo.jnlp
        jabdriver = JABDriver("ComboBoxDemo")
        combo_box = jabdriver.find_element_by_role("combo box")
        assert combo_box
        self.logger.info(combo_box.get_element_information())
        combo_box.select(option="Cat")
        assert combo_box.get_selected_element().name == "Cat"
        combo_box.select(option="Rabbit", simulate=True)
        assert combo_box.get_selected_element().name == "Rabbit"

    def test_dialog(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/DialogDemoProject/DialogDemo.jnlp
        jabdriver = JABDriver("Message")
        dialog = jabdriver.find_element_by_role("dialog")
        assert dialog
        self.logger.info(dialog.get_element_information())

    def test_file_chooser(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorial/uiswing/examples/zipfiles/components-FileChooserDemo2Project.zip
        jabdriver = JABDriver("Attach")
        file_chooser = jabdriver.find_element_by_role("file chooser")
        assert file_chooser
        self.logger.info(file_chooser.get_element_information())

    def test_frame(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/FrameDemoProject/FrameDemo.jnlp
        jabdriver = JABDriver("FrameDemo")
        frame = jabdriver.find_element_by_role("frame")
        assert frame
        self.logger.info(frame.get_element_information())

    def test_internal_frame(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/InternalFrameDemoProject/InternalFrameDemo.jnlp
        jabdriver = JABDriver("InternalFrameDemo")
        internal_frame = jabdriver.find_element_by_role("internal frame")
        assert internal_frame
        self.logger.info(internal_frame.get_element_information())

    def test_label(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/LabelDemoProject/LabelDemo.jnlp
        jabdriver = JABDriver("LabelDemo")
        label = jabdriver.find_element_by_role("label")
        assert label
        self.logger.info(label.get_element_information())

    def test_layered_pane(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/LayeredPaneDemoProject/LayeredPaneDemo.jnlp
        jabdriver = JABDriver("LayeredPaneDemo")
        label = jabdriver.find_element_by_role("layered pane")
        assert label
        self.logger.info(label.get_element_information())

    def test_list(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ListDemoProject/ListDemo.jnlp
        jabdriver = JABDriver("ListDemo")
        _list = jabdriver.find_element_by_role("list")
        assert _list
        self.logger.info(_list.get_element_information())
        _list.select("John Smith")
        assert _list.get_selected_element().name == "John Smith"
        _list.select("Kathy Green", simulate=True)
        assert _list.get_selected_element().name == "Kathy Green"

    def test_menu(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/MenuDemoProject/MenuDemo.jnlp
        jabdriver = JABDriver("MenuDemo")
        menu = jabdriver.find_element_by_xpath("//menu[@name='A Menu']")
        assert menu
        self.logger.info(menu.get_element_information())
        menu.select("Another one")
        menu.select("A check box menu item", simulate=True)

    def test_menu_bar(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/MenuDemoProject/MenuDemo.jnlp
        jabdriver = JABDriver("MenuDemo")
        menu_bar = jabdriver.find_element_by_role("menu bar")
        assert menu_bar
        self.logger.info(menu_bar.get_element_information())

    def test_menu_item(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/MenuDemoProject/MenuDemo.jnlp
        jabdriver = JABDriver("MenuDemo")
        menu_item = jabdriver.find_element_by_role("menu item")
        assert menu_item
        self.logger.info(menu_item.get_element_information())
        menu_item.click()

    def test_page_tab(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ColorChooserDemoProject/ColorChooserDemo.jnlp
        jabdriver = JABDriver("ColorChooserDemo")
        page_tab_hsv = jabdriver.find_element_by_xpath("//page tab[@name='HSV']")
        assert page_tab_hsv
        self.logger.info(page_tab_hsv.get_element_information())
        page_tab_hsv.click(simulate=True)
        assert page_tab_hsv.is_selected()

    def test_page_tab_list(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ColorChooserDemoProject/ColorChooserDemo.jnlp
        jabdriver = JABDriver("ColorChooserDemo")
        page_tab_list = jabdriver.find_element_by_xpath("//page tab list")
        assert page_tab_list
        self.logger.info(page_tab_list.get_element_information())
        page_tab_list.select("HSL")
        assert page_tab_list.get_selected_element().name == "HSL"
        page_tab_list.select("RGB", simulate=True)
        import time

        time.sleep(0.5)
        assert page_tab_list.get_selected_element().name == "RGB"

    def test_panel(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ColorChooserDemoProject/ColorChooserDemo.jnlp
        jabdriver = JABDriver("ColorChooserDemo")
        panel = jabdriver.find_element_by_xpath("//panel")
        assert panel
        self.logger.info(panel.get_element_information())

    def test_password_text(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/PasswordDemoProject/PasswordDemo.jnlp
        jabdriver = JABDriver("PasswordDemo")
        password = jabdriver.find_element_by_xpath("//password text")
        assert password
        self.logger.info(password.get_element_information())
        password.send_text("test password")
        assert password.text != "test password"
        password.send_text("test password2", simulate=True)
        assert password.text != "test password2"

    def test_popup_menu(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/PopupMenuDemoProject/PopupMenuDemo.jnlp
        jabdriver = JABDriver("PopupMenuDemo")
        jabdriver.find_element_by_name("A Menu").click()
        popup_menu = jabdriver.find_element_by_xpath("//popup menu")
        assert popup_menu
        self.logger.info(popup_menu.get_element_information())

    def test_progress_bar(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ProgressBarDemoProject/ProgressBarDemo.jnlp
        jabdriver = JABDriver("ProgressBarDemo")
        progress_bar = jabdriver.find_element_by_role("progress bar")
        assert progress_bar
        self.logger.info(progress_bar.get_element_information())

    def test_push_button(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ButtonDemoProject/ButtonDemo.jnlp
        jabdriver = JABDriver("ButtonDemo")
        left_button = jabdriver.find_element_by_name("Disable middle button")
        assert left_button
        self.logger.info(left_button.get_element_information())
        left_button.click()
        middle_button = jabdriver.find_element_by_name("Middle button")
        assert middle_button.is_enabled() == False
        right_button = jabdriver.find_element_by_name("Enable middle button")
        right_button.click(simulate=True)
        assert middle_button.is_enabled() == True

    def test_radio_button(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/RadioButtonDemoProject/RadioButtonDemo.jnlp
        jabdriver = JABDriver("RadioButtonDemo")
        cat = jabdriver.find_element_by_name("Cat")
        assert cat
        self.logger.info(cat.get_element_information())
        cat.click()
        assert cat.is_checked() == True
        dog = jabdriver.find_element_by_name("Dog")
        dog.click(simulate=True)
        assert dog.is_checked() == True

    def test_root_pane(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/RootLayeredPaneDemoProject/RootLayeredPaneDemo.jnlp
        jabdriver = JABDriver("RootLayeredPaneDemo")
        root_pane = jabdriver.find_element_by_role("root pane")
        assert root_pane
        self.logger.info(root_pane.get_element_information())

    def test_scroll_bar(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ScrollDemoProject/ScrollDemo.jnlp
        jabdriver = JABDriver("ScrollDemo")
        scroll_bar_ver = jabdriver.find_element_by_xpath(
            "//scroll bar[@states=contains('vertical')]"
        )
        assert scroll_bar_ver
        self.logger.info(scroll_bar_ver.get_element_information())
        scroll_bar_ver.scroll(to_bottom=True)
        scroll_bar_ver.scroll(to_bottom=False)
        scroll_bar_hor = jabdriver.find_element_by_xpath(
            "//scroll bar[@states=contains('horizontal')]"
        )
        scroll_bar_hor.scroll(to_bottom=True)
        scroll_bar_hor.scroll(to_bottom=False)

    def test_scroll_pane(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ScrollDemoProject/ScrollDemo.jnlp
        jabdriver = JABDriver("ScrollDemo")
        scroll_pane = jabdriver.find_element_by_xpath("//scroll pane")
        assert scroll_pane
        self.logger.info(scroll_pane.get_element_information())

    def test_separator(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/MenuDemoProject/MenuDemo.jnlp
        jabdriver = JABDriver("MenuDemo")
        separator = jabdriver.find_element_by_xpath("//separator")
        assert separator
        self.logger.info(separator.get_element_information())

    def test_slider(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/SliderDemoProject/SliderDemo.jnlp
        jabdriver = JABDriver("SliderDemo")
        slider = jabdriver.find_element_by_role("slider")
        assert slider
        self.logger.info(slider.get_element_information())
        slider.slide(to_bottom=True)
        slider.slide(to_bottom=False)

    def test_slider2(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/SliderDemo2Project/SliderDemo2.jnlp
        jabdriver = JABDriver("SliderDemo")
        slider = jabdriver.find_element_by_role("slider")
        assert slider
        self.logger.info(slider.get_element_information())
        slider.slide(to_bottom=True)
        slider.slide(to_bottom=False)

    def test_spinnbox(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/SpinnerDemoProject/SpinnerDemo.jnlp
        jabdriver = JABDriver("SpinnerDemo")
        spinner = jabdriver.find_element_by_role("spinbox")
        assert spinner
        self.logger.info(spinner.get_element_information())
        spinner.spin(option="May")
        assert spinner.text == "May\n"
        spinner_year = jabdriver.find_element_by_xpath(
            "//spinbox[@name=contains('Year')]"
        )
        spinner_year.spin(increase=True)
        assert spinner_year.text == "2022\n"
        spinner_year.spin(increase=False, simulate=True)
        assert spinner_year.text == "2021\n"

    def test_split_pane(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/SplitPaneDemoProject/SplitPaneDemo.jnlp
        jabdriver = JABDriver("SplitPaneDemo")
        split_pane = jabdriver.find_element_by_role("split pane")
        assert split_pane
        self.logger.info(split_pane.get_element_information())

    def test_status_bar(self) -> None:
        jabdriver = JABDriver("StatusBarDemo")
        status_bar = jabdriver.find_element_by_role("status bar")
        assert status_bar
        self.logger.info(status_bar.get_element_information())

    def test_table(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/TableDemoProject/TableDemo.jnlp
        jabdriver = JABDriver("TableDemo")
        table = jabdriver.find_element_by_role("table")
        assert table
        self.logger.info(table.get_element_information())
        assert table.get_cell(0, 0).name == "Kathy"
        assert table.get_cell(2, 2).name == "Knitting"

    def test_text_area(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/TextAreaDemoProject/TextAreaDemo.jnlp
        jabdriver = JABDriver("TextAreaDemo")
        text = jabdriver.find_element_by_role("text")
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

    def test_tool_bar(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/ToolBarDemoProject/ToolBarDemo.jnlp
        jabdriver = JABDriver("ToolBarDemo")
        tool_bar = jabdriver.find_element_by_role("tool bar")
        assert tool_bar
        self.logger.info(tool_bar.get_element_information())

    def test_tree(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/TreeDemoProject/TreeDemo.jnlp
        jabdriver = JABDriver("TreeDemo")
        tree = jabdriver.find_element_by_role("tree")
        assert tree
        self.logger.info(tree.get_element_information())
        tree.find_element_by_name("Books for Java Programmers").expand()
        assert tree.find_element_by_name("The Java Developers Almanac")

    def test_viewport(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/TreeDemoProject/TreeDemo.jnlp
        jabdriver = JABDriver("TreeDemo")
        viewport = jabdriver.find_element_by_role("viewport")
        assert viewport
        self.logger.info(viewport.get_element_information())

    def test_table_edit(self) -> None:
        # sample from https://docs.oracle.com/javase/tutorialJWS/samples/uiswing/TableFTFEditDemoProject/TableFTFEditDemo.jnlp
        jabdriver = JABDriver("TableFTFEditDemo")
        table = jabdriver.find_element_by_role("table")
        cell = table.get_cell(2, 2, True)
        assert cell
        self.logger.info(cell.name)
        cell._request_focus()
        cell.send_text("i", simulate=True)
        self.logger.info(cell.name)

    def test_component_info(self)->None:
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