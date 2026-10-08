"""The rewritten TextReader must decode what the old one decoded.

This is the evidence for the clean-room rewrite: not that the new code reads well,
but that across every input shape the two agree.

The comparison used to be made against the old implementation itself, kept in
``tests/_textreader_reference.py``.  That worked, and it was the wrong thing to
ship: the old implementation was derived from NVDA's GPLv2
``getTextFromRawBytes``, and a test file travels in the sdist.  An MIT
distribution carrying a verbatim copy of the code the rewrite removed defeats the
point of removing it.

So the behaviour is recorded as data instead -- ``tests/_textreader_oracle.py``
holds 1,764 ``input -> output`` pairs generated from
``git show v1.5.0:pyjab/common/textreader.py``.  The comparison is identical; only
what it compares against has changed.  Facts about what some code did are not that
code.

The calls that do *not* state an encoding are checked separately, because their
answer depends on the machine: ``TextReader`` asks ``locale.getpreferredencoding()``
and gets UTF-8 on macOS and cp1252 on Windows.  Freezing the decoded text would
freeze the locale of whatever machine generated the table -- which the first
version of this file did, passing here and failing on every Windows job.  What is
the same everywhere is which encoding gets chosen, so ``SNIFFED_WIDE`` records that
and the test checks the choice against the same implementation given the encoding
explicitly.
"""

from __future__ import annotations

import importlib.util
import locale
from pathlib import Path

import pytest

from pyjab.common.textreader import TextReader

REPO_ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "textreader_oracle", REPO_ROOT / "tests" / "_textreader_oracle.py"
)
oracle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oracle)


def cases():
    """Each oracle row, as ``(buffer, chars_len, encoding, expected)``."""
    for line in oracle.DATA.splitlines():
        if not line.strip():
            continue
        buffer_hex, chars_len, encoding, expected_hex = line.split("|")
        yield (
            bytes.fromhex(buffer_hex),
            int(chars_len),
            encoding or None,
            bytes.fromhex(expected_hex).decode("utf-8", "surrogatepass"),
        )


def sniffing():
    """Each ``buffer|chars_len|wide`` row, as ``(buffer, chars_len, wide)``."""
    for line in oracle.SNIFFED_WIDE.splitlines():
        if not line.strip():
            continue
        buffer_hex, chars_len, wide = line.split("|")
        yield bytes.fromhex(buffer_hex), int(chars_len), bool(int(wide))


ALL_CASES = list(cases())
ALL_SNIFFING = list(sniffing())

ENCODINGS = sorted({case[2] for case in ALL_CASES})
BUFFERS = sorted({case[0] for case in ALL_CASES})
LENGTHS = sorted({case[1] for case in ALL_CASES})


def test_the_oracle_covers_the_matrix_it_claims_to():
    """Guards the data against being quietly trimmed.

    A table of two rows would satisfy every assertion below and prove nothing.
    """
    assert len(ENCODINGS) == 14, "the rows with a stated encoding"
    assert len(BUFFERS) == 18
    assert len(LENGTHS) == 7
    assert len(ALL_CASES) == len(ENCODINGS) * len(BUFFERS) * len(LENGTHS) == 1764
    assert len(ALL_SNIFFING) == len(BUFFERS) * len(LENGTHS) == 126


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: repr(c[:3])[:60])
def test_the_rewrite_decodes_what_the_old_implementation_decoded(case):
    buffer, chars_len, encoding, expected = case

    assert TextReader.get_text_from_raw_bytes(buffer, chars_len, encoding) == expected


# ---------------------------------------------------------------------------
# The branches, named, so a failure says which one rather than only which row
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", ALL_SNIFFING, ids=lambda c: repr(c[:2])[:50])
def test_the_encoding_is_chosen_the_way_it_always_was(case):
    """Which encoding a buffer without one is read as.

    Checked by giving the same implementation that encoding explicitly and
    comparing: the locale can differ between machines, so the decoded text cannot
    be frozen, but *which* of the two branches is taken cannot differ and is.
    """
    buffer, chars_len, wide = case
    chosen = "utf_16_le" if wide else locale.getpreferredencoding()

    assert TextReader.get_text_from_raw_bytes(buffer, chars_len, None) == \
        TextReader.get_text_from_raw_bytes(buffer, chars_len, chosen)


def test_some_of_those_choices_are_observable():
    """Guards against the test above passing vacuously.

    Where both encodings produce the same text -- an empty buffer, most of them --
    comparing the two proves nothing about which branch ran.  Enough rows have to
    differ for the check to mean something.
    """
    observable = [
        case for case in ALL_SNIFFING
        if TextReader.get_text_from_raw_bytes(case[0], case[1], "utf_16_le")
        != TextReader.get_text_from_raw_bytes(case[0], case[1],
                                               locale.getpreferredencoding())
    ]

    assert len(observable) >= 50, f"only {len(observable)} rows distinguish the branches"


def test_an_empty_buffer_decodes_to_empty_text():
    """The branch that returns early."""
    assert TextReader.get_text_from_raw_bytes(b"\x00" * 32, 16) == ""


def test_a_wide_buffer_is_detected_from_its_tail():
    """The heuristic this file exists to pin down."""
    assert TextReader.get_text_from_raw_bytes(b"ab\x00\x00\x00\x00", 2) == "ab"


def test_a_single_character_is_read_as_narrow():
    """Documented as intentional rather than changed by the rewrite.

    Two bytes of UTF-16 are not longer than the one character they encode, so the
    tail test has nothing to find and the locale's encoding is used.  The rewrite
    keeps that: a compliance refactor is the wrong place to change what a text
    read returns.
    """
    assert TextReader.get_text_from_raw_bytes(b"A\x00", 1) == "A"


@pytest.mark.parametrize("fallback", ["replace", "ignore", "backslashreplace"])
def test_the_error_fallback_is_honoured(fallback):
    """Undecodable bytes reach the caller's chosen handler rather than raising."""
    result = TextReader.get_text_from_raw_bytes(
        b"\xff\xfe\xfd\xfc", 4, "utf_8", errors_fallback=fallback
    )

    assert isinstance(result, str)


def test_a_lone_surrogate_survives():
    """``surrogatepass`` is why a JAB buffer's surrogates do not raise.

    Plain UTF-8 cannot hold this character, which is also why the oracle stores
    its expected values as hex.
    """
    result = TextReader.get_text_from_raw_bytes(b"\x41\x00\x00\xd8", 2, "utf_16_le")

    assert "\ud800" in result
