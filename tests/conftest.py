import os
import subprocess
from enum import Enum
from pathlib import Path
from subprocess import Popen
from typing import NamedTuple

import pytest
import requests

from pyjab.jabdriver import JABDriver

# Default destination for test files download
ROOT_DIR = Path(__file__).resolve().parent
TEST_FILES_DIR = Path(ROOT_DIR / "jnlps")

# Base URLs for test JNLPs
BASE_ORACLE_URL = "https://docs.oracle.com/javase"
UI_SWING_BASE_URL = "/".join([BASE_ORACLE_URL, "tutorialJWS/samples/uiswing"])


class TestFile(NamedTuple):
    url: str
    file: Path


class DemoUrl(Enum):
    def __new__(cls, *args, **kwargs):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, value):
        super().__init__()
        _jnlp_file_path = Path(TEST_FILES_DIR / f"{self._name_}.jnlp")
        _zip_file_path = Path(TEST_FILES_DIR / f"{self._name_}.zip")
        self._value_ = TestFile(url=value,
                                file=_jnlp_file_path if value.endswith(".jnlp") else _zip_file_path)

    BUTTON = "/".join([UI_SWING_BASE_URL, "ButtonDemoProject/ButtonDemo.jnlp"])
    CHECK_BOX = "/".join([UI_SWING_BASE_URL, "CheckBoxDemoProject/CheckBoxDemo.jnlp"])
    COLOR_CHOOSER = "/".join([UI_SWING_BASE_URL, "ColorChooserDemoProject/ColorChooserDemo.jnlp"])
    COMBO_BOX = "/".join([UI_SWING_BASE_URL, "ComboBoxDemoProject/ComboBoxDemo.jnlp"])
    DIALOG = "/".join([UI_SWING_BASE_URL, "DialogDemoProject/DialogDemo.jnlp"])
    FILE_CHOOSER = "/".join(
        [BASE_ORACLE_URL, "tutorial/uiswing/examples/zipfiles/components-FileChooserDemo2Project.zip"])
    FRAME = "/".join([UI_SWING_BASE_URL, "FrameDemoProject/FrameDemo.jnlp"])
    INTERNAL_FRAME = "/".join([UI_SWING_BASE_URL, "InternalFrameDemoProject/InternalFrameDemo.jnlp"])
    LABEL = "/".join([UI_SWING_BASE_URL, "LabelDemoProject/LabelDemo.jnlp"])
    LAYERED_PANE = "/".join([UI_SWING_BASE_URL, "LayeredPaneDemoProject/LayeredPaneDemo.jnlp"])
    LIST = "/".join([UI_SWING_BASE_URL, "ListDemoProject/ListDemo.jnlp"])
    MENU = "/".join([UI_SWING_BASE_URL, "MenuDemoProject/MenuDemo.jnlp"])
    PASSWORD = "/".join([UI_SWING_BASE_URL, "PasswordDemoProject/PasswordDemo.jnlp"])
    POPUP = "/".join([UI_SWING_BASE_URL, "PopupMenuDemoProject/PopupMenuDemo.jnlp"])
    PROGRESS_BAR = "/".join([UI_SWING_BASE_URL, "ProgressBarDemoProject/ProgressBarDemo.jnlp"])
    RADIO_BUTTON = "/".join([UI_SWING_BASE_URL, "RadioButtonDemoProject/RadioButtonDemo.jnlp"])
    ROOT_LAYERED_PANE = "/".join([UI_SWING_BASE_URL, "RootLayeredPaneDemoProject/RootLayeredPaneDemo.jnlp"])
    SCROLL = "/".join([UI_SWING_BASE_URL, "ScrollDemoProject/ScrollDemo.jnlp"])
    SLIDER = "/".join([UI_SWING_BASE_URL, "SliderDemoProject/SliderDemo.jnlp"])
    SLIDER_TWO = "/".join([UI_SWING_BASE_URL, "SliderDemo2Project/SliderDemo2.jnlp"])
    SPINNER = "/".join([UI_SWING_BASE_URL, "SpinnerDemoProject/SpinnerDemo.jnlp"])
    SPLIT_PANE = "/".join([UI_SWING_BASE_URL, "SplitPaneDemoProject/SplitPaneDemo.jnlp"])
    STATUS_BAR = "/".join([UI_SWING_BASE_URL, "StatusBarDemoProject/StatusBarDemo.jnlp"])
    TABLE = "/".join([UI_SWING_BASE_URL, "TableDemoProject/TableDemo.jnlp"])
    TEXT_AREA = "/".join([UI_SWING_BASE_URL, "TextAreaDemoProject/TextAreaDemo.jnlp"])
    TOOLBAR = "/".join([UI_SWING_BASE_URL, "ToolBarDemoProject/ToolBarDemo.jnlp"])
    TREE = "/".join([UI_SWING_BASE_URL, "TreeDemoProject/TreeDemo.jnlp"])
    TABLE_FTF_EDIT = "/".join([UI_SWING_BASE_URL, "TableFTFEditDemoProject/TableFTFEditDemo.jnlp"])


@pytest.fixture(scope="module", autouse=True)
def get_test_jnlp_files():
    TEST_FILES_DIR.mkdir(exist_ok=True)

    existing_files = os.listdir(TEST_FILES_DIR)

    for test_file in DemoUrl:
        if test_file.value.file.name in existing_files:
            continue
        r = requests.get(test_file.value.url, allow_redirects=True)
        with open(test_file.value.file, 'wb') as f:
            f.write(r.content)


@pytest.fixture
def button_app() -> JABDriver:
    with AppInit(DemoUrl.BUTTON.value.file, "ButtonDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def checkbox_app() -> JABDriver:
    with AppInit(DemoUrl.CHECK_BOX.value.file, "CheckBoxDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def color_chooser_app() -> JABDriver:
    with AppInit(DemoUrl.COLOR_CHOOSER.value.file, "ColorChooserDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def combo_box_app() -> JABDriver:
    with AppInit(DemoUrl.COMBO_BOX.value.file, "ComboBoxDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def dialog_app() -> JABDriver:
    with AppInit(DemoUrl.DIALOG.value.file, "DialogDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def file_chooser_app() -> JABDriver:
    # TODO: Not sure how this is launching the app
    with AppInit(DemoUrl.FILE_CHOOSER.value.file, "FileChooserDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def frame_app() -> JABDriver:
    with AppInit(DemoUrl.FRAME.value.file, "FrameDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def internal_frame_app() -> JABDriver:
    with AppInit(DemoUrl.INTERNAL_FRAME.value.file, "InternalFrameDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def label_app() -> JABDriver:
    with AppInit(DemoUrl.LABEL.value.file, "LabelDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def layered_pane_app() -> JABDriver:
    with AppInit(DemoUrl.LAYERED_PANE.value.file, "LayeredPaneDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def list_app() -> JABDriver:
    with AppInit(DemoUrl.LIST.value.file, "ListDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def menu_app() -> JABDriver:
    with AppInit(DemoUrl.MENU.value.file, "MenuDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def password_app() -> JABDriver:
    with AppInit(DemoUrl.PASSWORD.value.file, "PasswordDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def popup_app() -> JABDriver:
    with AppInit(DemoUrl.POPUP.value.file, "PopupMenuDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def progress_bar_app() -> JABDriver:
    with AppInit(DemoUrl.PROGRESS_BAR.value.file, "ProgressBarDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def radio_button_app() -> JABDriver:
    with AppInit(DemoUrl.RADIO_BUTTON.value.file, "RadioButtonDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def root_layered_pane_app() -> JABDriver:
    with AppInit(DemoUrl.ROOT_LAYERED_PANE.value.file, "RootLayeredPaneDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def scroll_app() -> JABDriver:
    with AppInit(DemoUrl.SCROLL.value.file, "ScrollDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def slider_app() -> JABDriver:
    with AppInit(DemoUrl.SLIDER.value.file, "SliderDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def slider_two_app() -> JABDriver:
    with AppInit(DemoUrl.SLIDER_TWO.value.file, "SliderDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def spinbox_app() -> JABDriver:
    with AppInit(DemoUrl.SPINNER.value.file, "SpinnerDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def split_pane_app() -> JABDriver:
    with AppInit(DemoUrl.SPLIT_PANE.value.file, "SplitPaneDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def status_bar_app() -> JABDriver:
    with AppInit(DemoUrl.STATUS_BAR.value.file, "StatusBarDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def table_app() -> JABDriver:
    with AppInit(DemoUrl.TABLE.value.file, "TableDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def text_area_app() -> JABDriver:
    with AppInit(DemoUrl.TEXT_AREA.value.file, "TextAreaDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def tool_bar_app() -> JABDriver:
    with AppInit(DemoUrl.TOOLBAR.value.file, "ToolBarDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def tree_app() -> JABDriver:
    with AppInit(DemoUrl.TREE.value.file, "TreeDemo") as jabdriver:
        yield jabdriver


@pytest.fixture
def table_ftf_edit_app() -> JABDriver:
    with AppInit(DemoUrl.TABLE_FTF_EDIT.value.file, "TableFTFEditDemo") as jabdriver:
        yield jabdriver


class AppInit:
    def __init__(self, file: Path, window_name: str):
        self.file = file
        self.name = window_name
        self.jabdriver = None

    def __enter__(self):
        Popen(" ".join(["javaws", str(self.file)]), shell=True).wait()
        self.jabdriver = JABDriver(self.name)
        return self.jabdriver

    def __exit__(self, exc_type, exc_val, exc_tb):
        subprocess.run('cmd /c "wmic process where name=\'jp2launcher.exe\'" delete')
