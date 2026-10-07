"""Differential oracle for the textreader clean-room rewrite.

Java Access Bridge fills a caller-allocated byte buffer and reports how many
characters it wrote, but not how they are encoded.  Working that out is the one
piece of real logic pyjab took from NVDA, so it is the one piece that had to be
written again from scratch.

A rewrite is only trustworthy if it behaves identically, and "looks equivalent"
is not evidence.  This module keeps the pre-rewrite implementation and compares
the two over a matrix of inputs, including the awkward ones: an empty buffer, a
single character, a buffer whose tail is not zeroed, and an explicitly named
encoding in each of the spellings a caller might use.

The reference implementation is deleted once the comparison passes, so this file
records the behaviour it had rather than shipping code that would otherwise be
gone.
"""

from __future__ import annotations

import encodings
import locale
from typing import Optional


def reference_get_text_from_raw_bytes(
        buffer: bytes,
        chars_len: int,
        encoding: Optional[str] = None,
        errors_fallback: str = "replace",
) -> str:
    """The implementation as it stood before the rewrite, verbatim.

    Kept only as an oracle for ``test_textreader_rewrite.py``.
    """
    if encoding is None:
        if chars_len > 1 and any(buffer[chars_len:]):
            encoding = "utf_16_le"
        else:
            encoding = locale.getpreferredencoding()
    else:
        encoding = encodings.normalize_encoding(encoding).lower()
    if encoding.startswith("utf_16"):
        num_of_bytes = chars_len * 2
    elif encoding.startswith("utf_32"):
        num_of_bytes = chars_len * 4
    else:
        num_of_bytes = chars_len
    raw_text: bytes = buffer[:num_of_bytes]
    if not any(raw_text):
        return ""
    try:
        text = raw_text.decode(encoding, errors="surrogatepass")
    except UnicodeDecodeError:
        text = raw_text.decode(encoding, errors=errors_fallback)
    return text
