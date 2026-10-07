"""Making text out of the byte buffers Java Access Bridge hands back.

No JAB call returns a string.  The caller allocates a byte buffer, the call
writes characters into it and reports how many it wrote, and the encoding is
never part of the reply.  What comes back is therefore a character count and a
heap of bytes, and turning that into a ``str`` means working out how the bytes
are laid out.
"""

from __future__ import annotations

import encodings
import locale
from typing import Optional

#: How many bytes one character occupies in each family of wide encodings a JVM
#: may have used.  Narrowing a buffer to ``characters * width`` bytes gives back
#: exactly the text the call reported writing.
_WIDE_BYTE_WIDTH = (
    ("utf_16", 2),
    ("utf_32", 4),
)


class TextReader(object):
    """Decodes the character buffers returned by Java Access Bridge."""

    @staticmethod
    def get_text_from_raw_bytes(
            buffer: bytes,
            chars_len: int,
            encoding: Optional[str] = None,
            errors_fallback: str = "replace",
    ) -> str:
        """Decode ``chars_len`` characters from the start of ``buffer``.

        Args:
            buffer (bytes): the bytes the JAB call wrote into.
            chars_len (int): how many characters it reported writing.
            encoding (Optional[str], optional): the encoding, when the caller
                knows it.  Left as ``None`` it is worked out from the buffer,
                which is what :meth:`_sniff_encoding` does.  Defaults to None.
            errors_fallback (str, optional): how to handle bytes that cannot be
                decoded strictly.  Defaults to "replace".

        Returns:
            str: the decoded text, or ``""`` when the buffer holds nothing.
        """
        if encoding is None:
            encoding = TextReader._sniff_encoding(buffer, chars_len)
        else:
            encoding = encodings.normalize_encoding(encoding).lower()

        raw_text = buffer[:chars_len * TextReader._byte_width(encoding)]
        if not any(raw_text):
            return ""

        try:
            return raw_text.decode(encoding, errors="surrogatepass")
        except UnicodeDecodeError:
            return raw_text.decode(encoding, errors=errors_fallback)

    @staticmethod
    def _sniff_encoding(buffer: bytes, chars_len: int) -> str:
        """Work out the encoding of a buffer that arrived without one.

        Java strings are UTF-16, so a wide buffer is twice as long as the
        character count says, and bytes past the first ``chars_len`` of them are
        the evidence of that.  A narrow buffer zero-padded to the same size has
        only zeroes there, which is why ``any`` is the test rather than a length
        comparison.

        One character is always read as narrow.  Two bytes of UTF-16 are not
        longer than the single character they encode, so there is nothing for
        the test above to find and the locale's encoding would have to be
        assumed anyway.  This mirrors what Java Access Bridge actually returns
        for the single-character calls, where a wide read is not requested.
        """
        if chars_len > 1 and any(buffer[chars_len:]):
            return "utf_16_le"
        return locale.getpreferredencoding()

    @staticmethod
    def _byte_width(encoding: str) -> int:
        """How many bytes one character of ``encoding`` occupies.

        Everything not in :data:`_WIDE_BYTE_WIDTH` -- the locale encodings and
        the various UTF-8 spellings -- stores one character per byte.
        """
        for prefix, width in _WIDE_BYTE_WIDTH:
            if encoding.startswith(prefix):
                return width
        return 1
