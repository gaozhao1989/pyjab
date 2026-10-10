"""
Python implementation for Java application UI automation with Java Access Bridge.
"""
__author__ = "Gary Gao"
__email__ = "gaozhao89@qq.com"
__license__ = "MIT"
__url__ = "https://github.com/gaozhao1989/pyjab"
__version__ = "1.9.0"

# NOTE: no platform guard here on purpose.  pyjab.config and pyjab.common.service
# are platform independent and are unit tested on every OS, so `import pyjab`
# must stay harmless.  The Windows-only entry points (pyjab.jabdriver,
# pyjab.jabelement) raise a descriptive ImportError instead of letting a bare
# "No module named 'win32process'" escape.


def list_java_windows():
    """Every top-level window the bridge recognises as a Java window.

    Defined here, and imported inside the function, for the reason this module has no
    platform guard: ``import pyjab`` has to stay harmless on every OS, so a Windows-only
    body cannot be reached until it is called. Calling it elsewhere raises the descriptive
    ``ImportError`` that ``pyjab.jabdriver`` gives, rather than a bare missing-module one.

    Returns:
        list: dicts with ``hwnd``, ``title``, ``pid`` and ``vmid``.
    """
    from pyjab.jabdriver import list_java_windows as _list_java_windows

    return _list_java_windows()
