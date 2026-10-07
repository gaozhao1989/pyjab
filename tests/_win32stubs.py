"""Shared pywin32 stand-ins, and helpers to import Windows-only modules.

``pyjab.jabelement`` and ``pyjab.jabdriver`` import pywin32 at module scope and
refuse to import at all off Windows.  On Linux and macOS these helpers install
permissive stand-ins so that their *logic* can still be exercised -- which is
what keeps most of pyjab's behaviour verifiable without a Windows machine.

Two properties matter, and both are the result of a bug that got through once:

* stand-ins are installed only for modules that are genuinely missing, so on a
  real Windows checkout (where ``pip install .[dev]`` brings in pywin32) nothing
  here replaces anything;
* replacing a module that the code under test already bound is done by patching
  the *consumer's* attribute, not ``sys.modules``.  See the ``pump`` fixture in
  ``tests/test_message_pump.py``.

Importing this module installs the stand-ins as a side effect, so import it
before importing anything from pyjab that needs them.
"""

import contextlib
import importlib
import sys
import types
from unittest.mock import MagicMock

#: pywin32 modules pyjab touches, none of which exist off Windows.
STUB_MODULES = (
    "win32api",
    "win32clipboard",
    "win32con",
    "win32gui",
    "win32process",
)


class _PermissiveModule(types.ModuleType):
    """A module whose every attribute access yields a callable stub.

    Dunders are refused rather than mocked: faking ``__path__`` or ``__spec__``
    breaks the import machinery and ``isinstance`` checks.
    """

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        stub = MagicMock(name=name)
        setattr(self, name, stub)
        return stub


class ComError(Exception):
    """Stand-in for ``pythoncom.com_error``."""


def _available(name: str) -> bool:
    if name in sys.modules:
        return True
    try:
        importlib.import_module(name)
    except ImportError:
        return False
    return True


def install() -> bool:
    """Install a stand-in for every pywin32 module that is missing.

    Each module is probed on its own rather than treating ``pythoncom`` as proof
    that the whole of pywin32 is present: a partial installation would otherwise
    leave a gap, and the failure would be a bare ``ModuleNotFoundError`` at
    import time rather than a skipped test.

    Returns True when anything had to be stubbed.
    """
    stubbed = False

    if not _available("pythoncom"):
        pythoncom = _PermissiveModule("pythoncom")
        pythoncom.PumpWaitingMessages = MagicMock(return_value=False)
        pythoncom.com_error = ComError
        sys.modules["pythoncom"] = pythoncom
        stubbed = True

    for name in STUB_MODULES:
        if not _available(name):
            sys.modules[name] = _PermissiveModule(name)
            stubbed = True

    if not _available("win32com.client"):
        win32com = _PermissiveModule("win32com")
        win32com.client = _PermissiveModule("win32com.client")
        sys.modules["win32com"] = win32com
        sys.modules["win32com.client"] = win32com.client
        stubbed = True

    return stubbed


#: True when this process is running against stand-ins rather than real pywin32.
USING_STUBS = install()


@contextlib.contextmanager
def faked_platform(platform: str = "win32"):
    """Report *platform* through ``sys.platform`` for the duration of the block.

    Always restored: leaking ``"win32"`` sends later imports down Windows-only
    paths in the same process.
    """
    real = sys.platform
    sys.platform = platform
    try:
        yield
    finally:
        sys.platform = real


def import_jabelement():
    """Return ``JABElement``, working around its platform guard.

    ``PIL.ImageGrab`` is imported first, under the real platform, so that faking
    ``sys.platform`` cannot push PIL down a Windows-only import path.  On Windows
    itself all of this is a no-op.
    """
    import PIL.ImageGrab  # noqa: F401

    with faked_platform():
        from pyjab.jabelement import JABElement

    return JABElement


def import_jabdriver():
    """Return ``JABDriver``, working around its platform guard."""
    import PIL.ImageGrab  # noqa: F401

    with faked_platform():
        from pyjab.jabdriver import JABDriver

    return JABDriver
