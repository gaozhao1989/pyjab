"""A library does not configure logging.

``Logger.__init__`` called ``logging.basicConfig``, which configures the **root** logger.
Because ``Logger`` is a singleton (AGENTS.md 2.9) that happened once per process, on first
use — so importing pyjab silently decided the format and the level for every other logger
in the host application, and nothing in the host could tell that it had been decided.

The failure mode is not an exception, and it is not visible in pyjab's own test output
unless the tests look for it, which is why these do.
"""

from __future__ import annotations

import logging

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

from pyjab.common.logger import Logger


@pytest.fixture
def untouched_root():
    """The root logger's configuration, restored afterwards.

    Restoring matters: these tests assert that nothing changed, so a test that changed
    something on purpose (the counter-example below) would otherwise leave the process
    configured and make later tests pass or fail for the wrong reason.
    """
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield root
    root.handlers[:] = handlers
    root.setLevel(level)


def test_using_the_logger_does_not_touch_the_root_logger(untouched_root):
    """The property. Adding a handler to root is exactly what basicConfig does."""
    before = (len(untouched_root.handlers), untouched_root.level)

    Logger("probe")
    Logger("probe").info("something")

    after = (len(untouched_root.handlers), untouched_root.level)
    assert after == before, (
        "pyjab configured the root logger. A library must not: the application decides "
        "where its logs go, and it cannot un-decide what it never decided."
    )


def test_the_library_logger_has_a_null_handler(untouched_root):
    """So that a record does not reach the `lastResort` handler and print a warning.

    Without any handler, Python logs to `lastResort` at WARNING and above, which is how a
    library that "does not configure logging" still ends up writing to stderr.
    """
    logger = Logger("probe").log

    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)


def test_the_measurement_can_move(untouched_root):
    """The assertion above has to be able to fail.

    A test that "nothing changed" passes just as well when the code under test is not
    running at all, so this shows the thing being measured actually moving.

    It configures root **directly** rather than through ``logging.basicConfig``, because
    that call is a no-op when root already has a handler -- which under pytest it does. A
    counter-example that quietly does nothing is worse than none, and this one was written
    that way first.
    """
    before = (len(untouched_root.handlers), untouched_root.level)

    untouched_root.addHandler(logging.StreamHandler())
    untouched_root.setLevel(logging.DEBUG)

    after = (len(untouched_root.handlers), untouched_root.level)
    assert after != before
