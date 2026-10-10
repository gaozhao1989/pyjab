"""The standard-library PNG writer, checked by decoding what it produces.

Why this is not tested with ``assert png.startswith(b"\\x89PNG")``: **a wrong PNG is not
always an unreadable one.** A filter byte off, a row stride off by one, rows bottom-up
instead of top-down -- each gives a file that opens, at the wrong size or upside down or
sheared. This project's recurring failure is the thing that looks like it worked, so every
test here decodes the bytes back to pixels and compares them.

The decoder is in the module for this reason and is deliberately narrow: it reads the one
shape the writer produces and raises on anything else, rather than being a general PNG
reader that might be the thing that is wrong.
"""

from __future__ import annotations

import zlib

import pytest

from pyjab.common.png import SIGNATURE, bgra_to_png, decode_png


def bgra(pixels):
    """A BGRA buffer from ``(r, g, b, a)`` pixels, which is the order GDI hands over."""
    return b"".join(bytes([b, g, r, a]) for (r, g, b, a) in pixels)


BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)
RED = (255, 0, 0, 255)
WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
BROWN = (128, 64, 32, 255)


def test_it_starts_with_the_signature():
    """Necessary and nowhere near sufficient, which is why it is not the only test."""
    assert bgra_to_png(bgra([RED]), 1, 1).startswith(SIGNATURE)


def test_the_colours_are_not_swapped():
    """The buffer is BGRA and a PNG is RGBA. Reversing the wrong pair gives a blue image
    that is entirely plausible if you only ever screenshot blue things."""
    _w, _h, rows = decode_png(bgra_to_png(bgra([RED, GREEN, BLUE]), 3, 1))

    assert rows[0] == [RED, GREEN, BLUE]


def test_the_dimensions_survive():
    png = bgra_to_png(bgra([RED] * 6), 3, 2)

    width, height, rows = decode_png(png)

    assert (width, height) == (3, 2)
    assert len(rows) == 2 and len(rows[0]) == 3


def test_rows_are_top_down_by_default():
    """Row order is the difference between an image and its mirror, and both open."""
    top, bottom = RED, BLUE
    _w, _h, rows = decode_png(bgra_to_png(bgra([top] * 2 + [bottom] * 2), 2, 2))

    assert rows[0] == [top, top]
    assert rows[1] == [bottom, bottom]


def test_bottom_up_reverses_the_rows_and_nothing_else():
    """GDI's GetDIBits hands back bottom-to-top for a positive-height bitmap.

    Reversing the rows is not the same as reversing the pixel sequence -- the second also
    mirrors every row, which is a plausible-looking mistake and the one this asserts
    against. It was in fact written that way first, and this test is what caught it.
    """
    _w, _h, rows = decode_png(
        bgra_to_png(bgra([RED, GREEN] + [WHITE, BLACK]), 2, 2, bottom_up=True)
    )

    assert rows[0] == [WHITE, BLACK]
    assert rows[1] == [RED, GREEN]


def test_a_short_buffer_is_refused():
    """A short buffer encodes into a sheared image that still opens."""
    with pytest.raises(ValueError, match="expected 24 bytes"):
        bgra_to_png(bgra([RED] * 5), 3, 2)


@pytest.mark.parametrize("width,height", [(0, 1), (1, 0), (-1, 1)])
def test_a_nonsensical_size_is_refused(width, height):
    with pytest.raises(ValueError, match="must be positive"):
        bgra_to_png(b"", width, height)


def test_the_alpha_channel_survives():
    """Screenshots are opaque, but the format carries alpha and dropping it would be a
    silent change to every pixel."""
    pixel = (10, 20, 30, 128)
    _w, _h, rows = decode_png(bgra_to_png(bgra([pixel]), 1, 1))

    assert rows[0][0] == pixel


def test_the_crc_is_right():
    """A wrong CRC makes a file that most viewers open and some refuse."""
    data = bgra_to_png(bgra([RED, GREEN, BLUE, WHITE]), 2, 2)

    pos = len(SIGNATURE)
    checked = 0
    while pos < len(data):
        import struct
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        (stored,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        assert stored == zlib.crc32(kind + payload) & 0xFFFFFFFF, f"{kind} CRC"
        pos += 12 + length
        checked += 1
    assert checked >= 3, "IHDR, IDAT and IEND at least"


def test_the_decoder_refuses_a_file_it_did_not_write():
    """So that a failure in the decoder cannot be mistaken for a pass."""
    with pytest.raises(ValueError, match="not a PNG"):
        decode_png(b"GIF89a")
