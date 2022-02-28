class TestBugFix(object):
    def test_fix_same_title(self, java_control_app) -> None:
        assert java_control_app

    def test_fix_jab_init(self, java_control_app) -> None:
        tab_general = java_control_app.find_element_by_name("General")
        assert tab_general

    def test_multiple_key_press(self, java_control_app) -> None:
        java_control_app.find_element_by_name("General").click(simulate=True)
        java_control_app._press_hold_release_key("tab", "shift")
