"""Writing a PNG, with nothing but the standard library.

Pillow was a runtime dependency for two reasons, and only one of them was real: encoding
a PNG, and handing back an ``Image``. The second is pyjab's own divergence -- Selenium's
``get_screenshot()`` returns base64, and pyjab's docstring has always said so -- so the
first is what this module exists to remove.

A PNG of a screenshot is one of the simplest files in the format: 8-bit truecolour with
alpha (colour type 6), no interlacing, one ``IDAT`` holding zlib-compressed rows each
prefixed by a filter byte. That is what this writes, and it is deliberately the whole of
what it writes -- no palette, no bit depths, no interlacing, because a screenshot needs
none of them and each one is code that would never be exercised.

**The reason to be careful here is that a wrong PNG is not always an unreadable one.** A
bad filter byte, a row stride off by one, rows bottom-up instead of top-down -- each
produces a file that opens, at the wrong size or upside down or sheared. That is the
failure this project keeps finding: something that looks like it worked. The tests decode
what this produces back to pixels and compare, rather than asserting it starts with the
PNG signature.
"""

from __future__ import annotations

import struct
import zlib
from typing import Iterable, List, Sequence, Tuple

#: A PNG begins with these eight bytes. A file that has them is not thereby valid, which
#: is why nothing here tests for them.
SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: Colour type 6 is truecolour with alpha: what a screenshot needs, and the only shape this
#: module writes.
_COLOUR_TYPE_RGBA = 6
_BIT_DEPTH = 8


def _chunk(kind: bytes, payload: bytes) -> bytes:
    """One PNG chunk: length, type, payload, CRC over type+payload."""
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def bgra_to_png(data: bytes, width: int, height: int, *,
                bottom_up: bool = False) -> bytes:
    """Encode a BGRA buffer as a PNG.

    Args:
        data: ``width * height * 4`` bytes, four per pixel, in B, G, R, A order.
        width: pixels per row.
        height: rows.
        bottom_up: the buffer's rows are in bottom-to-top order, which is what GDI's
            ``GetDIBits`` produces for a positive-height bitmap. Reversing them here rather
            than at the call site keeps the orientation next to the stride arithmetic it
            has to agree with.

    Returns:
        bytes: a complete PNG file.

    Raises:
        ValueError: the buffer is not the size those dimensions imply. Checked rather than
            tolerated because a short buffer encodes into a sheared image that still opens.
    """
    # Size first, then length. The other order computes a byte count from a negative
    # dimension and reports "expected -4 bytes", which is worse than no message at all.
    if width <= 0 or height <= 0:
        raise ValueError(f"width and height must be positive, got {width}x{height}")
    expected = width * height * 4
    if len(data) != expected:
        raise ValueError(
            f"expected {expected} bytes for {width}x{height} BGRA, got {len(data)}"
        )

    rows: List[bytes] = []
    for y in range(height):
        start = y * width * 4
        row = bytearray(data[start:start + width * 4])
        # PNG is RGBA; the buffer is BGRA.
        row[0::4], row[2::4] = row[2::4], row[0::4]
        # Filter type 0 (None) for every row. A smarter filter would compress better and
        # would also be the kind of thing that is subtly wrong; a screenshot is written
        # once and read by a human or a model, not stored by the million.
        rows.append(b"\x00" + bytes(row))

    if bottom_up:
        rows.reverse()

    ihdr = struct.pack(">IIBBBBB", width, height, _BIT_DEPTH, _COLOUR_TYPE_RGBA, 0, 0, 0)
    return (
        SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(b"".join(rows), 6))
        + _chunk(b"IEND", b"")
    )


def decode_png(data: bytes) -> Tuple[int, int, List[List[Tuple[int, int, int, int]]]]:
    """Decode what :func:`bgra_to_png` writes, back to pixels.

    Deliberately narrow: this reads the one shape that function produces, and exists so
    that the tests can compare pixels rather than bytes. It is not a general PNG reader and
    says so by raising on anything it does not expect, rather than returning something
    plausible.

    Returns:
        tuple: ``(width, height, rows)``, where each pixel is ``(r, g, b, a)``.
    """
    if not data.startswith(SIGNATURE):
        raise ValueError("not a PNG")
    pos = len(SIGNATURE)
    width = height = None
    idat = bytearray()
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, colour, comp, filt, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (depth, colour, comp, filt, interlace) != (_BIT_DEPTH, _COLOUR_TYPE_RGBA, 0, 0, 0):
                raise ValueError("only 8-bit RGBA, unfiltered, non-interlaced is written")
        elif kind == b"IDAT":
            idat += payload
        elif kind == b"IEND":
            break
    if width is None or height is None:
        raise ValueError("no IHDR")

    raw = zlib.decompress(bytes(idat))
    stride = width * 4
    rows: List[List[Tuple[int, int, int, int]]] = []
    for y in range(height):
        start = y * (stride + 1)
        filter_type = raw[start]
        if filter_type != 0:
            raise ValueError(f"row {y} has filter type {filter_type}, not 0")
        row = raw[start + 1:start + 1 + stride]
        rows.append([tuple(row[i:i + 4]) for i in range(0, stride, 4)])
    return width, height, rows
