from pyjab.jabdriver import JABDriver


class TestBugFix(object):
    def test_fix_same_title(self) -> None:
        # Create same name folder and open it
        jabdriver = JABDriver(title="Java Control Panel")
        assert jabdriver

    def test_fix_jab_init(self) -> None:
        jabdriver = JABDriver(title="Java Control Panel")
        tab_general = jabdriver.find_element_by_name("General")
        assert tab_general

    def test_multiple_key_press(self) -> None:
        jabdriver = JABDriver(title="Java Control Panel")
        jabdriver.find_element_by_name("General").click(simulate=True)
        jabdriver._press_hold_release_key("tab", "shift")
