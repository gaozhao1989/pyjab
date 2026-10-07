"""The rewritten TextReader must decode exactly what the old one decoded.

This is the evidence for the clean-room rewrite: not that the new code reads
well, but that across every input shape the two agree.  The oracle lives in
``_textreader_reference.py`` and is the pre-rewrite implementation verbatim; it
exists only for this comparison.
"""

from __future__ import annotations

import pytest

from pyjab.common.textreader import TextReader
from tests._textreader_reference import reference_get_text_from_raw_bytes

#: Every encoding spelling a caller might pass, including the ones that need
#: normalising before they can be compared by prefix.
ENCODINGS = [
    None,
    "utf_16_le",
    "utf-16-le",
    "UTF-16LE",
    "utf_16",
    "utf16",
    "utf_32_le",
    "utf-32-le",
    "utf_8",
    "utf8",
    "UTF-8",
    "latin-1",
    "latin_1",
    "cp1252",
    "ascii",
]

#: Buffers covering the shapes JAB actually produces, plus the awkward ones.
BUFFERS = [
    b"",
    b"\x00",
    b"\x00" * 8,
    b"A",
    b"A\x00",
    b"A\x00B\x00",
    b"A\x00B\x00\x00\x00\x00\x00",
    b"AB",
    b"AB\x00\x00\x00\x00\x00\x00",
    b"ABCD",
    b"ABCD\x00\x00\x00\x00",
    b"\x41\x00\x00\xd8",              # a lone UTF-16 surrogate
    "\u00e9\u00e8".encode("utf_16_le") + b"\x00\x00",
    "\u4e2d\u6587".encode("utf_16_le") + b"\x00\x00\x00\x00",
    "\u4e2d\u6587".encode("utf_8"),
    b"\xff\xfe\xfd\xfc",              # never valid UTF-8
    bytes(range(16)),
    b"\x00\x00\x00\x00AB",            # zeroes first, text later
]


@pytest.mark.parametrize("encoding", ENCODINGS)
@pytest.mark.parametrize("buffer", BUFFERS)
@pytest.mark.parametrize("chars_len", [0, 1, 2, 3, 4, 8, 16])
def test_the_rewrite_agrees_with_the_old_implementation(buffer, chars_len, encoding):
    expected = reference_get_text_from_raw_bytes(buffer, chars_len, encoding)
    actual = TextReader.get_text_from_raw_bytes(buffer, chars_len, encoding)

    assert actual == expected, (
        f"buffer={buffer!r} chars_len={chars_len} encoding={encoding!r}"
    )


@pytest.mark.parametrize("fallback", ["replace", "ignore", "backslashreplace"])
def test_the_error_fallback_is_honoured_the_same_way(fallback):
    buffer = b"\xff\xfe\xfd\xfc"

    expected = reference_get_text_from_raw_bytes(
        buffer, 4, "utf_8", errors_fallback=fallback
    )
    actual = TextReader.get_text_from_raw_bytes(
        buffer, 4, "utf_8", errors_fallback=fallback
    )

    assert actual == expected


def test_an_empty_buffer_decodes_to_empty_text():
    """Guarded separately because it is the branch that returns early."""
    assert TextReader.get_text_from_raw_bytes(b"\x00" * 32, 16) == ""
    assert reference_get_text_from_raw_bytes(b"\x00" * 32, 16) == ""


def test_a_wide_buffer_is_detected_from_its_tail():
    """The heuristic this file exists to pin down."""
    assert TextReader.get_text_from_raw_bytes(b"ab\x00\x00\x00\x00", 2) == "ab"


def test_a_single_character_is_read_as_narrow():
    """Documented as intentional rather than changed by the rewrite.

    Two bytes of UTF-16 are not longer than the one character they encode, so
    the tail test has nothing to find and the locale's encoding is used.  The
    rewrite keeps that: a compliance refactor is the wrong place to change what
    a text read returns.
    """
    single = b"A\x00"

    assert (
        TextReader.get_text_from_raw_bytes(single, 1)
        == reference_get_text_from_raw_bytes(single, 1)
    )
