# Support Packages

pyjab is small and leans on well-established libraries rather than
reimplementing them.

## [pywin32](https://github.com/mhammond/pywin32)

Windows API access from Python. pyjab uses it for the things Java Access Bridge
does not cover: enumerating windows, reading a window's process id, bringing a
window to the foreground, synthesising mouse and keyboard input, and window
geometry.

Only required on Windows — the dependency carries a `sys_platform == "win32"`
marker, so `pip install pyjab` does not request it on other platforms.

Note for anyone upgrading from 1.1.x: older releases declared **both**
`pypiwin32` and `pywin32`. `pypiwin32` is a deprecated shim that pins
`pywin32==223`, and having both made dependency resolution fail for every
released version. It was removed in 1.2.0.

## [Pillow](https://github.com/python-pillow/Pillow)

The friendly PIL fork. pyjab uses it for screenshots — window, element and
whole-screen capture — and to save them as PNG or return them as bytes or
base64.

## Standard library

pyjab uses `ctypes` to talk to `WindowsAccessBridge-64.dll`, and `pythoncom`
(from pywin32) to service the COM message queue that delivers Java Access Bridge
accessibility events.

## Development

Installing the test tooling:

```console
> pip install -e ".[dev]"
```

That adds `pytest`. The GUI test suite drives a small Swing application that lives
in `tests/java` and is compiled on demand, so nothing is downloaded to run it.
