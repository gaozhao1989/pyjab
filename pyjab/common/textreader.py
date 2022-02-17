import encodings
import locale
from typing import Optional


class TextReader(object):
    """Text reader for retrieve text or transfer text in different types."""

    @staticmethod
    def get_text_from_raw_bytes(
            buffer: bytes,
            chars_len: int,
            encoding: Optional[str] = None,
            errors_fallback: str = "replace",
    ) -> str:
        """[summary]

        Args:
            buffer (bytes): bytes object to convert to str.
            chars_len (int): character length for handle bytes.
            encoding (Optional[str], optional): encoding format for buffer. Defaults to None.
            errors_fallback (str, optional): error handling scheme for handling of decoding errors. Default: "replace".

        Returns:
            str: decoded text from buffer.
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
