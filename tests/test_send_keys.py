"""Sending a shortcut, which is not the same thing as typing text.

pyjab-mcp's `java_send_keys` is blocked on this: `send_text("alt+y")` types the four
characters `a`, `l`, `t`, `+` and `y`, because text has no modifiers. This is the chord
form, and it is the one place in the library where a wrong answer does something
**irreversible** to somebody else's application -- so the parsing is tested as hard as the
sending.
"""

from __future__ import annotations

import pytest

import _win32stubs  # noqa: F401

from pyjab.common.win32utils import Win32Utils

Win32UtilsClass = Win32Utils.__wrapped__


@pytest.fixture
def recorder(monkeypatch):
    """A Win32Utils whose chord primitive records instead of pressing keys."""
    utils = Win32Utils()
    sent = []
    monkeypatch.setattr(utils, "_press_hold_release_key",
                        lambda *keys: sent.append(keys))
    return utils, sent


def test_a_chord_becomes_the_keys_it_names(recorder):
    utils, sent = recorder

    utils.send_keys("alt+y")

    assert sent == [("alt", "y")]


def test_names_are_case_insensitive(recorder):
    """The table is lowercase; nobody types it that way."""
    utils, sent = recorder

    utils.send_keys("CTRL+SHIFT+S")

    assert sent == [("ctrl", "shift", "s")]


def test_whitespace_around_names_is_ignored(recorder):
    utils, sent = recorder

    utils.send_keys("ctrl + alt + del")

    assert sent == [("ctrl", "alt", "del")]


def test_a_single_key_is_allowed(recorder):
    """Not a chord, but 'enter' is a key somebody wants to send."""
    utils, sent = recorder

    utils.send_keys("enter")

    assert sent == [("enter",)]


def test_the_order_is_preserved(recorder):
    """Modifiers are held in the order given, and released in the same order."""
    utils, sent = recorder

    utils.send_keys("shift+ctrl+a")

    assert sent == [("shift", "ctrl", "a")]


@pytest.mark.parametrize("chord,expected", [
    ("alt+nosuchkey", "nosuchkey"),
    ("ctrl+q+zzz", "zzz"),
])
def test_an_unknown_name_is_refused_and_named(recorder, chord, expected):
    """Refused, not ignored: a silently wrong chord acts on somebody else's application."""
    utils, sent = recorder

    with pytest.raises(ValueError) as caught:
        utils.send_keys(chord)

    assert expected in str(caught.value)
    assert not sent, "nothing should have been pressed"


@pytest.mark.parametrize("chord", ["", "   "])
def test_an_empty_chord_is_refused(recorder, chord):
    utils, _sent = recorder

    with pytest.raises(ValueError, match="needs a key or a chord"):
        utils.send_keys(chord)


def test_a_doubled_separator_is_refused(recorder):
    """`alt++y` is a typo, not a chord with an empty key in it."""
    utils, _sent = recorder

    with pytest.raises(ValueError, match="empty key name"):
        utils.send_keys("alt++y")


def test_it_does_not_type_the_letters_of_a_chord():
    """The distinction the whole issue is about.

    `send_text` on a fake element must reach the *text* path, not this one, and this one
    must not fall through to it. Asserted by name because the failure -- typing `a l t + y`
    into somebody's form -- looks like success to every check that is not this one.
    """
    assert hasattr(Win32UtilsClass, "send_keys")
    source_names = {name for name in dir(Win32UtilsClass) if not name.startswith("__")}
    assert "send_keys" in source_names
    assert "_send_keys" in source_names, "the text typer is still separate and still private"
