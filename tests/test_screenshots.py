"""The screenshot and window-size methods, which the docs once promised.

Three of these did not exist until 1.6.2: `docs/3-pyjab.md` had been written from
Selenium's documentation and named `get_screenshot_as_png()`,
`get_screenshot_as_base64()` and `get_window_size()`, none of which pyjab had.
They were added after a deliberate decision, so what is pinned here is the shape
Selenium users expect: PNG bytes, base64 of those bytes, and a size pair.

Nothing here touches a screen.  `get_screenshot` is replaced by a small image, so
what is under test is the encoding, not ImageGrab.
"""

from __future__ import annotations

import base64
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import
from pyjab.common.win32utils import Win32Utils
from tests._fakejab import bind, node

# Both modules raise ImportError off Windows unless sys.platform is faked for the
# import; the helpers do that and restore it.  Importing them directly fails.
JABElement = _win32stubs.import_jabelement()
JABDriver = _win32stubs.import_jabdriver()
Win32UtilsClass = Win32Utils.__wrapped__

#: What every PNG file starts with.
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def a_small_image():
    return Image.new("RGB", (4, 3), (10, 20, 30))


def an_element():
    element, _ = bind(node("push button", name="OK"))
    return element


# ---------------------------------------------------------------------------
# The PNG bytes
# ---------------------------------------------------------------------------

def test_an_element_returns_real_png_bytes():
    element = an_element()

    with patch.object(JABElement, "get_screenshot", return_value=a_small_image()):
        data = element.get_screenshot_as_png()

    assert isinstance(data, bytes)
    assert data.startswith(PNG_MAGIC), "not a PNG"


def test_the_bytes_are_a_readable_image():
    """Not just PNG-shaped: it has to open, and be the size that went in."""
    element = an_element()

    with patch.object(JABElement, "get_screenshot", return_value=a_small_image()):
        data = element.get_screenshot_as_png()

    reopened = Image.open(BytesIO(data))
    assert reopened.size == (4, 3)
    assert reopened.getpixel((0, 0)) == (10, 20, 30)


def test_the_bytes_match_what_pillow_would_have_written():
    """The method is a thin wrapper, not a second encoder with its own ideas."""
    element = an_element()
    image = a_small_image()
    expected = BytesIO()
    image.save(expected, format="PNG")

    with patch.object(JABElement, "get_screenshot", return_value=image):
        assert element.get_screenshot_as_png() == expected.getvalue()


# ---------------------------------------------------------------------------
# The base64 form
# ---------------------------------------------------------------------------

def test_base64_is_that_same_png_encoded():
    element = an_element()

    with patch.object(JABElement, "get_screenshot", return_value=a_small_image()):
        png = element.get_screenshot_as_png()
        encoded = element.get_screenshot_as_base64()

    assert isinstance(encoded, str)
    assert base64.b64decode(encoded) == png


def test_base64_is_pure_ascii():
    """It goes into HTML and JSON, where a stray byte is a bug."""
    element = an_element()

    with patch.object(JABElement, "get_screenshot", return_value=a_small_image()):
        encoded = element.get_screenshot_as_base64()

    encoded.encode("ascii")  # raises if it is not


def test_base64_can_be_embedded_without_escaping():
    element = an_element()

    with patch.object(JABElement, "get_screenshot", return_value=a_small_image()):
        encoded = element.get_screenshot_as_base64()

    assert '"' not in encoded and "<" not in encoded and "&" not in encoded


# ---------------------------------------------------------------------------
# The window size
# ---------------------------------------------------------------------------

class _StandInDriver:
    """Just the two attributes JABDriver.get_window_size reads.

    JABDriver.__init__ launches a Java process, so the method is called unbound
    against this instead.
    """

    def __init__(self, root_element, win32utils) -> None:
        self.root_element = root_element
        self.win32utils = win32utils


def a_root_element():
    element, _ = bind(node("frame", name="PyjabTestApp"))
    return element


def test_the_window_size_is_width_then_height():
    """A tuple, matching get_window_position, not the dict Selenium returns."""
    driver = _StandInDriver(a_root_element(), Win32UtilsClass())

    with patch.object(Win32UtilsClass, "_get_window_size", return_value=(800, 600)):
        assert JABDriver.get_window_size(driver) == (800, 600)


def test_the_size_comes_from_the_window_rectangle():
    """GetWindowRect gives (left, top, right, bottom); the size is the difference.

    Pinned because the failure mode is silent: returning `right, bottom` instead
    of the widths looks like a plausible pair of numbers.
    """
    import pyjab.common.win32utils as w

    # create=True, not raising=False: a stand-in win32gui that has no
    # GetWindowRect at all is a legitimate environment (AGENTS.md 4), and patch
    # only tolerates a missing attribute when it is told to create it.
    with patch.object(w.win32gui, "GetWindowRect",
                      return_value=(100, 50, 900, 650), create=True):
        assert Win32UtilsClass._get_window_size(1234) == (800, 600)


def test_a_window_not_at_the_origin_is_not_reported_by_position():
    """The likely off-by-origin bug: reporting left/top rather than sizes."""
    import pyjab.common.win32utils as w

    with patch.object(w.win32gui, "GetWindowRect",
                      return_value=(0, 0, 640, 480), create=True):
        assert Win32UtilsClass._get_window_size(1234) == (640, 480)
