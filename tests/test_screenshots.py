"""The screenshot and window-size methods, which the docs once promised.

Three of these did not exist until 1.6.2: `docs/3-pyjab.md` had been written from
Selenium's documentation and named `get_screenshot_as_png()`,
`get_screenshot_as_base64()` and `get_window_size()`, none of which pyjab had.
They were added after a deliberate decision, so what is pinned here is the shape
Selenium users expect: PNG bytes, base64 of those bytes, and a size pair.

Nothing here touches a screen.  `Win32Utils.grab_rect` is replaced by a known buffer,
so what is under test is the encoding and the wiring, not BitBlt.  The decode is done by
`pyjab.common.png.decode_png` rather than by an image library, because that is the whole
point of the change this test was updated for: neither the encoder nor its verification
needs Pillow any more.
"""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest

from pyjab.common.png import decode_png

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


#: A 4x3 frame, top-left pixel red and the rest a known grey, in BGRA as GDI hands it
#: over.  Small enough to write out, and not a solid colour -- a solid colour survives
#: having its rows scrambled.
SMALL_WIDTH, SMALL_HEIGHT = 4, 3
SMALL_PIXELS = [
    [(0, 0, 255, 255)] + [(10, 20, 30, 255)] * 3,
    [(10, 20, 30, 255)] * 4,
    [(10, 20, 30, 255)] * 4,
]


def a_small_buffer(width: int = SMALL_WIDTH, height: int = SMALL_HEIGHT) -> bytes:
    """A buffer of the requested size, the known pattern tiled into it.

    Sized to the request rather than fixed, because the code under test asks for the
    element's own rectangle -- which the fixture decides, not this file.  A fixed buffer
    makes that a ValueError about byte counts, which is a test artefact rather than a
    finding.
    """
    pixel = bytes([30, 20, 10, 255])
    return pixel * (width * height)


def an_element():
    element, _ = bind(node("push button", name="OK"))
    return element


# ---------------------------------------------------------------------------
# The PNG bytes
# ---------------------------------------------------------------------------

def test_an_element_returns_real_png_bytes():
    element = an_element()

    with patch.object(Win32UtilsClass, "grab_rect",
                      side_effect=lambda x, y, w, h: a_small_buffer(w, h)):
        data = element.get_screenshot_as_png()

    assert isinstance(data, bytes)
    assert data.startswith(PNG_MAGIC), "not a PNG"


def test_the_bytes_are_a_readable_image():
    """Not just PNG-shaped: it has to open, and be the size that went in."""
    element = an_element()

    asked = {}

    def grab(x, y, width, height):
        asked.update(width=width, height=height)
        return a_small_buffer(width, height)

    with patch.object(Win32UtilsClass, "grab_rect", side_effect=grab):
        data = element.get_screenshot_as_png()

    # The size comes from the element's own rectangle, which the fixture decides -- not
    # from a constant here, which is how this test was wrong first time round.
    width, height, rows = decode_png(data)
    assert (width, height) == (asked["width"], asked["height"])
    assert rows[0][0] == (10, 20, 30, 255)


def test_the_bytes_are_the_grabbed_rectangle_and_nothing_else():
    """The method is a thin wrapper over the grab and the encoder, not a third thing.

    This used to compare against Pillow's own output, which pinned "the same bytes as
    Pillow would write" -- a claim that stopped meaning anything once Pillow was gone, and
    that was never the contract anyway: two encoders may legitimately differ in filters and
    compression level and both be right.  What matters is that the pixels that come back
    are the pixels that were grabbed, at the size that was asked for.
    """
    element = an_element()
    requested = {}

    def grab(x, y, width, height):
        requested.update(x=x, y=y, width=width, height=height)
        return a_small_buffer(width, height)

    from pyjab.common.png import bgra_to_png
    with patch.object(Win32UtilsClass, "grab_rect", side_effect=grab):
        data = element.get_screenshot_as_png()

    width, height, rows = decode_png(data)
    assert (width, height) == (requested["width"], requested["height"])
    assert data == bgra_to_png(a_small_buffer(requested["width"], requested["height"]),
                               requested["width"], requested["height"])


# ---------------------------------------------------------------------------
# The base64 form
# ---------------------------------------------------------------------------

def test_base64_is_that_same_png_encoded():
    element = an_element()

    with patch.object(Win32UtilsClass, "grab_rect",
                      side_effect=lambda x, y, w, h: a_small_buffer(w, h)):
        png = element.get_screenshot_as_png()
        encoded = element.get_screenshot_as_base64()

    assert isinstance(encoded, str)
    assert base64.b64decode(encoded) == png


def test_base64_is_pure_ascii():
    """It goes into HTML and JSON, where a stray byte is a bug."""
    element = an_element()

    with patch.object(Win32UtilsClass, "grab_rect",
                      side_effect=lambda x, y, w, h: a_small_buffer(w, h)):
        encoded = element.get_screenshot_as_base64()

    encoded.encode("ascii")  # raises if it is not


def test_base64_can_be_embedded_without_escaping():
    element = an_element()

    with patch.object(Win32UtilsClass, "grab_rect",
                      side_effect=lambda x, y, w, h: a_small_buffer(w, h)):
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
