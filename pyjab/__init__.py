"""
Python implementation for Java application UI automation with Java Access Bridge.
"""
__author__ = "Gary Gao"
__email__ = "gaozhao89@qq.com"
__license__ = "MIT"
__url__ = "https://github.com/gaozhao1989/pyjab"
__version__ = "1.7.0"

# NOTE: no platform guard here on purpose.  pyjab.config and pyjab.common.service
# are platform independent and are unit tested on every OS, so `import pyjab`
# must stay harmless.  The Windows-only entry points (pyjab.jabdriver,
# pyjab.jabelement) raise a descriptive ImportError instead of letting a bare
# "No module named 'win32process'" escape.
