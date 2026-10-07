from __future__ import annotations

import os
import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest

if TYPE_CHECKING:
    from pyjab.jabdriver import JABDriver

# The GUI test modules import :mod:`pyjab.jabdriver` at module scope, which pulls
# in pywin32, and they need a real JDK, real Swing applications and an
# interactive desktop session.  They are therefore opt-in everywhere:
#
#     PYJAB_RUN_GUI_TESTS=1 pytest tests/
#
# Without that variable only the platform independent tests get collected.
GUI_TEST_MODULES = [
    "test_bridge_dll.py",
    "test_bug_fix.py",
    "test_components.py",
    "test_message_pump_gui.py",
]

collect_ignore: list[str] = []
if sys.platform != "win32" or os.environ.get("PYJAB_RUN_GUI_TESTS") != "1":
    collect_ignore += GUI_TEST_MODULES

# Default destination for test files download
ROOT_DIR = Path(__file__).resolve().parent
TEST_FILES_DIR = Path(ROOT_DIR / "jnlps")

# Base URLs for test JNLPs
BASE_ORACLE_URL = "https://docs.oracle.com/javase"
UI_SWING_BASE_URL = "/".join([BASE_ORACLE_URL, "tutorialJWS/samples/uiswing"])


class TestFile(NamedTuple):
    url: str
    file: Path
    window_title: str


class OracleApp(Enum):
    def __new__(cls, *args, **kwargs):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, value):
        super().__init__()
        _jnlp_file_path = Path(TEST_FILES_DIR / f"{self._name_}.jnlp")
        _zip_file_path = Path(TEST_FILES_DIR / f"{self._name_}.zip")

        def extract_file_name(path: str):
            # Get last string after / and then the first string before .
            return path.split("/")[-1].split(".")[0]

        def remove_digits(input_str: str):
            return ''.join([i for i in input_str if not i.isdigit()])

        self._value_ = TestFile(url=value,
                                file=_jnlp_file_path if value.endswith(".jnlp") else _zip_file_path,
                                window_title=remove_digits(extract_file_name(value)))

    BUTTON = "/".join([UI_SWING_BASE_URL, "ButtonDemoProject/ButtonDemo.jnlp"])
    CHECK_BOX = "/".join([UI_SWING_BASE_URL, "CheckBoxDemoProject/CheckBoxDemo.jnlp"])
    COLOR_CHOOSER = "/".join([UI_SWING_BASE_URL, "ColorChooserDemoProject/ColorChooserDemo.jnlp"])
    COMBO_BOX = "/".join([UI_SWING_BASE_URL, "ComboBoxDemoProject/ComboBoxDemo.jnlp"])
    DIALOG = "/".join([UI_SWING_BASE_URL, "DialogDemoProject/DialogDemo.jnlp"])
    # This needs to be looked at how to do properly as needs making into launchable project
    # FILE_CHOOSER = "/".join(
    #     [BASE_ORACLE_URL, "tutorial/uiswing/examples/zipfiles/components-FileChooserDemo2Project.zip"])
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


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "gui: needs Windows, a real JDK and an interactive desktop session. "
        "Deselect with '-m \"not gui\"'.",
    )


@pytest.fixture(scope="module")
def test_jnlp_files():
    """Download the Oracle Swing demo JNLP files used by the GUI tests.

    Deliberately *not* autouse: it needs network access and is only relevant to
    the GUI test modules, which request this fixture explicitly.
    """
    import requests

    TEST_FILES_DIR.mkdir(exist_ok=True)

    existing_files = os.listdir(TEST_FILES_DIR)

    for test_file in OracleApp:
        if test_file.value.file.name in existing_files:
            continue
        r = requests.get(test_file.value.url, allow_redirects=True)
        with open(test_file.value.file, 'wb') as f:
            f.write(r.content)


@pytest.fixture
def oracle_app(request) -> JABDriver:
    from pyjab.jabdriver import JABDriver

    app: TestFile = request.param.value
    with JABDriver(file_path=app.file, title=app.window_title) as jab_driver:
        yield jab_driver


@pytest.fixture
def java_control_app() -> JABDriver:
    from pyjab.jabdriver import JABDriver

    # Assumes installation of some jdk 1.8 - currently hardcoded
    with JABDriver(file_path=Path(r"C:\Program Files\Java\jdk1.8.0_311\jre\bin\javacpl.exe"),
                   title="Java Control Panel") as jabdriver:
        yield jabdriver
